#!/usr/bin/env python3
"""Foreground TCP forwarding through the existing trusted phone SSH link."""
import argparse
import ipaddress
import os
from pathlib import Path
import subprocess
import device_profile

ROOT = Path(__file__).resolve().parents[2]
PHONE = device_profile.PHONE
PRIVATE = tuple(ipaddress.ip_network(value) for value in
                ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def bind_address(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError('Informe um IPv4 específico do Mac.') from error
    if str(address) != '127.0.0.1' and not any(address in network for network in PRIVATE):
        raise argparse.ArgumentTypeError('Use IPv4 privado da LAN ou 127.0.0.1; wildcard/público recusado.')
    if address in ipaddress.ip_network('172.16.42.0/24'):
        raise argparse.ArgumentTypeError('Não publique na interface dedicada ao USB.')
    return str(address)


def port(value):
    number = int(value)
    if not 1024 <= number <= 65535:
        raise argparse.ArgumentTypeError('A porta deve estar entre 1024 e 65535.')
    return number


def ssh_options():
    return device_profile.ssh_options(ROOT)


def forward_command(options):
    return ssh_options() + ['-n', '-N', '-T', '-g', '-o', 'ExitOnForwardFailure=yes',
                            '-L', f'{options.bind}:{options.ssh_port}:{PHONE}:22',
                            '-L', f'{options.bind}:{options.http_port}:{PHONE}:8080',
                            f'root@{PHONE}']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind', required=True, type=bind_address)
    parser.add_argument('--ssh-port', type=port, default=2222)
    parser.add_argument('--http-port', type=port, default=8086)
    options = parser.parse_args()
    if options.ssh_port == options.http_port:
        parser.error('As portas SSH e HTTP devem ser distintas.')
    profile = device_profile.load(ROOT)
    if not profile['client_key'].is_file() or not profile['known_hosts'].is_file():
        raise SystemExit('Identidade SSH dedicada ausente; nenhum encaminhamento iniciado.')
    subprocess.run(ssh_options() + ['-n', f'root@{PHONE}', 'true'], check=True, timeout=15)
    print(f'SSH do iPhone: {options.bind}:{options.ssh_port}; chave do cliente ainda obrigatória.', flush=True)
    print(f'HTTP de diagnóstico sem autenticação: http://{options.bind}:{options.http_port}/cgi-bin/status', flush=True)
    print('Iniciando listeners; encerrá-los com Ctrl+C. Sem NAT, saída internet ou mudança de DNS.', flush=True)
    command = forward_command(options)
    os.execvp(command[0], command)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
