"""A real local reader follows modeled driver publication and durable journals."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_n71_dma_collector as frames
import test_n71_driver_runtime_session as fixture

ROOT = fixture.ROOT
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_dma_collector as original_collector
import n71_driver_runtime_stage as original_stage
import n71_driver_runtime_session as original_session


def load(name, source, variable):
    spec = importlib.util.spec_from_file_location(name, os.environ.get(variable, source))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


COLLECTOR_SOURCE = ROOT / 'scripts/host/n71_dma_collector.py'
STAGE_SOURCE = ROOT / 'scripts/host/n71_driver_runtime_stage.py'
SESSION_SOURCE = ROOT / 'scripts/host/n71_driver_runtime_session.py'
COLLECTOR = load('journal_dma_collector', COLLECTOR_SOURCE, 'N71_DMA_JOURNAL_SCRIPT')
STAGE = load('journal_dma_stage', STAGE_SOURCE, 'N71_DMA_STAGE_SCRIPT'); STAGE.n71_dma_collector = COLLECTOR
SESSION = load('journal_dma_session', SESSION_SOURCE, 'N71_DMA_SESSION_SCRIPT'); SESSION.dma = COLLECTOR


class RuntimeJournal(unittest.TestCase):
    def setUp(self):
        case = fixture.RuntimeSessionTests('test_start_observe_and_stop_share_one_boot_and_preserve_origin')
        case.setUp(); self.addCleanup(case.doCleanups); self.case = case; case.subject = SESSION
        self.boot = case.session.result['boot_id']; self.enabled = True; self.fail_publish = False
        self.invalid_tail = False; self.gate = case.root / 'published'; self.pidfile = case.root / 'reader-pids'
        child = case.root / 'reader.py'
        ready = frames.READY.replace(frames.BOOT, self.boot)
        first = ready + frames.frame(0, complete=0, stable=0, error=-13, valid=0)
        rest = ''.join(frames.frame(i) for i in range(1, 20)) + 'N71_DMA_OBSERVER_DONE count=20\n'
        child.write_text('import os,sys,time\nfrom pathlib import Path\n'
            + f'with Path({str(self.pidfile)!r}).open("a") as f: f.write(str(os.getpid())+"\\n")\n'
            + f'print({first!r},end="",flush=True)\n'
            + f'while not Path({str(self.gate)!r}).exists(): time.sleep(0.01)\n'
            + f'if Path({str(case.root / "invalid-tail")!r}).exists(): sys.stdout.buffer.write(b"\\xff"); sys.stdout.flush()\n'
            + f'else: print({rest!r},end="",flush=True)\n')
        self.prefix = [sys.executable, '-u', str(child)]
        restored = case.case.restored
        def restore(output):
            session = restored(output); session.ssh = self.prefix + ['root@' + COLLECTOR.device_profile.PHONE]
            return session
        case.case.restored = restore
        capture = case.capture
        def phone_capture(name, command):
            if name.startswith('driver-runtime-') and name.endswith('-publish'):
                if self.enabled:
                    raw = case.session.output / 'dma-observer-private.log'
                    self.assertIn('N71_DMA_OBSERVER_READY', raw.read_text())
                    self.assertTrue(self.pidfile.exists())
                    if self.invalid_tail: (case.root / 'invalid-tail').write_text('yes')
                    self.gate.write_text('publish observed')
                result = capture(name, command)
                if self.fail_publish: raise OSError('publish transport lost')
                return result
            return capture(name, command)
        case.capture = phone_capture
        hooks = [patch.object(COLLECTOR.profile, 'observer_parameters', side_effect=lambda *a: ' qualified' if self.enabled else ''),
            patch.object(COLLECTOR.device_profile, 'ssh_options', side_effect=lambda *a: list(self.prefix)),
            patch.object(original_stage, 'extra_proofs', STAGE.extra_proofs),
            patch.object(original_stage, 'load_source', STAGE.load_source),
            patch.object(original_session, 'dma', COLLECTOR), patch.object(original_collector, 'profile', COLLECTOR.profile)]
        for hook in hooks: hook.start(); self.addCleanup(hook.stop)

    def data(self):
        return json.loads((self.case.source / 'held-state-private.json').read_text())

    def dead(self):
        for text in self.pidfile.read_text().splitlines():
            with self.assertRaises(ProcessLookupError): os.kill(int(text), 0)

    def test_start_resume_observe_stop_copy_and_validate_the_registered_capture(self):
        self.case.accepted('start'); initial = self.data(); self.dead()
        receipt = initial['result']['dma_observer']; self.assertEqual(receipt['exit'], 0)
        self.assertEqual(receipt['observation']['stable_mappings'], 19)
        self.assertIn(COLLECTOR.STAGE, initial['proofs'])
        original = (self.case.source / 'dma-observer-proof-private.log').read_bytes()
        for action in ('observe', 'start', 'stop'):
            self.case.accepted(action)
            self.assertEqual(self.data()['result']['dma_observer'], receipt)
            self.assertEqual((self.case.source / 'dma-observer-proof-private.log').read_bytes(), original)
        self.assertEqual(len(self.pidfile.read_text().splitlines()), 1)
        self.assertTrue(self.case.session.result['cleanup_verified'])

    def test_receipt_tampering_is_refused_before_another_driver_effect(self):
        self.case.accepted('start'); before = list(self.case.effects()); path = self.case.source / 'held-state-private.json'
        data = self.data(); data['result']['dma_observer']['observation']['hardware_translation_proved'] = True
        path.write_text(json.dumps(data)); path.chmod(0o600)
        with self.assertRaises(ValueError): self.case.run_action('stop')
        self.assertEqual(self.case.effects(), before); self.dead()

    def test_cross_boot_receipt_and_unqualified_proof_are_refused(self):
        self.case.accepted('start'); data = self.data()
        raw = (self.case.source / 'dma-observer-proof-private.log').read_text()
        data['result']['dma_observer']['boot_id'] = frames.BOOT
        with self.assertRaises(ValueError): COLLECTOR.saved(self.case.session, data, {COLLECTOR.STAGE: raw})
        self.enabled = False
        with self.assertRaises(ValueError): STAGE.extra_proofs(self.case.session, data)
        self.dead()

    def test_primary_publish_failure_survives_capture_failure_and_child_is_reaped(self):
        self.fail_publish = True; self.invalid_tail = True
        with self.assertRaisesRegex(OSError, '^publish transport lost$'): self.case.run_action('start')
        self.dead()
        self.assertIn('dma_observer_error', self.case.session.result)
        self.assertIn('publish transport lost', self.case.session.result['driver_coordinator_error'])
        self.assertTrue((self.case.session.output / 'dma-observer-private.log').exists())

    def test_legacy_runtime_does_not_launch_a_reader_or_write_dma_receipts(self):
        self.enabled = False
        self.case.accepted('start'); self.case.accepted('stop')
        self.assertFalse(self.pidfile.exists())
        self.assertNotIn('dma_observer', self.data()['result'])

    def test_changed_ssh_identity_refuses_before_launch_and_publish(self):
        self.prefix.append('changed-after-pinning')
        with patch.object(COLLECTOR.device_profile, 'ssh_options', return_value=['different-client']):
            with self.assertRaises(ValueError): self.case.run_action('start')
        self.assertFalse(self.pidfile.exists())
        self.assertFalse(any(name.endswith('-publish') for name in self.case.effects()))


@unittest.skipIf(any(os.environ.get(name) for name in ('N71_DMA_JOURNAL_SCRIPT','N71_DMA_STAGE_SCRIPT','N71_DMA_SESSION_SCRIPT')), 'Mutation child')
class Mutations(unittest.TestCase):
    def test_registration_validation_and_publication_route_mutations_fail_by_assertion(self):
        variants = [
            ('receipt', COLLECTOR_SOURCE, 'N71_DMA_JOURNAL_SCRIPT',
             'json.dumps(value, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True)', 'True',
             'test_receipt_tampering_is_refused_before_another_driver_effect'),
            ('load-validation', STAGE_SOURCE, 'N71_DMA_STAGE_SCRIPT',
             '    n71_dma_collector.saved(session, data, proofs)', '    pass',
             'test_receipt_tampering_is_refused_before_another_driver_effect'),
            ('proof-registration', STAGE_SOURCE, 'N71_DMA_STAGE_SCRIPT',
             ' + n71_dma_collector.proof_names(session, data)', ' + ()',
             'test_start_resume_observe_stop_copy_and_validate_the_registered_capture'),
            ('publish-route', SESSION_SOURCE, 'N71_DMA_SESSION_SCRIPT',
             'dma.collecting(session, journal, session.output.parent.parent)', "__import__('contextlib').nullcontext()",
             'test_start_resume_observe_stop_copy_and_validate_the_registered_capture'),
            ('ssh-identity', COLLECTOR_SOURCE, 'N71_DMA_JOURNAL_SCRIPT',
             "session.ssh == device_profile.ssh_options(selected_root) + ['root@' + device_profile.PHONE]", 'True',
             'test_changed_ssh_identity_refuses_before_launch_and_publish'),
        ]
        import tempfile
        with tempfile.TemporaryDirectory(prefix='n71-dma-journal-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                body = source.read_text(); self.assertEqual(body.count(before), 1, name)
                body = body.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory) / (name + '.py'); path.write_text(body)
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_n71_dma_runtime_journal.RuntimeJournal.' + method],
                    env=dict(os.environ, **{variable: str(path)}, PYTHONPATH=str(ROOT / 'tests'), PYTHONDONTWRITEBYTECODE='1'),
                    capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0, name + result.stderr)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('DMA_JOURNAL_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
