#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PHONE_IP=172.16.42.1
HOST_IP=172.16.42.2
GUIDE_PID=
GUIDE_STATE_DIR=
CLIENT_KEY="$ROOT/keys/iphone_ed25519"
PROFILE_EXPLICIT=0
SSH_ARGS=(-F /dev/null -i "$ROOT/keys/iphone_ed25519" -o "UserKnownHostsFile=$ROOT/keys/known_hosts" -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3)

if [ "${IPHONE_LINUX_PROFILE+x}" = x ]; then
    PROFILE_EXPLICIT=1
    fields=$(python3 "$ROOT/scripts/host/device_profile.py" fields)
    PROFILE_FIELDS=()
    while IFS= read -r field; do PROFILE_FIELDS+=("$field"); done <<< "$fields"
    if [ "${#PROFILE_FIELDS[@]}" -ne 5 ]; then
        printf 'Campos de perfil incompletos; nenhuma ação iniciada.\n' >&2
        exit 1
    fi
    CLIENT_KEY="${PROFILE_FIELDS[0]}"
    PROFILE_PAYLOAD="${PROFILE_FIELDS[3]}"
    PROFILE_DIGEST="${PROFILE_FIELDS[4]}"
    SSH_ARGS=(-4 -F /dev/null -a -i "$CLIENT_KEY" -o "UserKnownHostsFile=${PROFILE_FIELDS[1]}" -o "HostKeyAlias=${PROFILE_FIELDS[2]}" -o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 -o ForwardAgent=no -o ForwardX11=no -o ControlMaster=no -o ControlPath=none)
    case "${1:-status}" in
        boot-probe|install-terminal)
            printf 'Perfil explícito exige imagem integrada; comando incompatível recusado.\n' >&2
            exit 1
            ;;
    esac
fi

ssh_ready() {
    [ -f "$CLIENT_KEY" ] && ssh -n "${SSH_ARGS[@]}" "root@$PHONE_IP" true 2>/dev/null
}

usb_interface() {
    python3 - <<'PY'
import plistlib
import subprocess

data = subprocess.check_output(["ioreg", "-r", "-n", "iPhone 6s Linux probe", "-a"])
if not data.strip():
    raise SystemExit("O dispositivo USB do Linux ainda não foi detectado.")
names = set()
def visit(value):
    if isinstance(value, dict):
        name = value.get("IORegistryEntryName", "")
        if value.get("IOObjectClass") == "IOEthernetInterface" and isinstance(name, str) and name.startswith("en") and name[2:].isdigit():
            names.add(name)
        for child in value.values():
            visit(child)
    elif isinstance(value, list):
        for child in value:
            visit(child)
visit(plistlib.loads(data))
if len(names) != 1:
    raise SystemExit("Não foi encontrada uma única interface USB do Linux do iPhone.")
print(names.pop())
PY
}

remote() {
    if ssh_ready; then
        ssh "${SSH_ARGS[@]}" "root@$PHONE_IP" '/bin/bash -se'
    else
        if [ "$PROFILE_EXPLICIT" -eq 1 ]; then
            printf 'SSH do perfil não confirmado; terminal de recuperação não será usado.\n' >&2
            return 1
        fi
        python3 "$ROOT/scripts/host/usb-shell.py" --script
    fi
}

install_terminal() {
    connect
    mkdir -p "$ROOT/logs"
    chmod 700 "$ROOT/logs"
    local digest transfer_pid
    digest=$(python3 - "$ROOT/runtime" <<'PY'
import hashlib,pathlib,sys
root=pathlib.Path(sys.argv[1]); archive=root/'iphone6s-runtime.tar.gz'
expected=(root/'SHA256SUMS').read_text().split()[0]
if hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
    raise SystemExit('Hash do runtime inesperado; instalação interrompida.')
print(expected)
PY
)
    if curl --silent --max-time 1 "http://$HOST_IP:8766/" >/dev/null 2>&1; then
        printf 'A porta USB 8766 já está em uso; encerre o servidor de transferência anterior.\n' >&2
        return 1
    fi
    python3 -m http.server 8766 --bind "$HOST_IP" --directory "$ROOT/runtime" > "$ROOT/logs/transfer.log" 2>&1 &
    transfer_pid=$!
    sleep 1
    local result=0
    {
        printf 'set -e\n'
        printf 'wget -O /tmp/iphone6s-runtime.tar.gz http://172.16.42.2:8766/iphone6s-runtime.tar.gz\n'
        printf 'echo "%s  /tmp/iphone6s-runtime.tar.gz" | sha256sum -c -\n' "$digest"
        printf 'tar -xzf /tmp/iphone6s-runtime.tar.gz -C /\nrm /tmp/iphone6s-runtime.tar.gz\n'
        printf '/usr/local/sbin/start-terminal\n'
    } | remote > "$ROOT/logs/install-last.log" 2>&1 || result=$?
    kill -TERM "$transfer_pid" 2>/dev/null || true
    wait "$transfer_pid" 2>/dev/null || true
    if [ "$result" -ne 0 ]; then cat "$ROOT/logs/install-last.log"; return "$result"; fi
    if ! ssh_ready; then printf 'SSH não confirmado; o terminal de recuperação foi mantido.\n' >&2; return 1; fi
    ssh "${SSH_ARGS[@]}" "root@$PHONE_IP" 'for pid in $(pidof telnetd); do kill "$pid"; done'
    printf 'Bash, SSH por chave e Herdr disponíveis. Terminal de teste sem senha encerrado.\n'
}

connect() {
    local iface
    iface=$(usb_interface)
    if ! /sbin/ifconfig "$iface" | grep -q "inet $HOST_IP "; then
        printf 'O macOS solicitará autenticação para configurar somente %s.\n' "$iface"
        /usr/bin/osascript -e "do shell script \"/sbin/ifconfig $iface inet $HOST_IP netmask 255.255.255.0 alias\" with administrator privileges"
    fi
    printf 'USB: Mac %s → iPhone %s (%s).\n' "$HOST_IP" "$PHONE_IP" "$iface"
}

status() {
    connect
    printf 'uname -a\ntr -d "\\000" < /proc/device-tree/model\necho\nuptime\nfree -m\n' | remote
}

serve() {
    connect
    if [ "$PROFILE_EXPLICIT" -eq 1 ] && ! ssh_ready; then
        printf 'SSH do perfil não confirmado; HTTP não comprova a identidade do servidor.\n' >&2
        return 1
    fi
    if curl --fail --silent --max-time 2 "http://$PHONE_IP:8080/cgi-bin/status" >/dev/null 2>&1; then
        printf 'Painel: http://%s:8080/cgi-bin/status\n' "$PHONE_IP"
        return
    fi
    local encoded
    mkdir -p "$ROOT/logs"
    chmod 700 "$ROOT/logs"
    encoded=$(base64 -i "$ROOT/phone/http/status" | fold -w 76)
    {
        printf 'mkdir -p /srv/iphone/cgi-bin\n'
        printf "base64 -d > /srv/iphone/cgi-bin/status <<'IPHONE_FILE'\n%s\nIPHONE_FILE\n" "$encoded"
        printf 'chmod 755 /srv/iphone/cgi-bin/status\n'
        printf "printf '%%s' '<!doctype html><meta http-equiv=\"refresh\" content=\"0;url=/cgi-bin/status\">' > /srv/iphone/index.html\n"
        # Expand these expressions on the phone, not on the Mac.
        # shellcheck disable=SC2016
        printf 'if [ ! -f /run/iphone-http.pid ] || ! kill -0 "$(cat /run/iphone-http.pid)" 2>/dev/null; then httpd -f -p 172.16.42.1:8080 -h /srv/iphone </dev/null >/run/iphone-http.log 2>&1 & echo $! > /run/iphone-http.pid; fi\n'
    } | remote > "$ROOT/logs/server-last.log"
    curl --fail --silent --show-error --max-time 10 "http://$PHONE_IP:8080/cgi-bin/status" > /dev/null
    printf '\nPainel: http://%s:8080/cgi-bin/status\n' "$PHONE_IP"
}

cleanup_guide() {
    if [ -n "$GUIDE_PID" ]; then
        kill -TERM "$GUIDE_PID" 2>/dev/null || true
        wait "$GUIDE_PID" 2>/dev/null || true
        GUIDE_PID=
    fi
    if [ -n "$GUIDE_STATE_DIR" ]; then
        rm -f "$GUIDE_STATE_DIR/state.json" "$GUIDE_STATE_DIR/state.tmp"
        rmdir "$GUIDE_STATE_DIR"
        GUIDE_STATE_DIR=
    fi
}

wait_for_pongo() {
    trap cleanup_guide EXIT INT TERM
    mkdir -p "$ROOT/runtime"
    mkdir -p "$ROOT/logs"
    chmod 700 "$ROOT/logs"
    if ! mkdir "$ROOT/runtime/dfu-active"; then
        printf 'Existe um monitor DFU ativo ou interrompido; confira runtime/dfu-active antes de repetir.\n' >&2
        return 1
    fi
    GUIDE_STATE_DIR="$ROOT/runtime/dfu-active"
    python3 "$ROOT/scripts/boot/dfu_boot.py" "$GUIDE_STATE_DIR/state.json" > "$ROOT/logs/dfu-last.log" 2>&1 &
    GUIDE_PID=$!
    printf 'Use USB-A → Lightning e entre em DFU manualmente quando aparecer cabo/computador.\n'
    printf 'Aguardando detecção USB; nenhuma página ou contagem será aberta.\n'
    local ready=0 phase
    for ((i=0; i<240; i++)); do
        if ioreg -p IOUSB -w0 | grep -q 'PongoOS USB Device'; then ready=1; break; fi
        if ! kill -0 "$GUIDE_PID" 2>/dev/null; then
            printf 'O monitor DFU encerrou. Nenhum payload Linux foi enviado.\n' >&2
            return 1
        fi
        if [ ! -f "$GUIDE_STATE_DIR/state.json" ]; then sleep 1; continue; fi
        if ! phase=$(python3 - "$GUIDE_STATE_DIR/state.json" <<'PY'
import json
import pathlib
import sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())['phase'])
PY
        ); then
            printf 'Estado DFU inválido. Nenhum payload Linux foi enviado.\n' >&2
            return 1
        fi
        case "$phase" in
            failed|retry|exited)
                printf 'Falha na etapa DFU/exploração USB. Nenhum payload Linux foi enviado.\n' >&2
                return 1
                ;;
        esac
        sleep 1
    done
    if [ "$ready" -ne 1 ]; then
        printf 'PongoOS não foi detectado. Nenhum payload Linux foi enviado.\n' >&2
        return 1
    fi
    cleanup_guide
    trap - EXIT INT TERM
}

boot() {
    local image="${1:-server}" restore_id="${2:-}" payload digest
    python3 "$ROOT/scripts/boot/pongo_select.py" > /dev/null
    if [ "$PROFILE_EXPLICIT" -eq 1 ]; then
        python3 "$ROOT/scripts/host/device_profile.py" check
    fi
    if [ -n "$restore_id" ]; then
        python3 "$ROOT/scripts/host/persist.py" verify "$restore_id"
    fi
    if [ "$PROFILE_EXPLICIT" -eq 1 ]; then
        payload="$PROFILE_PAYLOAD"
        digest="$PROFILE_DIGEST"
    elif [ "$image" = probe ]; then
        payload="$ROOT/artifacts/m1n1-linux-iphone6s.bin"
        digest=7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520
    else
        payload="$ROOT/artifacts/m1n1-linux-iphone6s-loopback-server.bin"
        digest=8b1a46dd67613c63aa6608dd3a0e73a73b358aaddc1818b423ff6009b55e3f66
    fi
    if ioreg -p IOUSB -w0 | grep -q 'iPhone 6s Linux probe'; then
        if [ "${IPHONE_LINUX_PONGO+x}" = x ]; then
            printf 'Pongo explícito exige novo boot; Linux já está ativo.\n' >&2
            return 1
        fi
        if [ -n "$restore_id" ]; then
            printf 'Restauração automática exige um novo boot; Linux já está ativo.\n' >&2
            return 1
        fi
        connect
        if ! ssh_ready; then
            if [ "$image" = probe ]; then install_terminal; else
                printf 'SSH da imagem integrada não foi confirmado.\n' >&2
                return 1
            fi
        fi
        serve
        return
    fi
    if [ "${IPHONE_LINUX_PONGO+x}" = x ] && ioreg -p IOUSB -w0 | grep -q 'PongoOS USB Device'; then
        printf 'Pongo já ativo não comprova a candidata selecionada; volte ao iOS e repita DFU.\n' >&2
        return 1
    fi
    python3 "$ROOT/scripts/boot/boot_tools.py" palera1n-macos-arm64 pongoterm
    python3 - "$payload" "$digest" <<'PY'
import hashlib
import pathlib
import sys
path = pathlib.Path(sys.argv[1])
if hashlib.sha256(path.read_bytes()).hexdigest() != sys.argv[2]:
    raise SystemExit(f"Hash inesperado: {path.name}. Boot interrompido.")
PY
    if ! ioreg -p IOUSB -w0 | grep -q 'PongoOS USB Device'; then
        wait_for_pongo
    else
        printf 'PongoOS já detectado; continuando o boot sem repetir DFU.\n'
    fi
    printf '/send %s\nbootm\n' "$payload" | "$ROOT/bin/pongoterm" &
    local transfer_pid=$!
    local ready=0
    for ((i=0; i<120; i++)); do
        if usb_interface >/dev/null 2>&1; then ready=1; break; fi
        sleep 1
    done
    kill -TERM "$transfer_pid" 2>/dev/null || true
    wait "$transfer_pid" 2>/dev/null || true
    if [ "$ready" -ne 1 ]; then
        printf 'A interface USB do Linux não apareceu. Boot ainda não confirmado.\n' >&2
        return 1
    fi
    connect
    if [ "$image" = probe ]; then
        install_terminal
    else
        for ((i=0; i<15; i++)); do
            if ssh_ready; then break; fi
            sleep 1
        done
        if ! ssh_ready; then
            printf 'Linux USB detectado, mas SSH integrado não confirmado.\n' >&2
            return 1
        fi
    fi
    if [ -n "$restore_id" ]; then
        python3 "$ROOT/scripts/host/persist.py" restore "$restore_id"
    fi
    serve
}

case "${1:-status}" in
    boot)
        if [ "$#" -eq 1 ]; then boot
        elif [ "$#" -eq 3 ] && [ "$2" = --restore ]; then boot server "$3"
        else printf 'Uso: %s boot [--restore ID]\n' "$0" >&2; exit 2; fi
        ;;
    autosnap) shift; exec python3 "$ROOT/scripts/host/autosnap.py" "$@" ;;
    lan) shift; exec python3 "$ROOT/scripts/host/lan.py" "$@" ;;
    dns) shift; exec python3 "$ROOT/scripts/host/dns.py" "$@" ;;
    boot-probe) boot probe ;;
    backup|restore) connect; exec python3 "$ROOT/scripts/host/persist.py" "$@" ;;
    backups) exec python3 "$ROOT/scripts/host/persist.py" "$@" ;;
    connect) connect ;;
    status) status ;;
    serve) serve ;;
    install-terminal) install_terminal ;;
    shell) connect; exec ssh -t "${SSH_ARGS[@]}" "root@$PHONE_IP" ;;
    console) connect; exec ssh -tt "${SSH_ARGS[@]}" "root@$PHONE_IP" '/usr/local/sbin/start-console && TERM=linux /usr/bin/script --quiet --flush --return --command "/bin/bash -i" /dev/tty1' ;;
    herdr) connect; exec ssh -tt "${SSH_ARGS[@]}" "root@$PHONE_IP" 'TERM=xterm-256color herdr --session iphone-linux' ;;
    disconnect)
        iface=$(usb_interface)
        /usr/bin/osascript -e "do shell script \"/sbin/ifconfig $iface inet $HOST_IP -alias\" with administrator privileges"
        ;;
    *) printf 'Uso: %s {boot [--restore ID]|boot-probe|autosnap {once|watch|status}|lan --bind IP [--ssh-port PORT] [--http-port PORT]|dns {install|start|stop|status|record NAME IP|lan --bind IP --allow IP [--port PORT] [--tunnel-port PORT]}|backup|restore [ID]|backups|connect|status|serve|install-terminal|shell|console|herdr|disconnect}\n' "$0" >&2; exit 2 ;;
esac
