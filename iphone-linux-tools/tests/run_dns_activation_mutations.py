"""Compile real source mutations and require assertion failures after a green baseline."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = {
    'peer': ('dns_activation.py',
             'if peer_identity(channel) != (expected.uid, expected.gid):', 'if False:',
             'ActivationTests.test_wrong_peer_refused'),
    'nonce': ('dns_activation.py', 'not hmac.compare_digest(nonce, expected.nonce)',
              'False', 'ActivationTests.test_wrong_nonce_refused'),
    'groups': ('dns_activation.py', ' or groups != 0', '',
               'ActivationTests.test_frame_identity_and_groups_refused'),
    'frame-gid': ('dns_activation.py', ' or gid != expected.gid', '',
                  'ActivationTests.test_frame_identity_and_groups_refused'),
    'socket-type': ('dns_activation.py',
                    'listener.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != kind', 'False',
                    'ActivationTests.test_wrong_first_type_refused'),
    'socket-bind': ('dns_activation.py', 'listener.getsockname() != (expected.bind, expected.port)',
                    'False', 'ActivationTests.test_wrong_address_and_port_refused'),
    'tcp-state': ('dns_activation.py', 'and premature_tcp_state(listener)', 'and False',
                  'ActivationTests.test_listening_tcp_refused'),
    'reuseaddr': ('dns_activation.py', 'listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)',
                  'False', 'ActivationTests.test_reuse_options_refused'),
    'reuseport': ('dns_activation.py', 'listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT)',
                  'False', 'ActivationTests.test_reuse_options_refused'),
    'raw-fd-cleanup': ('dns_activation.py',
                       'for descriptor in descriptors:\n            os.close(descriptor)',
                       'for descriptor in descriptors:\n            pass',
                       'ActivationTests.test_extra_descriptor_refused'),
    'adopted-fd-cleanup': ('dns_activation.py',
                           'for listener in adopted:\n            listener.close()',
                           'for listener in adopted:\n            pass',
                           'ActivationTests.test_rejected_adopted_fds_close_even_with_references_held'),
    'controller-root': ('dns_activation.py',
                        'if os.getuid() <= 0 or os.getuid() != os.geteuid() or os.getgid() <= 0:',
                        'if False:', 'ActivationTests.test_root_controller_refused_before_launch'),
    'usb-bind': ('dns_privileged.py',
                 " or address in ipaddress.ip_network('172.16.42.0/24')", '',
                 'ActivationTests.test_bootstrap_bind_scope'),
    'channel-mode': ('dns_privileged.py', 'parent.st_mode & 0o077', 'False',
                     'ActivationTests.test_private_channel_refuses_permissions_symlinks_and_owner'),
    'nonce-length': ('dns_privileged.py', 'if len(data) != 32:', 'if False:',
                     'ActivationTests.test_nonce_exact_length_and_eof'),
}
PRIVILEGED = {
    'drop-groups': ('dns_privileged.py', 'os.setgroups([])', 'pass',
                    'ActivationBootstrapTests.test_actual_root_bind_drop_handoff_data_and_cleanup'),
    'drop-uid': ('dns_privileged.py', 'os.setuid(options.uid)', 'pass',
                 'ActivationBootstrapTests.test_actual_root_bind_drop_handoff_data_and_cleanup'),
    'original-identity': ('dns_privileged.py',
                          "or str(options.uid) != os.environ.get('SUDO_UID')", 'or False',
                          'ActivationBootstrapTests.test_bootstrap_refuses_wrong_original_identity'),
}


def run(base, cases):
    return subprocess.run([sys.executable, '-B', str(base / 'tests/test_dns_activation.py')]
                          + cases + ['-v'], capture_output=True, text=True, timeout=30)


def main():
    privileged = os.environ.get('IPHONE_ACTIVATION_MUTATIONS_PRIVILEGED') == '1'
    if privileged and (sys.platform != 'linux' or os.geteuid() == 0
                       or not os.environ.get('IPHONE_ACTIVATION_TEST_BIND')):
        raise SystemExit('Privileged mutations require non-root VM namespace controller.')
    available = MUTATIONS | (PRIVILEGED if privileged else {})
    selected = sys.argv[1:] or list(available)
    if any(name not in available for name in selected):
        raise SystemExit('Unknown mutation or missing privileged opt-in.')
    with tempfile.TemporaryDirectory(prefix='idns-mutants-') as folder:
        base = Path(folder)
        (base / 'scripts/host').mkdir(parents=True)
        (base / 'tests').mkdir()
        originals = {}
        for source in (ROOT / 'scripts/host').glob('*.py'):
            shutil.copy(source, base / 'scripts/host' / source.name)
            originals[source.name] = source.read_text()
        shutil.copy(ROOT / 'tests/test_dns_activation.py', base / 'tests/test_dns_activation.py')
        cases = ['ActivationTests'] + (['ActivationBootstrapTests'] if privileged else [])
        baseline = run(base, cases)
        if baseline.returncode or 'skipped' in baseline.stderr:
            raise SystemExit('Baseline failed:\n' + baseline.stdout + baseline.stderr)
        print('BASELINE_OK ' + ','.join(cases), flush=True)
        for name in selected:
            filename, before, after, case = available[name]
            original = originals[filename]
            if original.count(before) != 1:
                raise SystemExit('Mutation anchor not unique: ' + name)
            mutated = original.replace(before, after)
            compile(mutated, filename, 'exec')  # Syntax failure never counts as a kill.
            target = base / 'scripts/host' / filename
            target.write_text(mutated)
            try:
                result = run(base, [case])
            finally:
                target.write_text(original)
            if (result.returncode != 1 or 'AssertionError:' not in result.stderr
                    or 'FAIL:' not in result.stderr or 'ERROR:' in result.stderr
                    or 'skipped' in result.stderr):
                raise SystemExit('Mutation survived or failed without assertion: ' + name
                                 + '\n' + result.stdout + result.stderr)
            print('ASSERTION_KILLED ' + name, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
