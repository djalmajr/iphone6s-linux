"""Check diagnostic ABI/payload guards in public-only disposable source copies."""
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = 'scripts/build/compose-n71-diagnostic.py'
DEPENDENCIES = (
    SUBJECT, 'scripts/build/integrate-source-kernel.py', 'scripts/build/kernel_patchset.py',
    'scripts/build/kernel_bundle.py', 'scripts/build/prepare-n71-pcie-diagnostic.py',
    'scripts/build/prepare-n71-topology.py', 'scripts/research/n71_runtime_tunables.py',
    'scripts/host/device_profile.py', 'scripts/host/profile_image.py',
    'scripts/host/n71_scan_held_result.py', 'scripts/host/n71_scan_pme_result.py',
    'scripts/host/n71_scan_target_result.py', 'scripts/host/n71_scan_result.py',
    'scripts/host/n71_resource_result.py',
    'scripts/host/n71_resource_readback.py', 'scripts/host/n71_resource_build.py',
    'scripts/host/n71_resource_optional.py',
)
MUTATIONS = (
    ('known-abi', 'if kernel_release not in known:', 'if False:'),
    ('selected-power-abi', "'7.2.0' + KERNEL.kernel_bundle.POWER_LOCALVERSION",
     "'7.2.0' + KERNEL.kernel_bundle.LOCALVERSION"),
    ('selected-binding-abi', "'7.2.0' + KERNEL.kernel_bundle.BINDING_LOCALVERSION",
     "'7.2.0' + KERNEL.kernel_bundle.POWER_LOCALVERSION"),
    ('binding-cli', 'KERNEL.kernel_bundle.POWER_BUNDLE, KERNEL.kernel_bundle.BINDING_BUNDLE',
     'KERNEL.kernel_bundle.POWER_BUNDLE'),
    ('cross-abi', 'raw.count(vermagic) != 1', 'False'),
    ('elf-machine', "struct.unpack_from('<HH', raw, 16) != (1, 183)", 'False'),
    ('payload-binding', 'if original != expected:', 'if False:'),
    ('dt-mask', 'value & ~mask', 'False'),
    ('omit-aspm-opt-in', 'if pcie_aspm_off else KERNEL.BOOTARGS', 'if False else KERNEL.BOOTARGS'),
    ('enable-aspm-off-by-default', 'if pcie_aspm_off else KERNEL.BOOTARGS', 'if True else KERNEL.BOOTARGS'),
    ('wrong-aspm-token', "b' pcie_aspm=off\\n'", "b' pcie_aspm=on\\n'"),
    ('ignore-aspm-flag-type', 'if type(pcie_aspm_off) is not bool:', 'if False:'),
    ('omit-aspm-cli', "parser.add_argument('--pcie-aspm-off',", "parser.add_argument('--aspm-hidden',"),
    ('held-aspm-scope', 'not options.pcie_aspm_off or', 'False or'),
    ('held-binding-scope', 'options.kernel_patchset != KERNEL.kernel_bundle.BINDING_BUNDLE', 'False'),
    ('held-reg-required', 'options.reg_on_module is None', 'False'),
    ('held-reg-explicit', 'elif options.reg_on_module is not None:', 'elif False:'),
    ('held-pcie-size', "len(driver) != pcie['bytes']", 'False'),
    ('held-pcie-hash', "hashlib.sha256(driver).hexdigest() != pcie['sha256']", 'False'),
    ('held-reg-size', "path.stat().st_size != reg['bytes']", 'False'),
    ('held-reg-hash', "hashlib.sha256(raw).hexdigest() != reg['sha256']", 'False'),
    ('held-reg-abi', 'validate_module(raw, kernel_release=kernel_release)', 'pass'),
    ('held-reg-private-path', 'DIAGNOSTIC.TUNABLES.private_path(options.reg_on_module)', 'options.reg_on_module'),
    ('held-reg-copy', 'if reg_driver is not None:', 'if False:'),
    ('held-profile-flag', "'pcie_scan_hold': options.pcie_scan_hold", "'pcie_scan_hold': False"),
    ('held-profile-target', 'pcie_scan_link_target=True', 'pcie_scan_link_target=False'),
    ('held-profile-noop', 'pcie_scan_pme_noop=False', 'pcie_scan_pme_noop=True'),
    ('held-profile-pme', 'pcie_scan_pme_disable=True', 'pcie_scan_pme_disable=False'),
    ('held-build-contract', 'records = selector.selected_records(ROOT, release=kernel_release, **kwargs)',
     "records = [dict(json.loads((ROOT / 'docs/evidence/n71-pci-held-caller.json').read_text())['kernel_build']['modules'][name], module=name) for name in ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')]"),
    ('held-resource-scope', 'if options.pcie_resource_capable and not options.pcie_scan_hold:', 'if False:'),
    ('held-resource-build', 'n71_resource_result if options.pcie_resource_capable else n71_scan_held_result',
     'n71_scan_held_result'),
    ('held-resource-provenance', "'pcie_resource_capable': options.pcie_resource_capable", "'pcie_resource_capable': False"),
    ('held-resource-default', "'--pcie-resource-capable', action='store_true',",
     "'--pcie-resource-capable', action='store_true', default=True,"),
    ('held-readback-hash-forwarding', "kwargs = {'pcie_sha256': hashlib.sha256(driver).hexdigest()} if selector is n71_resource_result else {}", 'kwargs = {}'),
)


def run(subject=None, *, pattern='test_n71_diagnostic_*.py'):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    environment.pop('N71_DIAGNOSTIC_COMPOSER_SCRIPT', None)
    if subject is not None:
        environment['N71_DIAGNOSTIC_COMPOSER_SCRIPT'] = str(subject)
    return subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                           '-p', pattern, '-v'], env=environment,
                          capture_output=True, text=True, timeout=30)


def main():
    baseline = run()
    if baseline.returncode:
        print(baseline.stderr, file=sys.stderr)
        return 1
    count = re.search(r'\bRan (\d+) tests?\b', baseline.stderr)
    if count is None:
        raise ValueError('Complete diagnostic baseline test count required')
    print('N71_DIAGNOSTIC_PAYLOAD_BASELINE_OK tests=' + count.group(1))
    for line in baseline.stdout.splitlines():
        if line.startswith('N71_READBACK_LINK_ASSERTION_KILL '):
            print(line)
    text = (ROOT / SUBJECT).read_text()
    with tempfile.TemporaryDirectory(prefix='n71-diagnostic-public-mutations-') as folder:
        copied = Path(folder) / 'source'
        for name in DEPENDENCIES:
            target = copied / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        target = copied / SUBJECT
        for name, before, after in MUTATIONS:
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            target.write_text(text.replace(before, after, 1))
            compile(target.read_text(), str(target), 'exec')
            pattern = 'test_n71_diagnostic_held_profile.py' if name.startswith('held-') else 'test_n71_diagnostic_payload.py'
            result = run(target, pattern=pattern)
            if (not result.returncode or 'FAIL:' not in result.stderr
                    or 'AssertionError' not in result.stderr or 'ERROR:' in result.stderr):
                print('SURVIVED_OR_INFRA_ERROR ' + name, file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return 1
            print('KILLED ' + name)
    print(f'N71_DIAGNOSTIC_PAYLOAD_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
