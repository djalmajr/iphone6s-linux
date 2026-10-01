#!/usr/bin/env python3
"""Save a verified snapshot, request kernel reboot and verify USB iOS return."""
import argparse
import os
from pathlib import Path
import plistlib
import re
import signal
import subprocess
import sys
import tarfile
import time
import autosnap
import device_profile
import persist

ROOT = Path(__file__).resolve().parents[2]
SYNC_MARKER = 'IPHONE_SYNC_COMPLETE'


def run_owned(command, timeout):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output, False
    except subprocess.TimeoutExpired:
        output, _ = autosnap.stop_job(process)
        return process.returncode, output, True
    except BaseException:
        autosnap.stop_job(process)
        raise


def usb_devices(timeout):
    code, output, expired = run_owned(['idevice_id', '-l'], timeout)
    if code or expired:
        raise ValueError('Enumeração USB indisponível.')
    devices = output.splitlines()
    if any(not re.fullmatch('[A-Za-z0-9-]{1,128}', value) for value in devices):
        raise ValueError('Enumeração USB inválida.')
    return devices


def linux_present(timeout):
    code, output, expired = run_owned(['ioreg', '-r', '-n', 'iPhone 6s Linux probe', '-a'], timeout)
    if code or expired:
        raise ValueError('Enumeração do gadget indisponível.')
    if not output.strip():
        return False
    value = plistlib.loads(output.encode())
    if not isinstance(value, list):
        raise ValueError('Enumeração do gadget inválida.')
    return bool(value)


def observe_ios(wait):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        def budget():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError('Prazo de confirmação expirado.')
            return min(5, remaining)
        try:
            if not linux_present(budget()):
                devices = usb_devices(budget())
                if len(devices) == 1:
                    code, model, expired = run_owned(
                        ['ideviceinfo', '-u', devices[0], '-k', 'ProductType'], budget())
                    if (code == 0 and not expired and model.strip() == 'iPhone8,1'
                            and not linux_present(budget())):
                        return
        except (ValueError, plistlib.InvalidFileException):
            pass
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    raise ValueError('Retorno ao iOS não confirmado; preserve o snapshot e use o fallback manual.')


def return_ios(wait):
    ssh = device_profile.ssh_options(ROOT) + [f'root@{device_profile.PHONE}']
    if usb_devices(5):
        raise ValueError('Há iOS USB enumerado antes do pedido; nenhuma ação iniciada.')
    code, output, expired = run_owned(ssh + ['test -r /proc/uptime && echo IPHONE_LINUX_READY'], 10)
    if code or expired or output.strip() != 'IPHONE_LINUX_READY':
        raise ValueError('SSH Linux não confirmado; nenhuma ação de reboot iniciada.')
    code, output, expired = run_owned(
        [sys.executable, str(ROOT / 'scripts/host/persist.py'), 'backup'], 180)
    match = re.fullmatch(r'Snapshot: (\d{8}T\d{6}Z-[a-f0-9]{8})\s*', output)
    if code or expired or not match:
        raise ValueError('Backup não concluído; reboot bloqueado.')
    with persist.snapshot_lock.lock(persist.STORE):
        persist.load_snapshot(match.group(1))
    print('BACKUP_VERIFIED', flush=True)
    command = f"set -e; sync; echo {SYNC_MARKER}"
    code, output, expired = run_owned(ssh + [command], 15)
    if code != 0 or expired or output.strip() != SYNC_MARKER:
        raise ValueError('Sync não confirmado; reboot bloqueado, snapshot preservado.')
    print('SYNC_VERIFIED', flush=True)
    code, _, expired = run_owned(ssh + ['/bin/busybox reboot -f'], 15)
    if not expired and code not in (0, 255):
        raise ValueError('Pedido de reboot recusado; snapshot preservado.')
    observe_ios(wait)
    print('RETURN_IOS_VERIFIED: iPhone8,1 USB; Linux gadget absent')


def wait_seconds(value):
    number = int(value)
    if not 1 <= number <= 300:
        raise argparse.ArgumentTypeError('Use --wait entre 1 e 300 segundos.')
    return number


def cancelled(_signal, _frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', type=wait_seconds, default=90)
    options = parser.parse_args()
    os.umask(0o077)
    signal.signal(signal.SIGTERM, cancelled)
    try:
        return_ios(options.wait)
        return 0
    except ValueError as error:
        print('RETURN_IOS_FAILED: ' + str(error), file=sys.stderr)
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException, tarfile.TarError):
        print('RETURN_IOS_FAILED: dependência/enumeração indisponível.', file=sys.stderr)
    except KeyboardInterrupt:
        print('RETURN_IOS_FAILED: cancelado; snapshot concluído preservado.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
