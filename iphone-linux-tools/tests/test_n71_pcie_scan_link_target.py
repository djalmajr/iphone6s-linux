"""Compile the real temporary target/restore contract; never access a device."""
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('wrong-root', 'value != 0x1004106b', 'value != 0x1005106b'),
    ('root-check-lost', 'value != 0x1004106b', 'value == 0'),
    ('decode-check-lost', 'value & 7)', 'value & 4)'),
    ('cap-offset-widened', 'next != 0x70', 'next < 0x40'),
    ('cap-version-widened', '((value >> 16) & 0xff) != 0x42', '((value >> 16) & 0xf0) != 0x40'),
    ('training-check-lost', '(result.link_status & 0x800)', '(result.link_status & 0x800000)'),
    ('active-link-check-lost', '!(result.link_status & 0x2000)', '!(result.link_status & 0x1000)'),
    ('max-speed-widened', '(result.link_capability & 0xf) != 2', '(result.link_capability & 0xf) < 1'),
    ('supported-speed-vector-lost', '((result.link_capability2 & 0xfe) != 0 && (result.link_capability2 & 0xfe) != 6)', 'false'),
    ('fresh-capability2-lost', 'saved->link_capability2 == fresh->link_capability2', 'true'),
    ('fresh-link-status-lost', 'saved->link_status == fresh->link_status', 'true'),
    ('capture-overwrites-pending', 'out->pending || out->prepared', 'false'),
    ('fresh-snapshot-lost', 'fresh.original != 1 || !n71_link_target_same(saved, &fresh)', 'fresh.original != 1'),
    ('pending-obligation-lost', 'saved->pending = true;', 'saved->pending = false;'),
    ('wrong-write-offset', 'io->write(io->context, 0xa0, 2, 2)', 'io->write(io->context, 0xa4, 2, 2)'),
    ('adjacent-status-width', 'io->write(io->context, 0xa0, 2, 2)', 'io->write(io->context, 0xa0, 4, 2)'),
    ('wrong-target', 'io->write(io->context, 0xa0, 2, 2)', 'io->write(io->context, 0xa0, 2, 3)'),
    ('prepare-readback-lost', 'fresh.original != 2 || !n71_link_target_same(saved, &fresh)', 'false'),
    ('restore-write-skipped', 'if (fresh.original != saved->original)', 'if (fresh.original == saved->original)'),
    ('pending-never-cleared', 'saved->pending = false;', 'saved->pending = true;'),
    ('duplicate-restored-write', 'if (fresh.original != saved->original)', 'if (fresh.original)'),
)


class N71PcieScanLinkTarget(unittest.TestCase):
    def run_gate(self, mutations):
        compiler = shutil.which('cc')
        if compiler is None:
            self.skipTest('Native compiler unavailable; native gate not passed.')
        source = (ROOT / 'phone/kernel/n71-pcie-scan-link-target.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-link-target-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header = folder / 'n71-pcie-scan-link-target.h'
            binary = folder / 'target'
            for name, before, after in (('baseline', None, None),) + mutations:
                if before is not None:
                    self.assertEqual(source.count(before), 1, name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                     '-I', str(folder), str(ROOT / 'tests/n71_pcie_scan_link_target.c'),
                     '-o', str(binary)], capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, name + ': compile failure is not a kill\n' + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5,
                                        cwd=folder, env=dict(os.environ, LC_ALL='C'),
                                        preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CORE, (0, 0)))
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PCIE_SCAN_LINK_TARGET_OK', result.stdout)
                else:
                    self.assertEqual(result.returncode, -6, name + ': SIGABRT required\n' + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_LINK_TARGET_ASSERTION_KILL ' + name, flush=True)

    def test_target_word_and_restore_preserve_link_and_cleanup(self):
        self.run_gate(())

    def test_compiled_assertion_mutations(self):
        self.run_gate(MUTATIONS)


if __name__ == '__main__':
    unittest.main()
