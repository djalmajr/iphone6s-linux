#!/bin/sh
set -eu
stage=$1
manager_hash=$2
hosts_hash=$3
old_manager_hash=$4
old_hosts_hash=$5
case "$stage" in /srv/data/.dev-dns-*) ;; *) exit 2 ;; esac
suffix=${stage#/srv/data/.dev-dns-}
[ "${#suffix}" = 32 ] || exit 2
case "$suffix" in *[!a-f0-9]*) exit 2 ;; esac
[ "$#" = 5 ] || exit 2
for digest in "$manager_hash" "$hosts_hash" "$old_manager_hash" "$old_hosts_hash"; do
    [ "${#digest}" = 64 ] || exit 2
    case "$digest" in *[!a-f0-9]*) exit 2 ;; esac
done
base=/srv/data/dns
lock=/run/iphone-dev-dns.lock
regular() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(stat -c '%h:%u' "$1")" = 1:0 ]
}
verify() { [ "$(sha256sum "$1" | cut -d ' ' -f1)" = "$2" ]; }
for directory in /srv /srv/data "$base" "$stage" "$base/runtime" "$base/runtime/bin" /run; do
    [ -d "$directory" ] && [ ! -L "$directory" ] || exit 2
done
for file in "$base/manage-dns.sh" "$base/hosts" "$base/runtime/bin/dnsmasq" "$stage/manager" "$stage/hosts"; do
    regular "$file" || exit 2
done
verify "$stage/manager" "$manager_hash"
verify "$stage/hosts" "$hosts_hash"
for temporary in "$base/.dev-manager-$suffix" "$base/.dev-hosts-$suffix"; do
    [ ! -e "$temporary" ] && [ ! -L "$temporary" ] || exit 2
done
mkdir "$lock" || exit 2
running=0
old_saved=0
finish() {
    result=$?
    trap - EXIT HUP INT TERM
    if [ "$result" -ne 0 ] && [ "$old_saved" = 1 ]; then
        # Stop only an instance identified by the selected DNS manager.
        /bin/sh "$base/manage-dns.sh" stop >/dev/null 2>&1 || true
        cp "$stage/old-manager" "$base/.dev-manager-$suffix"
        cp "$stage/old-hosts" "$base/.dev-hosts-$suffix"
        mv "$base/.dev-manager-$suffix" "$base/manage-dns.sh"
        mv "$base/.dev-hosts-$suffix" "$base/hosts"
        if verify "$base/manage-dns.sh" "$old_manager_hash" && verify "$base/hosts" "$old_hosts_hash"; then
            if [ "$running" = 0 ] || /bin/sh "$base/manage-dns.sh" start; then
                echo DEV_ROLLBACK_VERIFIED
            else
                echo DEV_RECOVERY_REQUIRED >&2
            fi
        else
            echo DEV_RECOVERY_REQUIRED >&2
        fi
    fi
    rm -f "$base/.dev-manager-$suffix" "$base/.dev-hosts-$suffix"
    rmdir "$lock"
    exit "$result"
}
trap finish EXIT
trap 'exit 1' HUP INT TERM
verify "$base/manage-dns.sh" "$old_manager_hash"
verify "$base/hosts" "$old_hosts_hash"
cp -p "$base/manage-dns.sh" "$stage/old-manager"
cp -p "$base/hosts" "$stage/old-hosts"
if /bin/sh "$base/manage-dns.sh" status >/dev/null 2>&1; then
    running=1
else
    result=$?
    [ "$result" = 1 ] || exit 2
fi
old_saved=1
if [ "$running" = 1 ]; then /bin/sh "$base/manage-dns.sh" stop; fi
cp "$stage/manager" "$base/.dev-manager-$suffix"
chmod 755 "$base/.dev-manager-$suffix"
cp "$stage/hosts" "$base/.dev-hosts-$suffix"
chmod 644 "$base/.dev-hosts-$suffix"
verify "$base/.dev-manager-$suffix" "$manager_hash"
verify "$base/.dev-hosts-$suffix" "$hosts_hash"
mv "$base/.dev-manager-$suffix" "$base/manage-dns.sh"
mv "$base/.dev-hosts-$suffix" "$base/hosts"
verify "$base/manage-dns.sh" "$manager_hash"
verify "$base/hosts" "$hosts_hash"
/bin/sh "$base/manage-dns.sh" start
/bin/sh "$base/manage-dns.sh" status >/dev/null
printf 'DEV_APPLIED %s\n' "$suffix"
