#!/usr/bin/env python3
"""Opt-in Bash session in the phone's volatile Herdr namespace."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import device_profile

ROOT = Path(__file__).resolve().parents[2]
PREAMBLE = r'''#!/bin/bash
set -eu
test -f /usr/local/bin/herdr && test ! -L /usr/local/bin/herdr
printf '%s\n' 'f4ccf4de745f2cb9a39a983e9ba3703dad50ec2a58dea83026ceab721bbd8d9e  /usr/local/bin/herdr' | sha256sum -c - >/dev/null
unset HERDR_ENV HERDR_SESSION HERDR_SOCKET_PATH HERDR_CLIENT_SOCKET_PATH HERDR_CONFIG_PATH HERDR_STARTUP_CWD HERDR_WORKSPACE_ID HERDR_PANE_ID HERDR_TAB_ID
export XDG_CONFIG_HOME=/run/iphone-herdr/config
export XDG_STATE_HOME=/run/iphone-herdr/state
export HERDR_CONFIG_PATH=/run/iphone-herdr/config/herdr/config.toml
export SHELL=/bin/bash
export TERM=xterm-256color
phone_herdr() { /usr/local/bin/herdr --session iphone-server "$@"; }
test "$(/usr/local/bin/herdr --version)" = 'herdr 0.9.1'
marker_valid() {
    test ! -L /srv/data
    test ! -L /srv/data/herdr
    test ! -L /srv/data/herdr/autostart
    if test -e /srv/data/herdr/autostart; then
        test -f /srv/data/herdr/autostart
        test -n "$(find /srv/data/herdr/autostart -type f -links 1 -print)"
        test "$(wc -c < /srv/data/herdr/autostart)" -le 2
        test "$(cat /srv/data/herdr/autostart)" = 1
    fi
}
running() {
    phone_herdr status server > /run/iphone-herdr/status.txt || return 2
    if grep -qx 'status: running' /run/iphone-herdr/status.txt; then return 0; fi
    if grep -qx 'status: not running' /run/iphone-herdr/status.txt; then return 1; fi
    return 2
}
start_session() {
    if running; then
        grep -qx 'private_protocol_compatible: yes' /run/iphone-herdr/status.txt
        echo 'HERDR_ALREADY_RUNNING'
        return
    else
        phone_herdr_status=$?
        test "$phone_herdr_status" = 1 || return "$phone_herdr_status"
    fi
    mkdir -p /run/iphone-herdr/config/herdr /run/iphone-herdr/state /srv/data
    cat > "$HERDR_CONFIG_PATH" <<'CONFIG'
[terminal]
default_shell = "/bin/bash"
[session]
resume_agents_on_restore = false
CONFIG
    export HERDR_STARTUP_CWD=/srv/data
    cd /srv/data
    (trap '' HUP; exec setsid /usr/local/bin/herdr --session iphone-server server) </dev/null >/run/iphone-herdr/start.log 2>&1 &
    for phone_herdr_attempt in 1 2 3 4 5 6 7 8 9 10; do
        printf 'Startup check %s\n' "$phone_herdr_attempt" >> /run/iphone-herdr/start.log
        if running; then
            grep -qx 'private_protocol_compatible: yes' /run/iphone-herdr/status.txt
            echo 'HERDR_STARTED'
            return
        fi
        sleep 1
    done
    echo 'Herdr startup not confirmed; inspect status before retrying.' >&2
    return 1
}
'''
LOCK = r'''
umask 077
test ! -L /run/iphone-herdr
for phone_herdr_node in /run/iphone-herdr/config /run/iphone-herdr/config/herdr /run/iphone-herdr/state; do
    test ! -L "$phone_herdr_node"
    test ! -e "$phone_herdr_node" || test -d "$phone_herdr_node"
done
for phone_herdr_node in /run/iphone-herdr/status.txt /run/iphone-herdr/start.log /run/iphone-herdr/config/herdr/config.toml; do
    test ! -L "$phone_herdr_node"
    if test -e "$phone_herdr_node"; then
        test -f "$phone_herdr_node"
        test -n "$(find "$phone_herdr_node" -type f -links 1 -print)"
    fi
done
mkdir -p /run/iphone-herdr
chmod 700 /run/iphone-herdr
mkdir /run/iphone-herdr/operation.lock || { echo 'Herdr operation already active or interrupted.' >&2; exit 1; }
trap 'rmdir /run/iphone-herdr/operation.lock' EXIT
marker_valid
'''
ACTIONS = {
    'start': 'start_session\n',
    'enable': 'start_session\nmkdir -p /srv/data/herdr\numask 077\nprintf "1\\n" > /srv/data/herdr/autostart\necho HERDR_AUTOSTART_ENABLED\n',
    'disable': 'rm -f /srv/data/herdr/autostart\necho HERDR_AUTOSTART_DISABLED\n',
    'restart': 'phone_herdr session stop iphone-server --json\nstart_session\n',
    'boot': 'if test -f /srv/data/herdr/autostart; then start_session; else echo HERDR_AUTOSTART_DISABLED; fi\n',
    'status': 'phone_herdr status server --json\n',
    'attach': 'exec /usr/local/bin/herdr --session iphone-server\n',
}


def script(action):
    if action not in ACTIONS:
        raise ValueError('Unknown Herdr action.')
    if action == 'status':
        return PREAMBLE + ACTIONS[action]
    if action == 'attach':
        return PREAMBLE + LOCK + 'start_session\nrmdir /run/iphone-herdr/operation.lock\ntrap - EXIT\n' + ACTIONS[action]
    return PREAMBLE + LOCK + ACTIONS[action]


def run(action):
    command = device_profile.ssh_options(ROOT)
    command += ['-tt' if action == 'attach' else '-T', f'root@{device_profile.PHONE}']
    if action == 'attach':
        # Inline trusted, fixed source leaves stdin available for the TUI.
        command += ['/bin/bash -c ' + shlex.quote(script(action))]
        os.execvp(command[0], command)
    else:
        command += ['/bin/bash -se']
        subprocess.run(command, input=script(action), text=True, check=True, timeout=40)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=tuple(ACTIONS), nargs='?', default='attach')
    parser.add_argument('--confirm-stop', action='store_true')
    options = parser.parse_args()
    if options.action == 'restart' and not options.confirm_stop:
        parser.error('restart closes this phone session and its processes; add --confirm-stop')
    if options.confirm_stop and options.action != 'restart':
        parser.error('--confirm-stop is only valid for restart')
    run(options.action)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
