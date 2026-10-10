#!/bin/sh
# Synthetic USB/SSH boundary for the real return-to-iOS CLI and snapshot tests.
set -eu
base=${0%/*}
base=${base%/*}
name=${0##*/}
mode=
IFS= read -r mode < "$base/mode" || [ -n "$mode" ]
printf '%s\n' "$name" >> "$base/events"

case "$name" in
    idevice_id)
        [ "$#" = 1 ] && [ "$1" = -l ] || exit 2
        [ "$mode" != usb-error ] || exit 1
        if [ -e "$base/phase" ] || [ "$mode" = already-ios ]; then
            printf '%s\n' SYNTHETIC-USB-ID-NOT-FOR-LOGS
        fi
        if [ -e "$base/phase" ] && [ "$mode" = multiple ]; then
            printf '%s\n' SECOND-USB-ID
        fi
        ;;
    ioreg)
        if [ "$mode" = bad-plist ]; then
            printf '%s\n' 'invalid plist'
        else
            count=0
            while IFS= read -r event; do
                if [ "$event" = ioreg ]; then count=$((count + 1)); fi
            done < "$base/events"
            printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><plist version="1.0">'
            if [ "$mode" = linux-stays ] || { [ "$mode" = linux-returns ] && [ "$count" -ge 2 ]; }; then
                printf '%s\n' '<array><dict/></array>'
            else
                printf '%s\n' '<array/>'
            fi
            printf '%s\n' '</plist>'
        fi
        ;;
    ideviceinfo)
        [ "$#" = 4 ] && [ "$1" = -u ] && [ "$2" = SYNTHETIC-USB-ID-NOT-FOR-LOGS ] &&
            [ "$3" = -k ] && [ "$4" = ProductType ] || exit 2
        [ "$mode" != info-error ] || exit 1
        if [ "$mode" = wrong-model ]; then
            printf '%s\n' iPhone99,9
        else
            printf '%s\n' iPhone8,1
        fi
        ;;
    ssh)
        strict=0 identities=0 alias=0 global_hosts=0 command=
        for argument do
            case "$argument" in
                StrictHostKeyChecking=yes) strict=1 ;;
                IdentitiesOnly=yes) identities=1 ;;
                HostKeyAlias=candidate-test) alias=1 ;;
                GlobalKnownHostsFile=/dev/null) global_hosts=1 ;;
            esac
            command=$argument
        done
        [ "$strict" = 1 ] && [ "$identities" = 1 ] || exit 2
        if [ -e "$base/expect-alias" ]; then
            [ "$alias" = 1 ] && [ "$global_hosts" = 1 ] || exit 2
        fi
        case "$command" in
            *IPHONE_LINUX_READY*)
                [ "$mode" != pin-error ] || exit 255
                printf '%s\n' IPHONE_LINUX_READY
                ;;
            *'tar -czf'*)
                if [ "$mode" = slow-backup ]; then
                    : > "$base/owned.pid.tmp"
                    if [ -e "$base/hold-pid-publication" ]; then
                        : > "$base/pid-opened"
                        count=0
                        while [ ! -e "$base/release-pid-publication" ]; do
                            [ "$count" -lt 1000 ] || exit 1
                            count=$((count + 1))
                            /bin/sleep 0.01
                        done
                    fi
                    printf '%s' "$$" > "$base/owned.pid.tmp"
                    /bin/mv "$base/owned.pid.tmp" "$base/owned.pid"
                    exec /bin/sleep 60
                fi
                exec /bin/cat "$base/incoming.tar.gz"
                ;;
            *)
                case "$command" in
                    *IPHONE_SYNC_COMPLETE*)
                        case "$command" in
                            *reboot*) ;;
                            *)
                                printf '%s\n' SYNC >> "$base/events"
                                case "$command" in *'sync;'*) ;; *) exit 2 ;; esac
                                [ "$mode" != sync-error ] || exit 1
                                [ "$mode" != sync-disconnect ] || exit 255
                                if [ "$mode" != missing-sync ]; then
                                    printf '%s\n' IPHONE_SYNC_COMPLETE
                                fi
                                exit 0
                                ;;
                        esac
                        ;;
                esac
                printf '%s\n' REBOOT >> "$base/events"
                case "$command" in *'reboot -f'*) ;; *) exit 2 ;; esac
                case "$command" in
                    *'sync;'*) ;;
                    *)
                        synced=0
                        while IFS= read -r event; do
                            if [ "$event" = SYNC ]; then synced=1; fi
                        done < "$base/events"
                        [ "$synced" = 1 ] || exit 2
                        ;;
                esac
                [ "$mode" != sync-error ] || exit 1
                case "$mode" in
                    missing-sync|fast-reboot) ;;
                    *) printf '%s\n' IPHONE_SYNC_COMPLETE ;;
                esac
                : > "$base/phase"
                [ "$mode" != request-error ] || exit 1
                case "$mode" in ssh-disconnect|fast-reboot) exit 255 ;; esac
                ;;
        esac
        ;;
    *) exit 2 ;;
esac
