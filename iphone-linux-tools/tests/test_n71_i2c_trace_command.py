"""Execute the I2C shell on disposable modeled sysfs, never on hardware."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SOURCE = ROOT / 'scripts/host/n71_i2c_trace_command.py'
spec = importlib.util.spec_from_file_location('i2c_trace_subject', os.environ.get('N71_I2C_TRACE_SCRIPT', SOURCE))
SUBJECT = importlib.util.module_from_spec(spec); spec.loader.exec_module(SUBJECT)
BOOT = '01234567-89ab-cdef-0123-456789abcdef'


class TraceCommand(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='n71-i2c-trace-'); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.modules = self.root / 'modules'; self.modules.mkdir()
        self.base = self.modules / 'n71_i2c_power_diagnostic/parameters'
        self.events = self.root / 'events'; self.scenario = self.root / 'scenario'; self.scenario.write_text('clean')
        self.boot = self.root / 'boot'; self.boot.write_text(BOOT + '\n')
        data = b'fixture-not-loadable'.ljust(52904, b'\0')
        self.record = {'path': 'sources/phone/kernel/' + SUBJECT.MODULE, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        folder = self.root / 'upload'; folder.mkdir(); self.module = folder / SUBJECT.MODULE; self.module.write_bytes(data)
        self.binary = self.root / 'bin'; self.binary.mkdir()
        prefix = (f'#!{sys.executable}\nimport sys,hashlib,shutil\nfrom pathlib import Path\n'
            + f'base=Path({str(self.base)!r}); events=Path({str(self.events)!r}); scenario=Path({str(self.scenario)!r}).read_text()\n')
        self.shim('id', '#!/bin/sh\necho 0\n')
        self.shim('uname', '#!/bin/sh\necho ' + SUBJECT.dma.RELEASE + '\n')
        self.shim('insmod', prefix + 'base.mkdir(parents=True)\n'
            + 'action=base/"action"\n'
            + 'if scenario=="action-error": action.mkdir()\n'
            + 'else: action.write_text("")\n'
            + 'with events.open("a") as f: f.write("load\\n")\n')
        self.shim('rmmod', prefix + 'with events.open("a") as f: f.write("unload\\n")\nshutil.rmtree(base.parent)\n')
        self.shim('cat', '#!/bin/sh\nbase=' + shlex.quote(str(self.base))
            + '\nevents=' + shlex.quote(str(self.events)) + '\nscenario=$(/bin/cat ' + shlex.quote(str(self.scenario)) + ')\n'
            + 'case "$1" in "$base/status"|"$base/configuration_status")\n'
            + 'action=; if test -f "$base/action"; then action=$(/bin/cat "$base/action"); fi\n'
            + 'printf "read %s\\n" "$action" >> "$events"\n'
            + 'dirty=0\nif { test "$scenario" = cleanup || test "$scenario" = retained; } && test "$action" = configure; then dirty=1; fi\n'
            + 'if test "$scenario" = retained && test "$action" = cleanup; then dirty=1; fi\n'
            + 'if test "$1" = "$base/status"; then\n'
            + ' if test "$dirty" = 1; then echo ' + shlex.quote(SUBJECT.CLEAN.replace('active=0','active=1'))
            + '; else echo ' + shlex.quote(SUBJECT.CLEAN) + '; fi\nelse\n'
            + ' if test "$dirty" = 1; then echo ' + shlex.quote(SUBJECT.CONFIGURATION.replace('controller_pending=0','controller_pending=1'))
            + '; else echo ' + shlex.quote(SUBJECT.CONFIGURATION) + '; fi\nfi\n;;\n*) exec /bin/cat "$@";;\nesac\n')
        self.shim('sha256sum', prefix + 'digest,name=sys.stdin.read().strip().split(None,1)\n'
            + 'sys.exit(0 if hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest else 1)\n')
        self.shim('dmesg', '#!/bin/sh\necho "[ 12.000000] N71_I2C_RESET_TRACE attempts=100 samples=100 sample_error=0 first_ctl=0000010f last_ctl=0000010f added_reads=0 added_writes=0"\n')

    def shim(self, name, text):
        path = self.binary / name; path.write_text(text); path.chmod(0o700)

    def run_shell(self):
        command = SUBJECT.script(BOOT, self.record).replace('/proc/sys/kernel/random/boot_id', str(self.boot)).replace(
            '/sys/module/', str(self.modules) + '/').replace('/tmp/n71-i2c-trace-' + BOOT, str(self.module.parent))
        return subprocess.run(['/bin/sh', '-c', command], env=dict(os.environ, PATH=str(self.binary) + ':/usr/bin:/bin'),
            capture_output=True, text=True, timeout=10)

    def test_clean_cycle_collects_trace_and_unloads_after_all_actions(self):
        result = self.run_shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        for action in ('inspect','configure','read-hdq-control'):
            self.assertIn('HDQ_ACTION action=' + action + ' exit=0', result.stdout)
        self.assertIn('N71_I2C_RESET_TRACE', result.stdout); self.assertIn('cleanup=verified', result.stdout)
        self.assertEqual(self.events.read_text().splitlines()[-1], 'unload'); self.assertFalse(self.base.exists())

    def test_pending_configuration_is_cleaned_before_normal_unload(self):
        self.scenario.write_text('cleanup'); result = self.run_shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        events = self.events.read_text().splitlines()
        self.assertLess(events.index('read cleanup'), events.index('unload'))

    def test_retained_configuration_prevents_unload_and_still_reports_trace(self):
        self.scenario.write_text('retained'); result = self.run_shell()
        self.assertNotEqual(result.returncode, 0); self.assertIn('HDQ_RETAINED_OWNERSHIP', result.stdout)
        self.assertIn('N71_I2C_RESET_TRACE', result.stdout)
        self.assertNotIn('unload', self.events.read_text()); self.assertTrue(self.base.exists())

    def test_negative_first_action_stops_series_but_verifies_clean_unload(self):
        self.scenario.write_text('action-error'); result = self.run_shell()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r'HDQ_ACTION action=inspect exit=[1-9][0-9]*')
        self.assertNotIn('HDQ_ACTION action=configure', result.stdout)
        self.assertIn('cleanup=verified', result.stdout); self.assertFalse(self.base.exists())

    def test_wrong_boot_bytes_and_concurrent_wlan_refuse_before_loading(self):
        old = self.module.read_bytes()
        for mode in ('boot','bytes','wlan'):
            with self.subTest(mode=mode):
                if mode=='boot': self.boot.write_text('11234567-89ab-cdef-0123-456789abcdef\n')
                elif mode=='bytes': self.module.write_bytes(b'x' + old[1:])
                else: (self.modules/'n71_pcie_diagnostic').mkdir()
                result = self.run_shell()
                self.assertNotEqual(result.returncode, 0); self.assertFalse(self.events.exists())
                self.boot.write_text(BOOT + '\n'); self.module.write_bytes(old)

    def test_old_or_implicit_variant_refuses_without_querying_source(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(SUBJECT.pmd, 'snapshot', side_effect=AssertionError('Must not query')):
            with self.assertRaises(ValueError): SUBJECT.prepare(ROOT, BOOT)
        with self.assertRaises(ValueError): SUBJECT.script(BOOT + ';invalid', self.record)


@unittest.skipIf(os.environ.get('N71_I2C_TRACE_SCRIPT'), 'Mutation child')
class Mutations(unittest.TestCase):
    def test_boot_cleanup_and_negative_series_mutations_fail_by_assertion(self):
        variants = [
            ('boot', 'test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}', ':', 'test_wrong_boot_bytes_and_concurrent_wlan_refuse_before_loading'),
            ('cleanup-guard', 'if ! is_clean; then\n        printf', 'if false; then\n        printf', 'test_retained_configuration_prevents_unload_and_still_reports_trace'),
            ('first-error', 'if test "$primary" -ne 0; then break; fi', ':', 'test_negative_first_action_stops_series_but_verifies_clean_unload'),
            ('trace-on-error', 'trap report EXIT', ':', 'test_retained_configuration_prevents_unload_and_still_reports_trace'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-i2c-trace-mutations-') as directory:
            for name, before, after, method in variants:
                body = SOURCE.read_text(); self.assertGreaterEqual(body.count(before), 1)
                body = body.replace(before, after); compile(body, name, 'exec')
                path = Path(directory)/(name+'.py'); path.write_text(body)
                result = subprocess.run([sys.executable,'-B','-m','unittest','test_n71_i2c_trace_command.TraceCommand.'+method],
                    env=dict(os.environ,N71_I2C_TRACE_SCRIPT=str(path),PYTHONPATH=str(ROOT/'tests'),PYTHONDONTWRITEBYTECODE='1'),
                    capture_output=True,text=True,timeout=20)
                self.assertNotEqual(result.returncode,0,name+result.stderr)
                self.assertIn('AssertionError',result.stderr,name+result.stderr); self.assertNotIn('ERROR:',result.stderr)
                print('I2C_TRACE_ASSERTION_KILL '+name,flush=True)


if __name__ == '__main__': unittest.main()
