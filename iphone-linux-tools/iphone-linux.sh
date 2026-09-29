#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
PHONE_IP=172.16.42.1
HOST_IP=172.16.42.2
GUIDE_PID=
SSH_ARGS=(-F /dev/null -i "$ROOT/keys/iphone_ed25519" -o "UserKnownHostsFile=$ROOT/keys/known_hosts" -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 -o ServerAliveInterval=5 -o ServerAliveCountMax=3)

ssh_ready() {
    [ -f "$ROOT/keys/iphone_ed25519" ] && ssh -n "${SSH_ARGS[@]}" "root@$PHONE_IP" true 2>/dev/null
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
        python3 "$ROOT/usb-shell.py" --script
    fi
}

install_terminal() {
    connect
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
    python3 -m http.server 8766 --bind "$HOST_IP" --directory "$ROOT/runtime" > "$ROOT/runtime/transfer.log" 2>&1 &
    transfer_pid=$!
    sleep 1
    local result=0
    {
        printf 'set -e\n'
        printf 'wget -O /tmp/iphone6s-runtime.tar.gz http://172.16.42.2:8766/iphone6s-runtime.tar.gz\n'
        printf 'echo "%s  /tmp/iphone6s-runtime.tar.gz" | sha256sum -c -\n' "$digest"
        printf 'tar -xzf /tmp/iphone6s-runtime.tar.gz -C /\nrm /tmp/iphone6s-runtime.tar.gz\n'
        printf '/usr/local/sbin/start-terminal\n'
    } | remote > "$ROOT/runtime/install-last.log" 2>&1 || result=$?
    kill -TERM "$transfer_pid" 2>/dev/null || true
    wait "$transfer_pid" 2>/dev/null || true
    if [ "$result" -ne 0 ]; then cat "$ROOT/runtime/install-last.log"; return "$result"; fi
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
    if curl --fail --silent --max-time 2 "http://$PHONE_IP:8080/cgi-bin/status" >/dev/null 2>&1; then
        printf 'Painel: http://%s:8080/cgi-bin/status\n' "$PHONE_IP"
        return
    fi
    local encoded
    encoded=$(base64 -i "$ROOT/server/status" | fold -w 76)
    {
        printf 'mkdir -p /srv/iphone/cgi-bin\n'
        printf "base64 -d > /srv/iphone/cgi-bin/status <<'IPHONE_FILE'\n%s\nIPHONE_FILE\n" "$encoded"
        printf 'chmod 755 /srv/iphone/cgi-bin/status\n'
        printf "printf '%%s' '<!doctype html><meta http-equiv=\"refresh\" content=\"0;url=/cgi-bin/status\">' > /srv/iphone/index.html\n"
        printf 'if [ ! -f /run/iphone-http.pid ] || ! kill -0 "$(cat /run/iphone-http.pid)" 2>/dev/null; then httpd -f -p 172.16.42.1:8080 -h /srv/iphone </dev/null >/run/iphone-http.log 2>&1 & echo $! > /run/iphone-http.pid; fi\n'
    } | remote > "$ROOT/server-last.log"
    curl --fail --silent --show-error --max-time 10 "http://$PHONE_IP:8080/cgi-bin/status" > /dev/null
    printf '\nPainel: http://%s:8080/cgi-bin/status\n' "$PHONE_IP"
}

cleanup_guide() {
    if [ -n "$GUIDE_PID" ]; then
        kill -TERM "$GUIDE_PID" 2>/dev/null || true
        wait "$GUIDE_PID" 2>/dev/null || true
        GUIDE_PID=
    fi
}

boot() {
    local image="${1:-server}" payload digest
    if [ "$image" = probe ]; then
        payload="$ROOT/m1n1-linux-iphone6s.bin"
        digest=7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520
    else
        payload="$ROOT/m1n1-linux-iphone6s-console-server.bin"
        digest=c49e03822e164767424d1ac786c3b00eec731de66acec497915c2cc83a39ee4a
    fi
    if ioreg -p IOUSB -w0 | grep -q 'iPhone 6s Linux probe'; then
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
    python3 - "$ROOT/palera1n-macos-arm64" "$payload" "$digest" <<'PY'
import hashlib
import pathlib
import sys
expected = ["950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9", sys.argv[3]]
for name, digest in zip(sys.argv[1:3], expected):
    path = pathlib.Path(name)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"Hash inesperado: {path.name}. Boot interrompido.")
PY
    if curl --fail --silent --max-time 1 http://127.0.0.1:8765/state >/dev/null 2>&1; then
        printf 'Já existe um guia na porta 8765. Encerre esse guia antes de iniciar outro.\n' >&2
        return 1
    fi
    trap cleanup_guide EXIT INT TERM
    python3 "$ROOT/dfu_visual.py" > "$ROOT/dfu-last.log" 2>&1 &
    GUIDE_PID=$!
    for ((i=0; i<20; i++)); do
        if curl --fail --silent --max-time 1 http://127.0.0.1:8765/state >/dev/null 2>&1; then break; fi
        if ! kill -0 "$GUIDE_PID" 2>/dev/null; then cat "$ROOT/dfu-last.log"; return 1; fi
        sleep 1
    done
    open http://127.0.0.1:8765
    printf 'Use o cabo USB-A → Lightning. Siga a contagem visual e mantenha o cabo conectado.\n'
    local ready=0
    for ((i=0; i<240; i++)); do
        if ioreg -p IOUSB -w0 | grep -q 'PongoOS USB Device'; then ready=1; break; fi
        sleep 1
    done
    if [ "$ready" -ne 1 ]; then
        printf 'PongoOS não foi detectado. Nenhum payload Linux foi enviado.\n' >&2
        return 1
    fi
    curl --fail --silent http://127.0.0.1:8765/state > "$ROOT/dfu-last-state.json"
    cleanup_guide
    trap - EXIT INT TERM
    printf '/send %s\nbootm\n' "$payload" | "$ROOT/pongoterm" &
    local transfer_pid=$!
    ready=0
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
    serve
}

case "${1:-status}" in
    boot) boot ;;
    boot-probe) boot probe ;;
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
    *) printf 'Uso: %s {boot|boot-probe|connect|status|serve|install-terminal|shell|console|herdr|disconnect}\n' "$0" >&2; exit 2 ;;
esac
