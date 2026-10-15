"""Falsify DNS manifest namespace guards with disposable synthetic bundles."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('manifest-shape', 'not isinstance(report, dict)', 'False',
     'test_invalid_manifest_list_and_records_have_clear_errors_before_ssh'),
    ('list-shape', "not isinstance(report.get('libraries'), list)", 'False',
     'test_invalid_manifest_list_and_records_have_clear_errors_before_ssh'),
    ('record-shape', 'not isinstance(item, dict)', 'False',
     'test_invalid_manifest_list_and_records_have_clear_errors_before_ssh'),
    ('name-type', "not isinstance(item.get('name'), str)", 'False',
     'test_invalid_manifest_list_and_records_have_clear_errors_before_ssh'),
    ('canonical-name', "not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.+-]{0,254}', name)", 'False',
     'test_traversal_absolute_nested_alias_and_control_names_refused_before_ssh'),
    ('duplicate-name', 'or name in names:', 'or False:',
     'test_duplicate_library_records_do_not_collapse_into_an_accepted_scope'),
    ('name-gate', '    names = library_names(report)',
     "    names = {item['name'] for item in report['libraries']}",
     'test_traversal_absolute_nested_alias_and_control_names_refused_before_ssh'),
    ('bundle-digest', "if len(data) != report['bundle_bytes'] or digest != report['bundle_sha256']:",
     'if False:', 'test_valid_names_do_not_bypass_bundle_digest'),
    ('tar-scope', 'if (len(members) != len(expected) or {item.name for item in members} != expected\n'
     '                or any(not item.isfile() or item.mode & 0o7000 for item in members)):',
     'if False:', 'test_tar_names_cannot_exceed_the_validated_library_set'),
    ('manifest-selection', 'install(options.manifest)',
     "install(ROOT / 'runtime/dns-provenance.json')",
     'test_valid_basenames_and_explicit_manifest_transfer_only_verified_bundle'),
]


def main():
    with tempfile.TemporaryDirectory(prefix='dns-bundle-mutations-') as temporary:
        project = Path(temporary).resolve()
        for name in ('scripts/host/dns.py', 'scripts/host/lan.py',
                     'scripts/host/device_profile.py', 'tests/test_dns_bundle.py'):
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', DNS_BUNDLE_SOURCE_ROOT=str(project))
        environment.pop('IPHONE_LINUX_PROFILE', None)
        command = [sys.executable, '-m', 'unittest']
        def run(test):
            return subprocess.run(command + [test], cwd=project / 'tests', env=environment,
                                  capture_output=True, text=True, timeout=20)
        baseline = run('test_dns_bundle')
        if baseline.returncode:
            raise RuntimeError('DNS bundle baseline failed:\n' + baseline.stderr)
        path = project / 'scripts/host/dns.py'
        text = path.read_text()
        for name, before, after, method in MUTATIONS:
            if text.count(before) != 1:
                raise ValueError('Mutation anchor changed: ' + name)
            try:
                path.write_text(text.replace(before, after, 1))
                result = run('test_dns_bundle.DnsBundleTests.' + method)
                if not result.returncode or 'FAIL:' not in result.stderr:
                    raise RuntimeError('SURVIVED_OR_INFRA_ERROR ' + name + '\n' + result.stderr)
                print('KILLED ' + name, flush=True)
            finally:
                path.write_text(text)
    print(f'DNS_BUNDLE_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}')


if __name__ == '__main__':
    main()
