"""Require assertion failures for scan evidence acceptance regressions."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('ignored-scan-error', "result['error'] == 0 and result['devices'] == 2", "result['error'] <= 0 and result['devices'] == 2"),
    ('bus-master-allowed', 'not (int(row[4], 16) & 4)', 'not (int(row[4], 16) & 8)'),
    ('bars-reordered', '[int(row[0]) for row in bars] == list(range(6))', 'len(bars) == 6'),
    ('failed-restore-allowed', "removed == ['1'] and restored == ['0']", "removed == ['1']"),
    ('failed-removal-allowed', "removed == ['1'] and restored == ['0']", "restored == ['0']"),
    ('non-power-of-two', 'size & (size - 1) == 0', 'size >= 0'),
    ('io-bar-allowed', 'flags & 0x700 == 0x200', 'flags & 0x700 in (0x100, 0x200)'),
    ('missing-scan-allowed', 'any(int(error) < 0 for error in earlier)', 'True'),
)


def main():
    source = (ROOT / 'scripts/host/n71_scan_result.py').read_text()
    with tempfile.TemporaryDirectory(prefix='n71-scan-result-mutations-') as directory:
        for name, before, after in MUTATIONS:
            if source.count(before) != 1:
                raise ValueError('Mutation anchor is not unique: ' + name)
            path = Path(directory) / (name + '.py')
            path.write_text(source.replace(before, after, 1))
            result = subprocess.run(
                [sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                 '-p', 'test_n71_scan_result.py'], capture_output=True, text=True, timeout=30,
                env=dict(os.environ, N71_SCAN_RESULT_SCRIPT=str(path), PYTHONDONTWRITEBYTECODE='1'))
            output = result.stdout + result.stderr
            if result.returncode == 0 or 'AssertionError' not in output or 'ERROR:' in output:
                raise RuntimeError('Mutation not killed by assertion: ' + name + output)
            print('N71_SCAN_RESULT_ASSERTION_KILL ' + name)
    print('N71_SCAN_RESULT_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
