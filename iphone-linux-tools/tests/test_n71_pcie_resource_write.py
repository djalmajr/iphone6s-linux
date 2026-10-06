"""Compile the allocation policy and require assertion evidence for mutations."""
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = (
    ('overwrite-capture', 'if (out->pending || out->active)', 'if (false)'),
    ('capture-wrong-layout', 'index == 0 ? 0x8000U : index == 2 ?', 'index == 0 ? 0x4000U : index == 2 ?'),
    ('capture-wrong-bar', 'index == 0 || index == 2 ? 4U : 0U', 'index == 0 ? 4U : 0U'),
    ('capture-extra-lost', '&result.extra[index]);', '&result.reference.saved[0].rom);'),
    ('capture-before-final-read', 'if (error)\n\t\t\treturn error;\n\t}\n\tresult.active',
     'if (error) { *out = result; return error; }\n\t}\n\tresult.active'),
    ('bar-wrong-type', '(value & 0xf) == 4 &&', '((value & 0xf) == 4 || (value & 0xf) == 5) &&'),
    ('bar-range-boundary', 'address >= 0xc0000000U', 'address > 0xc0000000U'),
    ('bar-alignment-lost', '!(address & (bytes - 1))', '!(address & 0U)'),
    ('mem-reserved-bits', '!(request->value & 0x000f000fU)', '!(request->value & 0U)'),
    ('mem-reversed-window', 'base <= limit', 'base >= limit'),
    ('pref-window-enabled', 'return request->value == 0x0000fff0;',
     'return request->value == 0x0000fff0 || request->value == 0xc080c000;'),
    ('bar-upper-enabled', 'case 0x24:\n\t\t\treturn request->value == 0;',
     'case 0x24:\n\t\t\treturn request->value <= 4;'),
    ('status-width', '\tu32 base, limit;\n',
     '\tu32 base, limit;\n\tif (request->root && request->where == 0x1c && request->size == 4) return true;\n'),
    ('command-width', 'request->where == 4 && request->size == 2',
     'request->where == 4 && (request->size == 2 || request->size == 4)'),
    ('inactive-write', 'if (!state->active || !state->pending)', 'if (false)'),
    ('lost-first-error', 'if (state->error)\n\t\treturn state->error;',
     'if (state->error == -E2BIG)\n\t\treturn state->error;'),
    ('budget-boundary', '> N71_RESOURCE_MAX_ATTEMPTS', '>= N71_RESOURCE_MAX_ATTEMPTS'),
    ('decode-enabled', 'if (command & 7)', 'if (command & 4)'),
    ('endpoint-not-guarded', 'for (function = 0; function < 2; function++)',
     'for (function = 0; function < 1; function++)'),
    ('write-readback-lost',
     'error = n71_resource_write_value(io, state, request, observed);',
     'error = io->write(io->context, request->root, request->where, request->size, request->value);'),
    ('failure-before-lost', '.before = before', '.before = before ^ 1U'),
    ('failure-request-root', 'state->failure = failure;',
     'failure.request.root = !request->root; state->failure = failure;'),
    ('failure-after-lost', 'failure.after = actual;', 'failure.after = actual ^ 1U;'),
    ('failure-readback-invalid', 'failure.after_valid = true;', 'failure.after_valid = false;'),
    ('failure-read-error-ignored', 'error = failure.read_error;', 'error = 0;'),
    ('failure-write-error-ignored', 'error = failure.write_error;', 'error = 0;'),
    ('failure-missing', 'failure.valid = true;', 'failure.valid = false;'),
    ('failure-on-success', 'if (error) {\n\t\tfailure.valid', 'if (true) {\n\t\tfailure.valid'),
    ('failure-raw-write-error-lost', 'state->failure = failure;',
     'failure.write_error = failure.write_error > 0 ? -EIO : failure.write_error; state->failure = failure;'),
    ('failure-extra-read', 'error = failure.write_error;',
     'error = failure.write_error; (void)io->read(io->context, request->root, request->where, request->size, &actual);'),
    ('failure-erased-on-restore', 'state->pending = false;',
     'state->failure = (struct n71_resource_write_failure){0}; state->pending = false;'),
    ('restore-with-live-bus', 'if (!bus_removed || state->active)', 'if ((void)bus_removed, state->active)'),
    ('restore-during-allocation', 'if (!bus_removed || state->active)', 'if (!bus_removed)'),
    ('restore-last-window-skipped',
     'for (index = 0; index < 3; index++) {\n\t\terror = n71_scan_restore_value',
     'for (index = 0; index < 2; index++) {\n\t\terror = n71_scan_restore_value'),
    ('restore-error-forgotten',
     'state->extra[index]);\n\t\tif (error)\n\t\t\treturn error;',
     'state->extra[index]);\n\t\tif (error)\n\t\t\treturn 0;'),
    ('restore-owner-lost',
     'state->extra[index]);\n\t\tif (error)',
     'state->extra[index]);\n\t\tstate->pending = false;\n\t\tif (error)'),
)


class ResourceWriteTests(unittest.TestCase):
    def test_config_effects_faults_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler, 'Native compiler required; gate not passed')
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        source = (ROOT / 'phone/kernel/n71-pcie-resource-write.h').read_text()
        with tempfile.TemporaryDirectory(prefix='n71-resource-write-') as directory:
            folder = Path(directory)
            for name in ('n71-pcie-contract.h', 'n71-pcie-ecam.h', 'n71-pcie-scan-config.h',
                         'n71-pcie-io16-upper.h', 'n71-pcie-pref64-disable.h'):
                shutil.copyfile(ROOT / 'phone/kernel' / name, folder / name)
            header, binary = folder / 'n71-pcie-resource-write.h', folder / 'policy'
            for name, before, after in (('baseline', None, None),) + MUTATIONS:
                if before is not None:
                    self.assertEqual(source.count(before), 1, 'Mutation anchor must be unique: ' + name)
                header.write_text(source if before is None else source.replace(before, after, 1))
                compiled = subprocess.run(
                    [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                     '-I', str(folder), str(ROOT / 'tests/n71_pcie_resource_write.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(compiled.returncode, 0, 'Compilation failure is not a kill: ' + name + compiled.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_PCIE_RESOURCE_WRITE_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -6, 'Missing SIGABRT: ' + name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_RESOURCE_WRITE_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
