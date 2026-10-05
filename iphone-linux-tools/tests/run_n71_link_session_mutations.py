"""Selected session guards must fail assertions when weakened, without SSH."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71-link-session.py'
MUTATIONS = {
    'profile-release-pair': ("metadata.get('kernel_release') == release", 'True'),
    'profile-payload': ("metadata.get('payload_sha256') == payload_sha256", 'True'),
    'binding-build-flags': ("and build['werror'] is True and build['modpost_passed'] is True", ''),
    'binding-module-abi': ("all(record['vermagic'] == release + ' SMP preempt mod_unload aarch64' for record in records)", 'True'),
    'selected-elf-release': ("magic = ('vermagic=' + release +", "magic = ('vermagic=' + RELEASE +"),
    'selected-live-release': ("p.stdout.startswith(self.release + '\\n')", "p.stdout.startswith(RELEASE + '\\n')"),
    'selected-result-release': ("{'kernel_release': self.release,", "{'kernel_release': RELEASE,"),
    'selected-history-release': ('History(options.previous_clean, ROOT, release)', 'History(options.previous_clean, ROOT, RELEASE)'),
    'binding-profile-module-hash': ("metadata['module_sha256'] == records[0]['sha256']", 'True'),
    'selected-session-release': ('history=history, scan_link_target=options.scan_link_target, release=release).run()', 'history=history, scan_link_target=options.scan_link_target).run()'),
    'target-profile-flag': ("metadata.get('pcie_scan_link_target', False) is options.scan_link_target", 'True'),
    'target-mode-abi': ('host_scan and release == BINDING_RELEASE,', 'True,'),
    'target-module-abi': ("all(r['vermagic'] == release + ' SMP preempt mod_unload aarch64' for r in records)", 'True'),
    'target-module-pin': ("and evidence['contract']['module_pin_while_pending'] is True", ''),
    'target-build-flags': ("and build['modpost_passed'] is True and build['werror'] is True", ''),
    'target-unbind': ("and evidence['contract']['bind_attributes_suppressed'] is True", ''),
    'reg-on-under-retention': ('if self.reg_attempted and pcie_released:', 'if self.reg_attempted:'),
    'ignore-live-status': ("n71_scan_target_result.live_status(p.stdout)\n                    if not", "{'ready': 1, 'retained': 0}\n                    if not"),
    'ignore-retry-state': ('and n71_scan_target_result.is_clean(n71_scan_target_result.live_status(p.stdout)),', 'and True,'),
    'host-selection': ("'n71-pcie-controls-scan-build.json'", "'n71-pcie-bridge-scan-build.json'"),
    'cycle-mode': ("parameters += ' dart_cycle=1'", "parameters += ''"),
    'cycle-cleanup': ('n71_dart_cycle_result.cleanup(p.stdout)', 'pass'),
    'private-ttbr-output': ("and 'N71_DART_TTBR ' not in line", ''),
    'original-latch': ("'N71_REG_ON_OBSERVED control=80 bit0=0 compatible-plan=1' in p.stdout",
                       "'N71_REG_ON_OBSERVED' in p.stdout"),
    'fresh-control': ("and 'N71_REG_ON_CONTROL_READBACK value=81' in p.stdout,", 'and True,'),
    'restore-pending': ('require(p.returncode == 0 and (absent or restored),', 'require(p.returncode == 0,'),
    'cleanup-finally': ('            self.cleanup()', "            self.result['cleanup_verified'] = True"),
    'read-budget': ("require(0 <= int(reads) <= 10000, 'Link read budget exceeded')",
                    "require(True, 'Link read budget exceeded')"),
    'endpoint-validity': ("and identities[0] not in ('00000000', 'ffffffff'),", 'and True,'),
    'link-predicate': ('require(int(status, 16) & 1 and len(identities) == 1', 'require(len(identities) == 1'),
    'inventory-budget': ('1 <= int(reads) <= 63', '1 <= int(reads) <= 64'),
    'inventory-master': ('not (int(command, 16) & 4)', 'True'),
    'inventory-bars': ('[int(index) for index, _ in bars] == list(range(6))', 'len(bars) == 6'),
    'inventory-mode': ("' config_inventory=1' if self.config_inventory else ''", "''"),
    'inventory-selection': ("if record['module'] == 'n71-pcie-diagnostic.ko' else record for record in records]",
                            'if False else record for record in records]'),
}
TARGET_MUTATIONS = {
    'status-unique': ('len(rows) == 1', 'len(rows) >= 1'),
    'ignore-retained': ("('retained', 'scan_pending', 'reset_pending', 'powered', 'attached', 'power_put_pending', 'cleanup_error')",
                        "('scan_pending', 'reset_pending', 'powered', 'attached', 'power_put_pending', 'cleanup_error')"),
    'ignore-powered': ("('retained', 'scan_pending', 'reset_pending', 'powered', 'attached', 'power_put_pending', 'cleanup_error')",
                       "('retained', 'scan_pending', 'reset_pending', 'attached', 'power_put_pending', 'cleanup_error')"),
    'ignore-put-pending': ("'attached', 'power_put_pending', 'cleanup_error'", "'attached', 'cleanup_error'"),
    'counts-annotation': ('text.count(suffix) == 1', 'True'),
    'final-caller-cleanup': ('tuple(map(int, sessions[-1][:7])) == (0, 0, 0, 0, 0, 0, 0)', 'True'),
    'final-config': ("config[-1] == '0'", 'True'),
    'final-target': ("restored[-1] == ('0', '0')", 'True'),
    'bus-removed': ("require(removed == ['1'],", 'require(True,'),
    'caller-primary': ("live_status(text).get('primary_error') == 0", 'True'),
    'unbound-success': ("result['error'] < 0", 'True'),
    'unbound-primary': ("int(sessions[-1][7]) == result['error']", 'True'),
}


def main():
    with tempfile.TemporaryDirectory(prefix='n71-link-session-mutations-') as directory:
        folder = Path(directory)
        variants = [(SOURCE, 'N71_LINK_SESSION_SCRIPT', name, values) for name, values in MUTATIONS.items()]
        variants += [(ROOT / 'scripts/host/n71_scan_target_result.py', 'N71_SCAN_TARGET_RESULT_SCRIPT', name, values)
                     for name, values in TARGET_MUTATIONS.items()]
        for source, variable, name, (before, after) in variants:
            text = source.read_text()
            if text.count(before) != 1:
                raise SystemExit('Mutation anchor differs: ' + name)
            mutated = folder / (name + '.py')
            mutated.write_text(text.replace(before, after))
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
            environment[variable] = str(mutated)
            process = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                      '-p', 'test_n71_link_session.py'], env=environment,
                                     capture_output=True, text=True, timeout=30)
            output = process.stdout + process.stderr
            if process.returncode == 0 or 'AssertionError' not in output or 'ERROR:' in output:
                raise SystemExit('Mutation not killed by assertion: ' + name)
            print('N71_LINK_SESSION_MUTATION_KILLED', name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
