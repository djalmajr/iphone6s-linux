"""Selected session guards must fail assertions when weakened, without SSH."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71-link-session.py'
MUTATIONS = {
    'host-selection': ("'n71-pcie-controls-scan-build.json'", "'n71-pcie-bridge-scan-build.json'"),
    'cycle-mode': ("parameters += ' dart_cycle=1'", "parameters += ''"),
    'cycle-cleanup': ('n71_dart_cycle_result.cleanup(p.stdout)', 'pass'),
    'private-ttbr-output': ("and 'N71_DART_TTBR ' not in line", ''),
    'original-latch': ("'N71_REG_ON_OBSERVED control=80 bit0=0 compatible-plan=1' in p.stdout",
                       "'N71_REG_ON_OBSERVED' in p.stdout"),
    'fresh-control': ("and 'N71_REG_ON_CONTROL_READBACK value=81' in p.stdout,", 'and True,'),
    'restore-pending': ('require(p.returncode == 0 and (absent or restored),', 'require(p.returncode == 0,'),
    'cleanup-finally': ('            self.cleanup()', "            self.result['cleanup_verified'] = True"),
    'read-budget': ("require(0 <= int(reads) <= 10000, 'Link read budget exceeded')",
                    "require(True, 'Link read budget exceeded')"),
    'endpoint-validity': ("and identities[0] not in ('00000000', 'ffffffff'),", 'and True,'),
    'link-predicate': ('require(int(status, 16) & 1 and len(identities) == 1', 'require(len(identities) == 1'),
    'inventory-budget': ('1 <= int(reads) <= 63', '1 <= int(reads) <= 64'),
    'inventory-master': ('not (int(command, 16) & 4)', 'True'),
    'inventory-bars': ('[int(index) for index, _ in bars] == list(range(6))', 'len(bars) == 6'),
    'inventory-mode': ("' config_inventory=1' if self.config_inventory else ''", "''"),
    'inventory-selection': ("if record['module'] == 'n71-pcie-diagnostic.ko' else record for record in records]",
                            'if False else record for record in records]'),
}


def main():
    text = SOURCE.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-link-session-mutations-') as directory:
        folder = Path(directory)
        for name, (before, after) in MUTATIONS.items():
            if text.count(before) != 1:
                raise SystemExit('Mutation anchor differs: ' + name)
            mutated = folder / (name + '.py')
            mutated.write_text(text.replace(before, after))
            environment = dict(os.environ, N71_LINK_SESSION_SCRIPT=str(mutated), PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                      '-p', 'test_n71_link_session.py'], env=environment,
                                     capture_output=True, text=True, timeout=30)
            output = process.stdout + process.stderr
            if process.returncode == 0 or 'AssertionError' not in output or 'ERROR:' in output:
                raise SystemExit('Mutation not killed by assertion: ' + name)
            print('N71_LINK_SESSION_MUTATION_KILLED', name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
