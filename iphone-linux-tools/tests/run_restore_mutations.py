#!/usr/bin/env python3
"""Reject restore regressions using disposable copies in the dedicated VM."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

if not (sys.platform == 'linux' and os.geteuid() == 0
        and os.environ.get('IPHONE_RESTORE_VM_TESTS') == '1'):
    raise SystemExit('Requires explicit disposable Linux VM/root opt-in.')

source = Path(__file__).resolve().parents[1]
mutations = [
    ('missing-pre-upload-journal', 'restore_journal.py',
     '    write(store, record)\n    return record', '    return record', '88'),
    ('ignored-remote-errors', 'persist.py',
     'check=True, **kwargs', 'check=False, **kwargs', 'CalledProcessError not raised'),
]
for label, filename, original, changed, expected in mutations:
    with tempfile.TemporaryDirectory(prefix='iphone-restore-mutation-') as temporary:
        target = Path(temporary) / 'project'
        shutil.copytree(source / 'scripts/host', target / 'scripts/host',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (target / 'tests').mkdir()
        shutil.copy(source / 'tests/test_restore_failure_vm.py', target / 'tests')
        path = target / 'scripts/host' / filename
        content = path.read_text()
        if content.count(original) != 1:
            raise SystemExit('Mutation anchor changed: ' + label)
        path.write_text(content.replace(original, changed))
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                                 '-s', str(target / 'tests'), '-p', 'test_restore_failure_vm.py', '-v'],
                                capture_output=True, text=True)
        output = result.stdout + result.stderr
        print(label, 'exit=' + str(result.returncode))
        print('\n'.join(output.splitlines()[-6:]))
        if result.returncode == 0 or expected not in output:
            raise SystemExit('Mutation survived or failed for another reason: ' + label + '\n' + output)
print('Both mutations rejected; disposable copies removed.')
