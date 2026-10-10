#!/bin/bash
set -euo pipefail

# Run only in the dedicated fresh-build VM. No phone hardware is initialized.
ns=iphone6s-repro-test
root=/home/ubuntu/iphone6s-userspace-test-2
evidence=/home/ubuntu/repro-evidence
if ip netns list | grep -q "^${ns}\b"; then exit 1; fi
if ip link show rphost >/dev/null 2>&1; then exit 1; fi
test ! -e "$root"
test ! -e "$evidence/userspace-ready"
test ! -e "$evidence/userspace-finish"
cp -a /home/ubuntu/iphone6s-server-rootfs "$root"
chmod 700 "$root"
ip netns add "$ns"
cleanup() {
    set +e
    for process in $(ip netns pids "$ns"); do kill -TERM "$process"; done
    ip netns delete "$ns"
    if ip link show rphost >/dev/null 2>&1; then ip link delete rphost; fi
    printf 'cleaned\n' > "$evidence/userspace-cleaned"
}
trap cleanup EXIT INT TERM
ip link add rphost type veth peer name rpguest
ip link set rpguest netns "$ns"
ip addr add 172.16.42.2/24 dev rphost
ip link set rphost up
ip -n "$ns" addr add 172.16.42.1/24 dev rpguest
ip -n "$ns" link set rpguest up
ip -n "$ns" link set lo up
ip netns exec "$ns" unshare --mount --uts --pid --fork --kill-child \
    bash -s -- "$root" "$evidence" <<'INNER' &
set -euo pipefail
root=$1
evidence=$2
mount --make-rprivate /
mount -t proc proc "$root/proc"
mount -t tmpfs -o mode=755 tmpfs "$root/dev"
for node in 'null 1 3' 'zero 1 5' 'random 1 8' 'urandom 1 9' 'tty 5 0'; do
    read -r name major minor <<< "$node"
    mknod -m 666 "$root/dev/$name" c "$major" "$minor"
done
mkdir "$root/dev/pts"
mount -t devpts -o newinstance,ptmxmode=0666,mode=0620 devpts "$root/dev/pts"
ln -s pts/ptmx "$root/dev/ptmx"
chroot "$root" /bin/busybox --install -s
chroot "$root" /usr/local/sbin/start-terminal > "$evidence/userspace-terminal.log" 2>&1
chroot "$root" /bin/busybox httpd -f -p 172.16.42.1:8080 -h /srv/iphone \
    > "$evidence/userspace-http.log" 2>&1 &
printf 'ready\n' > "$evidence/userspace-ready"
for attempt in $(seq 1 300); do
    if test -e "$evidence/userspace-finish"; then exit 0; fi
    sleep 1
done
exit 124
INNER
child=$!
wait "$child"
