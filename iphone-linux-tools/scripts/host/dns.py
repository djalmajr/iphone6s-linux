#!/usr/bin/env python3
"""Explicit install and lifecycle operations for the local-only phone DNS."""
import argparse
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import uuid
import lan

ROOT = Path(__file__).resolve().parents[2]


def local_name(value):
    name = value.lower().rstrip('.')
    labels = name.split('.')
    if (not name.endswith('.home.arpa') or len(name) > 253 or
            any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                for label in labels)):
        raise argparse.ArgumentTypeError('Use um nome válido dentro de home.arpa.')
    return name


def service_ip(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError('Informe um IPv4 privado válido.') from error
    if not any(address in network for network in lan.PRIVATE):
        raise argparse.ArgumentTypeError('O registro deve apontar para IPv4 privado.')
    return str(address)


def remote(command, payload=None):
    return subprocess.run(lan.ssh_options() + [f'root@{lan.PHONE}', command],
                          input=payload, check=True, timeout=60)


def verify_bundle(manifest):
    if not manifest.is_file():
        raise ValueError('Manifesto DNS local ausente; copie o manifesto do build autenticado.')
    report = json.loads(manifest.read_text())
    archive = ROOT / 'runtime/iphone6s-dns-runtime.tar.gz'
    data = archive.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != report['bundle_bytes'] or digest != report['bundle_sha256']:
        raise ValueError('Hash/tamanho do bundle DNS inesperado; operação interrompida.')
    expected = {'srv/data/dns/runtime/bin/dnsmasq', 'srv/data/dns/runtime/COPYRIGHT',
                'srv/data/dns/runtime/provenance.json'}
    expected.update('srv/data/dns/runtime/lib/' + item['name'] for item in report['libraries'])
    with tarfile.open(archive, 'r:gz') as content:
        members = content.getmembers()
        if (len(members) != len(expected) or {item.name for item in members} != expected
                or any(not item.isfile() or item.mode & 0o7000 for item in members)):
            raise ValueError('Escopo/tipo de arquivos do bundle DNS inesperado.')
    return data, digest


def install(manifest):
    data, digest = verify_bundle(manifest)
    encoded = base64.b64encode((ROOT / 'phone/dns/manage-dns.sh').read_bytes()).decode()
    suffix = uuid.uuid4().hex
    command = f'''set -eu
base=/srv/data/dns
archive=/run/iphone-dns-install-{suffix}.tar.gz
stage=/srv/data/.iphone-dns-install-{suffix}
lock=/run/iphone-dns-install.lock
for parent in /srv /srv/data "$base"; do
    test ! -L "$parent" || {{ echo 'Symlink parent refused.' >&2; exit 1; }}
done
test ! -e "$base" || {{ echo 'DNS already has files; use start/restore, not install.' >&2; exit 1; }}
mkdir "$lock"
chmod 700 "$lock"
trap 'rm -f "$archive"; rm -rf "$stage"; rmdir "$lock"' EXIT
mkdir -p /srv/data
mkdir "$stage"
chmod 700 "$stage"
umask 077
cat > "$archive"
echo '{digest}  '"$archive" | sha256sum -c -
tar -xzf "$archive" -C "$stage"
tree=$stage/srv/data/dns
printf '%s' '{encoded}' | base64 -d > "$tree/manage-dns.sh"
chmod 755 "$tree/manage-dns.sh" "$tree" "$tree/runtime" "$tree/runtime/bin" "$tree/runtime/lib"
printf '172.16.42.1 iphone-usb.home.arpa\n' > "$tree/hosts"
chmod 644 "$tree/hosts"
printf '%s\n' '{digest}' > "$tree/bundle.sha256"
test ! -e "$base"
mv "$tree" "$base"
echo 'DNS installed in RAM; start explicitly and save a snapshot.'
'''
    remote(command, data)


def record(options):
    name, address = shlex.quote(options.name), shlex.quote(options.address)
    temporary = '/srv/data/dns/.hosts-' + uuid.uuid4().hex
    command = f'''set -eu
hosts=/srv/data/dns/hosts
test -f "$hosts" && test ! -L "$hosts"
awk 'NF && $1 !~ /^#/ && NF != 2 {{exit 1}}' "$hosts"
temporary={shlex.quote(temporary)}
trap 'rm -f "$temporary"' EXIT
awk -v name={name} '$1 ~ /^#/ || $2 != name {{print}}' "$hosts" > "$temporary"
printf '%s %s\n' {address} {name} >> "$temporary"
chmod 644 "$temporary"
mv "$temporary" "$hosts"
echo 'Record saved; restart DNS to load it and save a snapshot.'
'''
    remote(command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    installation = commands.add_parser('install')
    installation.add_argument('--manifest', type=Path, default=ROOT / 'runtime/dns-provenance.json')
    for action in ('start', 'stop', 'status'):
        commands.add_parser(action)
    configuration = commands.add_parser('record')
    configuration.add_argument('name', type=local_name)
    configuration.add_argument('address', type=service_ip)
    proxy = commands.add_parser('lan')
    proxy.add_argument('--bind', required=True, type=lan.bind_address)
    proxy.add_argument('--allow', required=True, action='append', type=lan.bind_address)
    proxy.add_argument('--port', type=lan.port, default=1053)
    proxy.add_argument('--tunnel-port', type=lan.port, default=1054)
    options = parser.parse_args()
    if options.action == 'install':
        install(options.manifest)
    elif options.action == 'record':
        record(options)
    elif options.action == 'lan':
        import dns_lan
        if options.port == options.tunnel_port:
            parser.error('Portas DNS e túnel devem ser distintas.')
        dns_lan.serve(options)
    else:
        remote('/bin/sh /srv/data/dns/manage-dns.sh ' + options.action)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
