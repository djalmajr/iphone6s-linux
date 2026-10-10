"""Exercise integration guards in disposable synthetic projects, never devices."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/integrate-source-kernel.py'
MUTATIONS = [
    ('kernel-hash', "if digest(blobs[name]) != expected['sha256']:", 'if False:'),
    ('page-size', "(struct.unpack_from('<Q', header, 24)[0] >> 1) & 3 != 2", 'False'),
    ('retained-old-module', 'removed += 1\n            continue',
     'removed += 1\n            result.append(raw[start:offset])\n            continue'),
    ('private-output-mode', 'path.chmod(0o600)', 'path.chmod(0o644)'),
    ('destination-scope', "output.parent != ROOT / 'runtime' or output.exists()", 'output.exists()'),
    ('m1n1-digest', "not expected['matches_original'] or digest(m1n1) != expected['sha256']", 'False'),
    ('header-byte-preservation', "header[:54] + f'{len(new):08x}'.encode() + header[62:]",
     "header[:54].lower() + f'{len(new):08x}'.encode() + header[62:].lower()"),
    ('patchset-record-selection', "'kernel-dart-build.json' if patchset else 'kernel-source-build.json'",
     "'kernel-source-build.json'"),
    ('patchset-base', "if source['commit'] != kernel_patchset.BASE:", 'if False:'),
    ('patchset-identity', "if source['patchset'] != patchset or source['patch_sha256'] != kernel_patchset.PATCH_SHA:",
     'if False:'),
    ('patchset-builtin-dart', "if patchset and 'CONFIG_APPLE_DART=y' not in config:", 'if False:'),
    ('bundle-full-link', "if record['build'].get('full_image_linked') is not True or record['build'].get('vmlinux_modpost_verified') is not True:",
     'if False:'),
    ('bundle-base', "if source['commit'] != kernel_bundle.BASE:", 'if False:'),
    ('bundle-identity', "if source['bundle'] != patchset or source['required_localversion'] != version:",
     'if False:'),
    ('bundle-pinned-sources', "if source['patches'] != patches or source['files'] != {key: list(value) for key, value in files.items()}:",
     'if False:'),
    ('bundle-release', "if record['build']['kernel_release'] != '7.2.0' + version:",
     'if False:'),
    ('bundle-export', "if record['build'].get('serdev_stop_bits_export_verified') is not True:",
     'if False:'),
    ('bundle-config', 'if any(line not in config for line in required):', 'if False:'),
    ('bundle-old-module', 'if forbid_extra_modules and normalized != MODULE:', 'if False:'),
    ('binding-record-selection', "'kernel-n71-binding-build.json' if patchset == kernel_bundle.BINDING_BUNDLE",
     "'kernel-n71-power-bundle-build.json' if patchset == kernel_bundle.BINDING_BUNDLE"),
    ('binding-builtin-providers', 'if patchset in (kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE) and any(',
     'if patchset == kernel_bundle.POWER_BUNDLE and any('),
    ('binding-old-module', 'forbid_extra_modules=options.kernel_patchset in (kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE)',
     'forbid_extra_modules=options.kernel_patchset in (kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE)'),
    ('power-record-selection', "'kernel-n71-power-bundle-build.json' if patchset == kernel_bundle.POWER_BUNDLE",
     "'kernel-n71-bundle-build.json' if patchset == kernel_bundle.POWER_BUNDLE"),
    ('power-builtin-providers', 'if patchset in (kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE) and any(', 'if False and any('),
    ('power-old-module', 'forbid_extra_modules=options.kernel_patchset in (kernel_bundle.BUNDLE, kernel_bundle.POWER_BUNDLE, kernel_bundle.BINDING_BUNDLE)',
     'forbid_extra_modules=options.kernel_patchset in (kernel_bundle.BUNDLE, kernel_bundle.BINDING_BUNDLE)'),
]


def run(source=None, *, timeout=60):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment.pop('KERNEL_INTEGRATION_SCRIPT', None)
    if source is not None:
        environment['KERNEL_INTEGRATION_SCRIPT'] = str(source)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                           '-p', 'test_kernel*integration.py', '-v'], env=environment,
                          capture_output=True, text=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mutation', action='append', choices=[item[0] for item in MUTATIONS],
                        help='Run only named mutations when retrying an interrupted gate.')
    parser.add_argument('--test-timeout', type=int, choices=(60, 120, 180), default=60,
                        help='Bounded suite timeout for a VM sharing resources with a build.')
    options = parser.parse_args()
    selected = [item for item in MUTATIONS if not options.mutation or item[0] in options.mutation]
    baseline = run(timeout=options.test_timeout)
    if baseline.returncode:
        print(baseline.stderr, file=sys.stderr)
        return 1
    text = SOURCE.read_text()
    with tempfile.TemporaryDirectory(prefix='kernel-integration-mutations-') as work:
        for name, before, after in selected:
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            path = Path(work) / (name + '.py')
            path.write_text(text.replace(before, after, 1))
            compile(path.read_text(), str(path), 'exec')
            result = run(path, timeout=options.test_timeout)
            if (not result.returncode or 'FAIL:' not in result.stderr
                    or 'AssertionError' not in result.stderr or 'ERROR:' in result.stderr):
                print('SURVIVED_OR_INFRA_ERROR ' + name, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return 1
            print('KILLED ' + name)
    print(f'KERNEL_INTEGRATION_MUTATIONS_OK {len(selected)}/{len(selected)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
