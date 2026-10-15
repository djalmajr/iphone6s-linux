"""Replay typed readbacks and refuse invented capability, scope or counters."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename, variable):
    source = ROOT / 'scripts/host' / filename
    spec = importlib.util.spec_from_file_location(name, os.environ.get(variable, source))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREF64 = load('pref64_under_test', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT')
READBACK = load('typed_readback_under_test', 'n71_resource_readback.py', 'N71_READBACK_SCRIPT')
HELD = 'N71_PCIE_SESSION_HELD ready=1\n'
OPTIONAL = 'N71_PCIE_OPTIONAL_WINDOWS captured=1 io_absent=0 pref_absent=0 io_noops=0 pref_noops=0; absent ranges are emulated without hardware writes\n'
IO16 = 'N71_PCIE_IO16_UPPER captured=1 enabled=1 noops=1; temporary upper disable without hardware write\n'
REPORT = 'N71_PCIE_PREF64_DISABLE captured=1 enabled=1 writes=1; full disabled readback with preserved types\n'
ABSENT = 'N71_PCIE_ASSIGN_READBACK failed=0 root=0 where=000 size=0 value=00000000 before=00000000 after_valid=0 after=00000000 write_error=0 read_error=0; no additional IO\n'
RESULT = 'N71_PCIE_RESOURCE_RESULT error=0 assigned=1 pending=1 claimed=1 attempts=14 writes=5; no decode, bind or DMA\n'
POSITIVE = HELD + OPTIONAL + IO16 + REPORT + ABSENT + RESULT


def state(**changes):
    return dict(error=0, assigned=1, pending=1, claimed=1, attempts=14, writes=5,
                optional_windows=dict(pref_absent=0), io16_upper=dict(captured=1, enabled=1, noops=1)) | changes


def failed(*, after=0xfff0, write=0, read=0):
    raw_error = write or read
    error = raw_error if raw_error < 0 else -5
    report = ('N71_PCIE_ASSIGN_READBACK failed=1 root=1 where=024 size=4 value=0000fff0 '
              f'before=00010001 after_valid={int(not raw_error)} after={after:08x} '
              f'write_error={write} read_error={read} expected=0001fff1; no additional IO\n')
    refusal = f'N71_PCIE_SCAN_WRITE_REFUSED bus=0 devfn=08 where=024 size=4 value=0000fff0 error={error}\n'
    text = HELD + refusal + OPTIONAL + IO16 + REPORT.replace('writes=1;', 'writes=0;') + report + RESULT
    text = text.replace('error=0 assigned=1', f'error={error} assigned=0').replace('writes=5;', 'writes=4;')
    result = state(error=error, assigned=0, writes=4)
    result['pref64_disable'] = PREF64.parse(text, result, required=True)
    return text, result


class Pref64ContractTests(unittest.TestCase):
    def test_positive_empty_and_legacy_requirements(self):
        self.assertEqual(PREF64.parse(POSITIVE, state(), required=True), dict(captured=1, enabled=1, writes=1))
        self.assertIsNone(PREF64.parse('', None, required=True))
        self.assertIsNone(PREF64.parse(POSITIVE.replace(REPORT, ''), state()))
        empty = REPORT.replace('captured=1', 'captured=0').replace('enabled=1', 'enabled=0').replace('writes=1;', 'writes=0;')
        self.assertEqual(PREF64.parse(POSITIVE.replace(REPORT, empty),
                         state(assigned=0, pending=0, claimed=0, attempts=0, writes=0)),
                         dict(captured=0, enabled=0, writes=0))
        with self.assertRaises(ValueError):
            PREF64.parse('', None, required=1)

    def test_required_unique_complete_ordered_and_known_report(self):
        variants = [POSITIVE.replace(REPORT, ''), POSITIVE.replace(REPORT, REPORT * 2),
                    POSITIVE.replace('PREF64_DISABLE', 'PREF64_OTHER'),
                    POSITIVE.replace('writes=1;', 'writes=;'),
                    POSITIVE + 'N71_PCIE_PREF64_OTHER extra\n',
                    POSITIVE.replace(IO16 + REPORT, REPORT + IO16),
                    POSITIVE.replace(REPORT + ABSENT, ABSENT + REPORT),
                    POSITIVE.replace(REPORT, '') + REPORT]
        for text in variants:
            with self.assertRaises(ValueError):
                PREF64.parse(text, state(), required=True)
        for missing in ('optional_windows', 'io16_upper'):
            result = state(); del result[missing]
            with self.assertRaises(ValueError):
                PREF64.parse(POSITIVE, result)

    def test_capture_capability_and_verified_write_boundaries(self):
        variants = [POSITIVE.replace('PREF64_DISABLE captured=1', 'PREF64_DISABLE captured=0'),
                    POSITIVE.replace('PREF64_DISABLE captured=1 enabled=1', 'PREF64_DISABLE captured=1 enabled=0'),
                    POSITIVE.replace('writes=1;', 'writes=0;'), POSITIVE.replace('writes=1;', 'writes=6;')]
        for text in variants:
            with self.assertRaises(ValueError):
                PREF64.parse(text, state())
        for result in (state(pending=0), state(optional_windows=dict(pref_absent=1))):
            with self.assertRaises(ValueError):
                PREF64.parse(POSITIVE, result)

    def test_typed_failure_preserves_original_request_and_full_expectation(self):
        for after in (0xfff0, 0x10001):
            text, result = failed(after=after)
            row = READBACK.parse(text, result, required=True)
            self.assertEqual(row, dict(failed=1, root=1, where=36, size=4, value=65520, before=65537,
                             after_valid=1, after=after, write_error=0, read_error=0, expected=131057))
        for write, read in ((7, 0), (-67, 0), (0, 7), (0, -67)):
            text, result = failed(after=0, write=write, read=read)
            row = READBACK.parse(text, result)
            self.assertEqual((row['write_error'], row['read_error'], row['after_valid'], row['expected']),
                             (write, read, 0, 0x1fff1))
        text, result = failed(after=0x1fff1)
        with self.assertRaises(ValueError):
            READBACK.parse(text, result)

    def test_annotation_cannot_widen_scope_or_change_original_refusal(self):
        text, result = failed()
        variants = [text.replace(' expected=0001fff1', ''),
                    text.replace('expected=0001fff1', 'expected=0000fff0'),
                    text.replace('expected=0001fff1', 'expected=0001ffe1'),
                    text.replace('before=00010001', 'before=0001fff1'),
                    text.replace('before=00010001', 'before=00020001'),
                    text.replace('where=024', 'where=020'), text.replace('root=1', 'root=0'),
                    text.replace('where=024 size=4', 'where=024 size=2'),
                    text.replace('value=0000fff0', 'value=0000ffe0'),
                    text.replace('devfn=08', 'devfn=00'),
                    text.replace('after=0000fff0', 'after=00010001').replace('where=024', 'where=020')]
        for changed in variants:
            with self.assertRaises(ValueError):
                READBACK.parse(changed, result)
        for proof in (dict(captured=1, enabled=0, writes=0), dict(captured=0, enabled=1, writes=0), None):
            changed = dict(result)
            if proof is None: del changed['pref64_disable']
            else: changed['pref64_disable'] = proof
            with self.assertRaises(ValueError):
                READBACK.parse(text, changed)
        positive = POSITIVE.replace('read_error=0;', 'read_error=0 expected=00000000;')
        with self.assertRaises(ValueError):
            READBACK.parse(positive, state())
        legacy = text.replace(' expected=0001fff1', '').replace('after=0000fff0', 'after=0001fff1')
        row = READBACK.parse(legacy, state(error=-5, assigned=0, writes=4))
        self.assertNotIn('expected', row)
        self.assertEqual(row['after'], 0x1fff1)


class Pref64MutationsTests(unittest.TestCase):
    def test_contract_mutations_fail_by_assertion(self):
        variants = (
            ('required-proof', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', 'not required or result is None', 'True'),
            ('unknown-proof', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT',
             "text.count('N71_PCIE_PREF64_')", "text.count('N71_PCIE_PREF64_DISABLE ')"),
            ('prior-io16-proof', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', "and 'io16_upper' in result", 'and True'),
            ('proof-order', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT',
             "< text.index('N71_PCIE_ASSIGN_READBACK ') < text.index('N71_PCIE_RESOURCE_RESULT ')",
             "< text.index('N71_PCIE_RESOURCE_RESULT ') <= text.index('N71_PCIE_RESOURCE_RESULT ')"),
            ('capture-owner', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', "data['captured'] == result['pending']", 'True'),
            ('disabled-counter', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', "data['enabled'] or data['writes'] == 0", 'True'),
            ('absent-capability', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', "result['optional_windows']['pref_absent'] == 0", 'True'),
            ('write-budget', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', "data['writes'] <= result['writes']", 'True'),
            ('positive-write-proof', 'n71_resource_pref64.py', 'N71_PREF64_RESULT_SCRIPT', "data['writes'] > 0", 'True'),
            ('annotation-scope', 'n71_resource_readback.py', 'N71_READBACK_SCRIPT', '(annotation is not None) == typed', 'True'),
            ('annotation-capture', 'n71_resource_readback.py', 'N71_READBACK_SCRIPT', "result.get('pref64_disable', {}).get('captured') == 1", 'True'),
            ('annotation-baseline', 'n71_resource_readback.py', 'N71_READBACK_SCRIPT', "data['before'] == 0x10001", 'True'),
            ('annotation-full-expected', 'n71_resource_readback.py', 'N71_READBACK_SCRIPT', "data['expected'] == 0x1fff1", 'True'),
            ('typed-readback-mismatch', 'n71_resource_readback.py', 'N71_READBACK_SCRIPT', "data['after'] != expected if typed", 'True if typed'),
        )
        with tempfile.TemporaryDirectory(prefix='n71-pref64-contract-') as directory:
            for name, module, variable, before, after in variants:
                source = (ROOT / 'scripts/host' / module).read_text()
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
                environment.pop('N71_READBACK_SCRIPT', None); environment.pop('N71_PREF64_RESULT_SCRIPT', None)
                environment[variable] = str(path)
                p = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                    '-p', 'test_n71_resource_pref64.py', '-k', 'Pref64ContractTests'],
                                   cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = p.stdout + p.stderr
                self.assertNotEqual(p.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_PREF64_CONTRACT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
