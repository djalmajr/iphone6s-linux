"""Actual retained owner headers; compiled mutation failures must be assertions."""
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'n71-i2c-pin-owner.h'
OF = 'n71-i2c-pin-owner-of.h'
MUTATIONS = (
    (OF, 'foreign-cell', 'cells[0] != 0x10073 ||', 'false ||'),
    (OF, 'foreign-mmio', 'resource.start != 0x20f100000ULL ||', 'false ||'),
    (OF, 'missing-group-ref-release', 'of_node_put(group);', '(void)group;'),
    (OWNER, 'unbind-allowed', '!device->driver->suppress_bind_attrs)', 'false)'),
    (OWNER, 'replacement-provider', 'registered_gdev != owner->gdev', 'false'),
    (OWNER, 'wrong-pin-offset', '(115 - pin) * 4', '(114 - pin) * 4'),
    (OWNER, 'ignore-glitchless-bit', '(values[1] & 0x270)', '(values[1] & 0x260)'),
    (OWNER, 'cached-readback', 'regmap_read_bypassed(map, offset, &values[2])', 'regmap_read(map, offset, &values[2])'),
    (OWNER, 'missing-selection', 'error = pinctrl_select_state(owner->pinctrl, state);',
     'error = false ? pinctrl_select_state(owner->pinctrl, state) : 0;'),
    (OWNER, 'missing-obligation', 'owner->cleanup_pending = true;', 'owner->cleanup_pending = false;'),
    (OWNER, 'leaked-descriptor', 'gpiod_put(owner->descriptors[index - 1]);', 'if (false) gpiod_put(owner->descriptors[index - 1]);'),
    (OWNER, 'missing-post-release-readback', 'n71_i2c_pin_owner_drop_handles(owner);\n\t\t\terror = n71_i2c_pin_owner_same(owner, map);',
     'n71_i2c_pin_owner_drop_handles(owner);\n\t\t\terror = 0;'),
    (OWNER, 'leaked-provider', 'put_device(&owner->provider->dev);', 'if (false) put_device(&owner->provider->dev);'),
)


class N71I2CPinOwnerTests(unittest.TestCase):
    def test_scope_retained_ownership_release_retry_and_assertion_mutations(self):
        compiler = shutil.which('cc')
        self.assertIsNotNone(compiler)
        limits = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, limits[1]))
        self.addCleanup(resource.setrlimit, resource.RLIMIT_CORE, limits)
        sources = {name: (ROOT / 'phone/kernel' / name).read_text() for name in (OWNER, OF)}
        with tempfile.TemporaryDirectory(prefix='n71-pin-owner-') as directory:
            folder = Path(directory)
            for name in ('device', 'of', 'of_address', 'of_platform', 'platform_device', 'regmap',
                         'slab', 'string', 'gpio/consumer', 'gpio/driver', 'gpio/machine', 'pinctrl/consumer'):
                path = folder / 'linux' / (name + '.h')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('/* APIs supplied by fixture. */\n')
            binary = folder / 'owner'
            for target, name, before, after in ((None, 'baseline', None, None),) + MUTATIONS:
                if before:
                    self.assertEqual(sources[target].count(before), 1, name)
                for filename, source in sources.items():
                    (folder / filename).write_text(source.replace(before, after, 1) if filename == target else source)
                result = subprocess.run(
                    [compiler, '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(folder),
                     str(ROOT / 'tests/n71_i2c_pin_owner.c'), '-o', str(binary)],
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, name + result.stderr)
                result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5, cwd=folder)
                if before is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('N71_I2C_PIN_OWNER_OK cases=', result.stdout)
                    print(result.stdout.strip(), flush=True)
                else:
                    self.assertEqual(result.returncode, -signal.SIGABRT, name + result.stderr)
                    self.assertIn('assert', result.stderr.lower(), name)
                    print('N71_I2C_PIN_OWNER_ASSERTION_KILL ' + name, flush=True)
            print('N71_I2C_PIN_OWNER_GATE_OK mutations=' + str(len(MUTATIONS)), flush=True)


if __name__ == '__main__':
    unittest.main()
