#!/bin/sh
set -eu

export PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin
BASE=/srv/data/dns
RUN=/run/iphone-dns
BINARY=$BASE/runtime/bin/dnsmasq

process_ticks() { awk '{print $22}' "/proc/$1/stat"; }

owned_pid() {
    [ -f "$RUN/state" ] && [ ! -L "$RUN/state" ] || return 1
    read -r pid ticks extra < "$RUN/state"
    case "$pid:$ticks" in *[!0-9:]*|:*|*:) return 2 ;; esac
    [ -z "${extra:-}" ] || return 2
    kill -0 "$pid" 2>/dev/null || return 1
    [ "$(readlink "/proc/$pid/exe")" = "$BINARY" ] || return 2
    [ "$(process_ticks "$pid")" = "$ticks" ] || return 2
    printf '%s\n' "$pid"
}

prepare_account() {
    if grep -q '^nobody:' /etc/passwd; then
        [ "$(awk -F: '$1=="nobody" {print $3 ":" $4}' /etc/passwd)" = 65534:65534 ] || return 1
    else
        [ -z "$(awk -F: '$3==65534 {print $1}' /etc/passwd)" ] || return 1
    fi
    if grep -q '^nobody:' /etc/group; then
        [ "$(awk -F: '$1=="nobody" {print $3}' /etc/group)" = 65534 ] || return 1
    else
        [ -z "$(awk -F: '$3==65534 {print $1}' /etc/group)" ] || return 1
    fi
    if ! grep -q '^nobody:' /etc/passwd; then
        printf 'nobody:x:65534:65534:DNS service:/nonexistent:/bin/false\n' >> /etc/passwd
    fi
    if ! grep -q '^nobody:' /etc/group; then
        printf 'nobody:x:65534:\n' >> /etc/group
    fi
}

start() {
    [ "$(id -u)" = 0 ] || { echo 'Start requires phone root.' >&2; return 1; }
    if [ ! -f "$BINARY" ] || [ ! -x "$BINARY" ]; then
        echo 'Verified DNS runtime missing.' >&2
        return 1
    fi
    mkdir -p "$BASE" "$RUN"
    chmod 700 "$RUN"
    if pid=$(owned_pid); then
        printf 'DNS already running: %s\n' "$pid"
        return
    else
        result=$?
        [ "$result" = 1 ] || { echo 'Untrusted/stale PID reference; refusing start.' >&2; return 1; }
    fi
    prepare_account || { echo 'DNS account conflicts with existing identity.' >&2; return 1; }
    if [ ! -e "$BASE/hosts" ]; then
        printf '172.16.42.1 iphone-usb.home.arpa\n' > "$BASE/hosts"
        chmod 644 "$BASE/hosts"
    fi
    if [ ! -f "$BASE/hosts" ] || [ -L "$BASE/hosts" ]; then
        echo 'Hosts must be a regular file.' >&2
        return 1
    fi
    export LD_LIBRARY_PATH=$BASE/runtime/lib
    set -- --conf-file=/dev/null --no-resolv --no-hosts '--local=/#/' \
        --cache-size=0 --bind-interfaces --listen-address=172.16.42.1 --port=5353 \
        --addn-hosts="$BASE/hosts" --user=nobody --group=nobody \
        --no-dhcp-interface=usb0 --pid-file="$RUN/daemon.pid" --log-facility="$RUN/service.log"
    "$BINARY" --test "$@"
    "$BINARY" "$@"
    read -r child extra < "$RUN/daemon.pid"
    case "$child" in ''|*[!0-9]*) echo 'Invalid DNS daemon PID.' >&2; return 1 ;; esac
    [ -z "${extra:-}" ] && kill -0 "$child" 2>/dev/null || return 1
    if [ "$(readlink "/proc/$child/exe")" != "$BINARY" ]; then
        echo 'DNS executable identity not confirmed.' >&2
        return 1
    fi
    printf '%s %s\n' "$child" "$(process_ticks "$child")" > "$RUN/state"
    chmod 600 "$RUN/state"
    printf 'Local-only DNS ready on 172.16.42.1:5353 (UDP/TCP).\n'
}

stop() {
    if pid=$(owned_pid); then
        kill -TERM "$pid"
        for delay in 1 2 3 4 5; do
            if ! kill -0 "$pid" 2>/dev/null; then
                rm "$RUN/state"
                echo 'Owned DNS instance stopped.'
                return
            fi
            [ "$delay" -ge 5 ] || sleep 1
        done
        echo 'DNS did not exit; state retained.' >&2
        return 1
    else
        result=$?
        [ "$result" = 1 ] || { echo 'Untrusted/stale PID reference; refusing signal.' >&2; return 1; }
        echo 'DNS is not running.'
    fi
}

case "${1:-status}" in
    start) [ "$#" = 1 ]; start ;;
    stop) [ "$#" = 1 ]; stop ;;
    status) owned_pid ;;
    *) echo 'Usage: manage-dns.sh {start|stop|status}' >&2; exit 2 ;;
esac
