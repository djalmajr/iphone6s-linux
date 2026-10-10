"""Falsify candidate-profile boundaries in a disposable source copy."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ('ssh-strict-pin-policy', 'device_profile.py',
     "'StrictHostKeyChecking=yes'", "'StrictHostKeyChecking=no'",
     'test_valid_profile_and_effective_ssh_identity'),
    ('boolean-format', 'device_profile.py',
     "type(data['format']) is not int", "not isinstance(data['format'], int)",
     'test_invalid_schema_paths_and_aliases_fail_closed'),
    ('empty-profile-fallback', 'device_profile.py',
     "selected = os.environ.get('IPHONE_LINUX_PROFILE')",
     "selected = os.environ.get('IPHONE_LINUX_PROFILE') or None",
     'test_explicit_invalid_selection_never_falls_back'),
    ('private-file-guard', 'device_profile.py',
     "if (not valid_type or metadata.st_uid != os.geteuid()\n            or metadata.st_mode & 0o7077 or (not directory and metadata.st_nlink != 1)):",
     'if False:', 'test_private_files_links_and_directory_permissions'),
    ('payload-hash', 'device_profile.py',
     "if hashlib.file_digest(file, 'sha256').hexdigest() != profile[hash_field]:",
     'if False:', 'test_changed_hash_and_mixed_payload_are_rejected'),
    ('payload-initramfs-binding', 'profile_image.py',
     'if payload.read() != compressed:', 'if False:',
     'test_changed_hash_and_mixed_payload_are_rejected'),
    ('client-authorization-binding', 'profile_image.py',
     'if len(authorized) != 1 or device_profile.public_wire(authorized[0]) != client_public:',
     'if len(authorized) != 1:', 'test_client_and_server_identities_must_match_image'),
    ('server-pin-binding', 'profile_image.py',
     "if dropbear_public(entries['etc/dropbear/dropbear_ed25519_host_key']) != profile['server_public']:",
     'if False:', 'test_client_and_server_identities_must_match_image'),
    ('embedded-key-permissions', 'profile_image.py',
     'if mode != expected or uid != 0 or gid != 0 or (not directory and links != 1):',
     'if False:', 'test_unsafe_embedded_permissions_and_duplicate_identity'),
    ('extra-cpio-archive', 'profile_image.py',
     'if size != 0 or any(raw[offset:]):', 'if False:',
     'test_additional_archive_and_unsupported_init_are_rejected'),
    ('telnet-image', 'profile_image.py',
     "if b'telnetd' in entries['init'] or b'ip link set lo up' not in entries['init']:",
     'if False:', 'test_additional_archive_and_unsupported_init_are_rejected'),
    ('lan-profile-transport', 'lan.py',
     'return device_profile.ssh_options(ROOT)', "return ['ssh']",
     'test_profile_transport.ProfileTransportTests.test_snapshot_lan_and_dns_select_same_identity_without_default_keys'),
    ('snapshot-profile-transport', 'persist.py',
     "return device_profile.ssh_options(ROOT) + [f'root@{device_profile.PHONE}']",
     "return ['ssh', 'root@172.16.42.1']",
     'test_profile_transport.ProfileTransportTests.test_snapshot_lan_and_dns_select_same_identity_without_default_keys'),
    ('dns-profile-preflight', 'dns_lan.py',
     'profile = device_profile.load(lan.ROOT)',
     "profile = {'client_key': lan.ROOT / 'keys/iphone_ed25519', 'known_hosts': lan.ROOT / 'keys/known_hosts'}",
     'test_profile_transport.ProfileTransportTests.test_snapshot_lan_and_dns_select_same_identity_without_default_keys'),
    ('consumer-empty-profile-fallback', 'device_profile.py',
     "selected = os.environ.get('IPHONE_LINUX_PROFILE')",
     "selected = os.environ.get('IPHONE_LINUX_PROFILE') or None",
     'test_profile_transport.ProfileTransportTests.test_invalid_profile_aborts_before_ssh_or_snapshot_publication'),
    ('wrapper-profile-alias', 'iphone-linux.sh',
     '-o "HostKeyAlias=${PROFILE_FIELDS[2]}"', '-o HostKeyAlias=wrong-test-profile',
     'test_profile_boot.ProfileBootTests.test_valid_profile_sends_selected_payload_and_uses_selected_ssh_identity'),
    ('wrapper-profile-selection', 'iphone-linux.sh',
     'if [ "${IPHONE_LINUX_PROFILE+x}" = x ]; then', 'if [ 0 = 1 ]; then',
     'test_profile_boot.ProfileBootTests.test_invalid_selector_and_incompatible_commands_abort_before_usb'),
    ('wrapper-profile-preflight', 'iphone-linux.sh',
     'python3 "$ROOT/scripts/host/device_profile.py" check', ':',
     'test_profile_boot.ProfileBootTests.test_image_or_identity_mismatch_aborts_before_usb'),
    ('wrapper-recovery-fallback', 'iphone-linux.sh',
     'if [ "$PROFILE_EXPLICIT" -eq 1 ]; then\n            printf',
     'if [ 0 = 1 ]; then\n            printf',
     'test_profile_boot.ProfileBootTests.test_profile_ssh_failure_refuses_recovery_but_default_probe_keeps_it'),
    ('wrapper-http-trust', 'iphone-linux.sh',
     'if [ "$PROFILE_EXPLICIT" -eq 1 ] && ! ssh_ready; then', 'if false; then',
     'test_profile_boot.ProfileBootTests.test_profile_ssh_failure_refuses_untrusted_http'),
]


def run():
    with tempfile.TemporaryDirectory(prefix='profile-mutations-') as temporary:
        project = Path(temporary) / 'project'
        shutil.copytree(ROOT, project, ignore=shutil.ignore_patterns(
            'keys', 'runtime', 'backups', 'logs', 'bin', 'artifacts', '__pycache__', '.git'))
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        environment.pop('IPHONE_LINUX_PROFILE', None)
        command = [sys.executable, '-m', 'unittest']
        for pattern in ('test_device_profile.py', 'test_profile_transport.py', 'test_profile_boot.py'):
            baseline = subprocess.run(command + ['discover', '-s', 'tests', '-p', pattern],
                                      cwd=project, env=environment, capture_output=True, text=True, timeout=40)
            if baseline.returncode:
                raise RuntimeError('Profile baseline failed:\n' + baseline.stdout + baseline.stderr)
            print('BASELINE_PROFILE_OK', pattern, flush=True)
        for name, filename, old, new, test in MUTATIONS:
            source = project / 'scripts/host' / filename
            original = source.read_text()
            if original.count(old) != 1:
                raise RuntimeError('Mutation target is not unique: ' + name)
            try:
                source.write_text(original.replace(old, new, 1))
                target = test if '.' in test else 'test_device_profile.DeviceProfileTests.' + test
                result = subprocess.run(command + [target],
                                        cwd=project / 'tests', env=environment, capture_output=True,
                                        text=True, timeout=15)
                if result.returncode == 0 or 'FAIL:' not in result.stderr:
                    raise RuntimeError('Mutation survived or did not reach an assertion: ' + name
                                       + '\n' + result.stdout + result.stderr)
                print('KILLED', name, flush=True)
            finally:
                source.write_text(original)
        print(f'PROFILE_MUTATIONS_OK {len(MUTATIONS)}/{len(MUTATIONS)}', flush=True)


if __name__ == '__main__':
    run()
