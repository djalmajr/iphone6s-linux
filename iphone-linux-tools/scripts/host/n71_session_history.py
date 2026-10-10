"""Tie an opt-in hot continuation to private cleanup and exact kernel history."""
import json
from pathlib import Path
import re
import device_profile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def kernel_lines(text):
    return [line for line in text.splitlines()
            if re.match(r'^\[\s*\d+\.\d+\].*N71_', line)]


def read_private(directory, name):
    path = directory / name
    device_profile.protected(path)
    require(path.stat().st_size <= 2 * 1024 * 1024, 'Previous evidence exceeds budget')
    return path.read_text().split('\nSTDERR\n', 1)[0]


class History:
    def __init__(self, directory, root, release):
        directory = Path(directory).absolute()
        require(directory.parent == root / 'runtime', 'Previous session must be directly under runtime')
        device_profile.protected(directory.parent, directory=True)
        device_profile.protected(directory, directory=True)
        result = json.loads(read_private(directory, 'result-private.json'))
        require(result.get('cleanup_verified') is True and result.get('cleanup_errors') == []
                and result.get('kernel_release') == release and result.get('endpoint_id') == '43a314e4',
                'Previous endpoint/ABI/cleanup not proved')
        pcie = read_private(directory, 'pcie-cleanup-private.log')
        require('N71_PCIE_RESET_RESTORED asserted=1 readback=1' in pcie
                and 'N71_PCIE_POWER_RELEASED powered=0 attached=0' in pcie,
                'Previous reset/power cleanup missing')
        final = read_private(directory, 'reg-unload-private.log')
        require(final.startswith('N71_REG_UNLOADED\n') and
                re.findall(r'N71_REG_ON_REMOVE error=(-?\d+) restore_pending=(\d+)', final)
                and all(row == ('0', '0') for row in
                        re.findall(r'N71_REG_ON_REMOVE error=(-?\d+) restore_pending=(\d+)', final)),
                'Previous REG_ON unload not proved')
        self.lines = kernel_lines(final)
        require(self.lines and any('N71_PCIE_' in line for line in self.lines),
                'Previous timestamped diagnostic history missing')
        self.known = frozenset(self.lines)
        self.boot_id = result.get('boot_id')

    def verify_live(self, text):
        require(kernel_lines(text) == self.lines, 'Kernel diagnostic history changed or belongs to another boot')
        if self.boot_id is not None:
            require(re.findall(r'^N71_BOOT_ID ([0-9a-f-]{36})$', text, re.M) == [self.boot_id],
                    'Previous boot identity differs')

    def fresh(self, text):
        return '\n'.join(line for line in text.splitlines() if line not in self.known) + '\n'
