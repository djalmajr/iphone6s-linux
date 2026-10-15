"""Wire contracts and real local reader lifetimes; no phone, firmware or SSH."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_dma_observation as wire

SOURCE = ROOT / 'scripts/host/n71_dma_collector.py'
spec = importlib.util.spec_from_file_location('dma_collector_subject', os.environ.get('N71_DMA_COLLECTOR_SCRIPT', SOURCE))
subject = importlib.util.module_from_spec(spec); spec.loader.exec_module(subject)
WIRE_SOURCE = ROOT / 'scripts/host/n71_dma_observation.py'
if os.environ.get('N71_DMA_WIRE_SCRIPT'):
    spec = importlib.util.spec_from_file_location('dma_wire_subject', os.environ['N71_DMA_WIRE_SCRIPT'])
    wire = importlib.util.module_from_spec(spec); spec.loader.exec_module(wire)
    subject.wire = wire

BOOT = '01234567-89ab-cdef-0123-456789abcdef'
READY = f'N71_DMA_OBSERVER_READY boot={BOOT} release={wire.RELEASE} interval=1 count=20\n'


def row(index, *, physical=0x800000028, valid=0x3ff, time_ns=None, command=0, last=0):
    return (f'sample={index} time_ns={100 + index if time_ns is None else time_ns} '
        f'pa={physical:016x} valid={valid:08x} command={command:08x} tcr=00000080 '
        f'error=80000102 error_addr=3ffff028 ttbr=00000001,00000002,00000003,{last:08x}\n')


def frame(index, *, physical=0x800000028, error=0, complete=2, stable=1, valid=0x3ff):
    return (f'N71_DMA_FRAME_BEGIN index={index}\nrequested=1 iova=000000003ffff028 '
        f'complete={complete} stable={stable} error={error}\n'
        + row(0, physical=physical, valid=valid, time_ns=100 + index * 2)
        + row(1, physical=physical, valid=valid, time_ns=101 + index * 2)
        + f'N71_DMA_FRAME_END index={index}\n')


class WireTests(unittest.TestCase):
    def test_full_frames_zero_mapping_and_error_values_are_preserved(self):
        raw = READY + ''.join(frame(i, physical=0) for i in range(20)) + 'N71_DMA_OBSERVER_DONE count=20\n'
        value = wire.parse(raw.encode(), BOOT)
        self.assertTrue(value['done']); self.assertFalse(value['truncated'])
        self.assertEqual(value['stable_mappings'], 0)
        self.assertFalse(value['hardware_translation_proved'])
        self.assertEqual(value['frames'][0]['samples'][0]['words'][2:4], [0x80000102, 0x3ffff028])
        raw = READY + frame(0, complete=0, stable=0, error=-13, valid=0)
        value = wire.parse(raw.encode(), BOOT)
        self.assertEqual(value['frames'][0]['error'], -13); self.assertTrue(value['truncated'])

    def test_partial_full_mask_and_reverse_clock_error_do_not_invent_success(self):
        body = 'requested=1 iova=000000003ffff028 complete=0 stable=0 error=-5\n'
        body += row(0, last=0xffffffff) + row(1, valid=0)
        value = wire.observation(body.splitlines())
        self.assertEqual(value['samples'][0]['valid'], 0x3ff)
        self.assertEqual(value['samples'][0]['words'][-1], 0xffffffff)
        body = 'requested=1 iova=000000003ffff028 complete=2 stable=0 error=-11\n'
        body += row(0, time_ns=200) + row(1, time_ns=100)
        text = READY + 'N71_DMA_FRAME_BEGIN index=0\n' + body + 'N71_DMA_FRAME_END index=0\n'
        value = wire.parse(text.encode(), BOOT)
        self.assertFalse(value['clock_monotonic']); self.assertFalse(value['frames'][0]['stable'])

    def test_forged_scope_order_masks_and_success_are_rejected(self):
        good = READY + frame(0)
        bad = [good.replace(BOOT, '11234567-89ab-cdef-0123-456789abcdef'),
            good.replace('interval=1 count=20', 'interval=1 count=100'),
            good.replace('index=0', 'index=1'), good.replace('valid=000003ff', 'valid=000007ff'),
            good.replace('complete=2', 'complete=1'), good.replace('stable=1', 'stable=0'),
            good.replace('error=0\n', 'error=-5\n', 1), good.replace('command=00000000', 'command=00000008'),
            good.replace('sample=1', 'sample=0'), good.replace('pa=0000000800000028', 'pa=0000001000000028'),
            good + 'N71_DMA_OBSERVER_DONE count=20\n']
        bad.append((READY + frame(0, complete=0, stable=0, error=-13, valid=0x7ff)))
        for text in bad:
            with self.subTest(text=text[:160]), self.assertRaises(ValueError): wire.parse(text.encode(), BOOT)
        for raw in (b'x' * (wire.LIMIT + 1), b'\xff'):
            with self.assertRaises(ValueError): wire.parse(raw, BOOT)
        with self.assertRaises(ValueError): wire.command(BOOT + '; touch /tmp/injected')

    def test_truncation_keeps_only_finished_frames(self):
        text = READY + frame(0) + 'N71_DMA_FRAME_BEGIN index=1\nrequested=1'
        value = wire.parse(text.encode(), BOOT)
        self.assertEqual(len(value['frames']), 1); self.assertTrue(value['truncated'])

    def test_generated_shell_executes_both_budgets_and_refuses_wrong_scope(self):
        with tempfile.TemporaryDirectory(prefix='n71-dma-wire-') as directory:
            root = Path(directory); params = root / 'parameters'; params.mkdir()
            boot = root / 'boot'; boot.write_text(BOOT + '\n')
            for name in ('driver_runtime', 'iommu_parent', 'msi_parent', 'scan_hold', 'dma_observe'):
                (params / name).write_text('Y\n')
            (params / 'held').write_text('held=1\n'); (params / 'dma_iova').write_text('1073737768\n')
            (params / 'dma_observation').write_text('\n'.join(frame(0).splitlines()[1:4]) + '\n')
            binary = root / 'bin'; binary.mkdir()
            for name, body in [('id', 'echo 0'), ('uname', 'echo ' + wire.RELEASE)]:
                path = binary / name; path.write_text('#!/bin/sh\n' + body + '\n'); path.chmod(0o700)
            command = wire.command(BOOT).replace('/proc/sys/kernel/random/boot_id', str(boot)).replace(
                '/sys/module/n71_pcie_diagnostic/parameters', str(params))
            hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in params.iterdir()}
            for fractional, count in ((True, 100), (False, 20)):
                sleep = binary / 'sleep'; sleep.write_text('#!/bin/sh\n' + ('exit 0\n' if fractional
                    else 'test "$1" != 0.1\n')); sleep.chmod(0o700)
                process = subprocess.run(['/bin/sh', '-c', command], capture_output=True, timeout=10,
                    env=dict(os.environ, PATH=str(binary) + ':/usr/bin:/bin'))
                self.assertEqual(process.returncode, 0, process.stderr)
                value = wire.parse(process.stdout, BOOT)
                self.assertTrue(value['done']); self.assertEqual(len(value['frames']), count)
            self.assertEqual(hashes, {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in params.iterdir()})
            boot.write_text('11234567-89ab-cdef-0123-456789abcdef\n')
            process = subprocess.run(['/bin/sh', '-c', command], capture_output=True, timeout=10,
                env=dict(os.environ, PATH=str(binary) + ':/usr/bin:/bin'))
            self.assertNotEqual(process.returncode, 0); self.assertNotIn(b'OBSERVER_READY', process.stdout)


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='n71-dma-process-'); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.root.chmod(0o700)
        self.pidfile = self.root / 'child-pid'; self.gate = self.root / 'published'

    def start(self, body, *, accepted=True):
        child = self.root / 'child.py'
        child.write_text('import os,sys,time\nfrom pathlib import Path\n'
            + f'Path({str(self.pidfile)!r}).write_text(str(os.getpid()))\n' + body)
        try:
            return subject.Collector({'boot': BOOT, 'output': self.root, 'ssh': [sys.executable, '-u', str(child)]})
        except (ValueError, OSError) as error:
            if accepted:
                self.fail('Local reader contract refused: ' + str(error))
            raise

    def dead(self):
        pid = int(self.pidfile.read_text())
        with self.assertRaises(ProcessLookupError): os.kill(pid, 0)

    def test_ready_precedes_publish_and_finished_process_is_reaped(self):
        first = READY + frame(0, complete=0, stable=0, error=-13, valid=0)
        rest = ''.join(frame(i) for i in range(1, 20)) + 'N71_DMA_OBSERVER_DONE count=20\n'
        collector = self.start(f'print({first!r},end="",flush=True)\n'
            + f'while not Path({str(self.gate)!r}).exists(): time.sleep(0.01)\n'
            + f'print({rest!r},end="",flush=True)\n')
        self.addCleanup(collector.close)
        self.assertFalse(self.gate.exists()); self.assertIsNone(collector.process.poll())
        self.gate.write_text('published')
        result = collector.finish(); self.dead()
        self.assertEqual(result['exit'], 0); self.assertFalse(result['timed_out'])
        self.assertEqual(len(result['observation']['frames']), 20)
        self.assertEqual(result['observation']['stable_mappings'], 19)
        self.assertEqual(result['sha256'], hashlib.sha256(collector.path.read_bytes()).hexdigest())
        self.assertEqual(collector.path.stat().st_mode & 0o777, 0o600)
        collector.close()
        with self.assertRaises(FileExistsError): self.start('print("must not start")\n', accepted=False)

    def test_timeout_reaps_reader_and_preserves_partial_observation(self):
        collector = self.start(f'print({(READY + frame(0))!r},end="",flush=True)\ntime.sleep(10)\n')
        self.addCleanup(collector.close); collector.deadline = time.monotonic() + 0.05
        result = collector.finish(); self.dead()
        self.assertTrue(result['timed_out']); self.assertLess(result['exit'], 0)
        self.assertEqual(len(result['observation']['frames']), 1); self.assertTrue(collector.closed)

    def test_missing_ready_reaps_owned_process_and_preserves_output(self):
        with patch.object(subject, 'READY_SECONDS', 0.1), self.assertRaises(ValueError):
            self.start('print("",end="",flush=True)\ntime.sleep(10)\n', accepted=False)
        self.dead(); self.assertTrue((self.root / 'dma-observer-private.log').exists())

    def test_byte_overflow_reaps_reader_without_discarding_private_file(self):
        collector = self.start(f'print({READY!r},end="",flush=True)\n'
            + f'while not Path({str(self.gate)!r}).exists(): time.sleep(0.01)\n'
            + f'print("x" * {wire.LIMIT + 1},flush=True)\ntime.sleep(10)\n')
        self.addCleanup(collector.close); self.gate.write_text('published')
        with self.assertRaises(ValueError): collector.finish()
        self.dead(); self.assertGreater(collector.path.stat().st_size, wire.LIMIT)


@unittest.skipIf(os.environ.get('N71_DMA_COLLECTOR_SCRIPT') or os.environ.get('N71_DMA_WIRE_SCRIPT'), 'Mutation child')
class Mutations(unittest.TestCase):
    def test_scope_budgets_stability_and_reap_mutations_fail_by_assertion(self):
        variants = [
            ('boot', WIRE_SOURCE, 'N71_DMA_WIRE_SCRIPT', 'match is not None and match[1] == boot', 'match is not None', 'WireTests.test_forged_scope_order_masks_and_success_are_rejected'),
            ('mask', WIRE_SOURCE, 'N71_DMA_WIRE_SCRIPT', 'valid <= 0x3ff', 'True', 'WireTests.test_forged_scope_order_masks_and_success_are_rejected'),
            ('zero-pa', WIRE_SOURCE, 'N71_DMA_WIRE_SCRIPT', "frame['samples'][0]['physical'] != 0", 'True', 'WireTests.test_full_frames_zero_mapping_and_error_values_are_preserved'),
            ('hardware-proof', WIRE_SOURCE, 'N71_DMA_WIRE_SCRIPT', "'hardware_translation_proved': False", "'hardware_translation_proved': True", 'WireTests.test_full_frames_zero_mapping_and_error_values_are_preserved'),
            ('private-mode', SOURCE, 'N71_DMA_COLLECTOR_SCRIPT', 'os.O_EXCL, 0o600', 'os.O_EXCL, 0o644', 'ProcessTests.test_ready_precedes_publish_and_finished_process_is_reaped'),
            ('partial-loss', SOURCE, 'N71_DMA_COLLECTOR_SCRIPT', "'timed_out': timed_out", "'timed_out': False", 'ProcessTests.test_timeout_reaps_reader_and_preserves_partial_observation'),
        ]
        with tempfile.TemporaryDirectory(prefix='n71-dma-collector-mutations-') as directory:
            for name, source, variable, before, after, method in variants:
                body = source.read_text(); self.assertEqual(body.count(before), 1, name)
                body = body.replace(before, after, 1); compile(body, name, 'exec')
                path = Path(directory) / (name + '.py'); path.write_text(body)
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'test_n71_dma_collector.' + method],
                    env=dict(os.environ, **{variable: str(path)}, PYTHONPATH=str(ROOT / 'tests'), PYTHONDONTWRITEBYTECODE='1'),
                    capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode, 0, name + result.stdout + result.stderr)
                self.assertIn('AssertionError', result.stderr, name + result.stderr)
                self.assertNotIn('ERROR:', result.stderr, name + result.stderr)
                print('DMA_COLLECTOR_ASSERTION_KILL ' + name, flush=True)


if __name__ == '__main__':
    unittest.main()
