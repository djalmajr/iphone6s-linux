"""Replay the observed first refusal and reject unproved or changed readbacks."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import test_n71_resource_result as fixture
import test_n71_resource_stage as journal_fixture
import n71_resource_stage

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_readback.py'
SPEC = importlib.util.spec_from_file_location('readback_under_test', os.environ.get('N71_READBACK_SCRIPT', SOURCE))
READBACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READBACK)
fixture.RESOURCE.n71_resource_readback = READBACK
REPORT = ('N71_PCIE_ASSIGN_READBACK failed=1 root=1 where=030 size=4 value=0000ffff before=00000000 '
          'after_valid=1 after=00000000 write_error=0 read_error=0; no additional IO\n')
ABSENT = ('N71_PCIE_ASSIGN_READBACK failed=0 root=0 where=000 size=0 value=00000000 before=00000000 '
          'after_valid=0 after=00000000 write_error=0 read_error=0; no additional IO\n')
REFUSAL = 'N71_PCIE_SCAN_WRITE_REFUSED bus=0 devfn=08 where=030 size=4 value=0000ffff error=-5\n'


def logs(report=REPORT, *, error=-5):
    active, closed = fixture.failed()
    result = next(line + '\n' for line in active.splitlines() if line.startswith('N71_PCIE_RESOURCE_RESULT '))
    values = REFUSAL + report + result
    return tuple(text.replace(result, values).replace('-13', str(error)).replace('error=-5', 'error=' + str(error))
                 for text in (active, closed))


class ResourceReadbackTests(unittest.TestCase):
    def test_first_failed_value_survives_assignment_and_cleanup(self):
        # Mutations killed: discard the first readback, omit the selected requirement, or accept a changed history.
        active, closed = logs()
        assignment = fixture.RESOURCE.outcome(active)
        self.assertEqual(assignment['event'].get('write_readback'), dict(failed=1, root=1, where=48, size=4,
                         value=65535, before=0, after_valid=1, after=0, write_error=0, read_error=0))
        self.assertFalse(assignment['assignment_verified'])
        self.assertEqual(fixture.RESOURCE.cleanup(closed, assignment)['assignment_error'], -5)
        selected = SimpleNamespace(modules=[({'module': 'n71-pcie-diagnostic.ko', 'assignment_readback': True}, b'')])
        n71_resource_stage.verify_readback(selected, active)
        with self.assertRaises(ValueError):
            n71_resource_stage.verify_readback(selected, active.replace(REPORT, ''))
        for bad in (closed.replace(REPORT, ''), closed.replace('after=00000000', 'after=00000001')):
            with self.assertRaises(ValueError):
                fixture.RESOURCE.cleanup(bad, assignment)

    def test_raw_callback_errors_never_prove_a_readback(self):
        # Mutations killed: normalize away raw errors, accept invalid values, or claim a read after write failure.
        for field in ('write_error', 'read_error'):
            for error in (-67, 7):
                report = REPORT.replace('after_valid=1', 'after_valid=0').replace(field + '=0', field + '=' + str(error))
                active, closed = logs(report, error=error if error < 0 else -5)
                assignment = fixture.RESOURCE.outcome(active)
                observed = assignment['event'].get('write_readback')
                self.assertIsInstance(observed, dict)
                self.assertEqual(observed[field], error)
                self.assertEqual((observed['after_valid'], observed['after']), (0, 0))
                self.assertEqual(fixture.RESOURCE.cleanup(closed, assignment)['assignment_error'], error if error < 0 else -5)
                for bad in (report.replace('after_valid=0', 'after_valid=1'),
                            report.replace('after=00000000', 'after=deadbeef')):
                    with self.assertRaises(ValueError):
                        fixture.RESOURCE.outcome(logs(bad, error=error if error < 0 else -5)[0])
        report = REPORT.replace('after_valid=1', 'after_valid=0').replace('write_error=0', 'write_error=-67').replace('read_error=0', 'read_error=-67')
        with self.assertRaises(ValueError):
            fixture.RESOURCE.outcome(logs(report, error=-67)[0])

    def test_report_is_unique_complete_and_in_the_original_phase(self):
        # Mutations killed: accept missing/partial/duplicate records, a reordered record or a later refusal.
        active, _ = logs()
        bad_texts = [active + REPORT, active.replace(REPORT, REPORT.rstrip() + ' garbage\n'),
                     REPORT + active.replace(REPORT, ''), active.replace(REPORT, '') + REPORT,
                     active.replace('N71_PCIE_ASSIGN_READBACK', 'N71_PCIE_ASSIGN_UNKNOWN'),
                     active.replace(REFUSAL, ''), active.replace(REFUSAL, REFUSAL.replace('where=030', 'where=020')),
                     active.replace(REFUSAL, REFUSAL.replace('bus=0 devfn=08', 'bus=1 devfn=00')),
                     active.replace(REFUSAL, REFUSAL.replace('error=-5', 'error=-67')),
                     active.replace(REFUSAL, REFUSAL.rstrip() + ' garbage\n'),
                     active.replace(REFUSAL, '') + REFUSAL]
        for text in bad_texts:
            with self.subTest(text=text), self.assertRaises(ValueError):
                fixture.RESOURCE.outcome(text)
        with self.assertRaises(ValueError):
            fixture.RESOURCE.event(active.replace(REPORT, ''), readback_required=True)
        with self.assertRaises(ValueError):
            fixture.RESOURCE.event(REPORT)

    def test_values_error_and_write_budget_must_agree(self):
        # Mutations killed: accept invented validity/no-op, invalid width, different error or no attempted write.
        for before, after in (('before=00000000', 'before=0000ffff'), ('after_valid=1', 'after_valid=0'),
                              ('after=00000000', 'after=0000ffff'), ('write_error=0', 'write_error=-4096'),
                              ('where=030', 'where=031'), ('size=4', 'size=0'),
                              ('size=4', 'size=2'), ('root=1', 'root=0')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                fixture.RESOURCE.outcome(logs(REPORT.replace(before, after))[0])
        with self.assertRaises(ValueError):
            fixture.RESOURCE.outcome(logs(error=-67)[0])
        active, _ = logs()
        with self.assertRaises(ValueError):
            fixture.RESOURCE.event(active.replace('N71_PCIE_RESOURCE_RESULT error=-5',
                                                  'N71_PCIE_RESOURCE_RESULT error=-67'))
        for before, after in (('where=030', 'where=031'), ('where=030', 'where=ffc')):
            with self.assertRaises(ValueError):
                fixture.RESOURCE.outcome(active.replace(before, after))
        with self.assertRaises(ValueError):
            fixture.RESOURCE.outcome(active.replace('attempts=12', 'attempts=8'))

    def test_legacy_records_and_absent_failure_have_distinct_contracts(self):
        # Mutations killed: require a fictitious legacy readback or allow invented absent-failure fields.
        self.assertNotIn('write_readback', fixture.RESOURCE.event(fixture.OPEN))
        positive = fixture.OPEN.replace(fixture.RESULT, ABSENT + fixture.RESULT)
        self.assertEqual(fixture.RESOURCE.event(positive, readback_required=True).get('write_readback', {}).get('failed'), 0)
        for field in ('root=0', 'where=000', 'size=0', 'value=00000000', 'before=00000000', 'after_valid=0',
                      'after=00000000', 'write_error=0', 'read_error=0'):
            before, value = field.split('=')
            changed = before + '=' + ('1'.zfill(len(value)))
            with self.assertRaises(ValueError):
                fixture.RESOURCE.event(positive.replace(field, changed))
        with self.assertRaises(ValueError):
            fixture.RESOURCE.event(positive, readback_required=1)


class ReadbackMutationsTests(unittest.TestCase):
    def test_contract_mutations_fail_by_assertion(self):
        variants = {
            'required-record-lost': ('not required or result is None', 'True'),
            'unknown-record-accepted': ("text.count('N71_PCIE_ASSIGN_')", "text.count('N71_PCIE_ASSIGN_READBACK ')"),
            'absent-fields-invented': ('not any(data.values())', 'True'),
            'record-after-result': ("< text.index('N71_PCIE_RESOURCE_RESULT ')", '< len(text)'),
            'width-check-lost': ("size in (2, 4) and data['where'] <= 0xfc and data['where'] % size == 0", 'True'),
            'noop-accepted': ("data['before'] != data['value']", 'True'),
            'callback-validity-invented': ("not data['after_valid'] and data['after'] == 0", 'True'),
            'read-after-failed-write': ('(not write or read == 0)', 'True'),
            'equal-readback-accepted': ("data['after'] != data['value']", 'True'),
            'assignment-error-lost': ("result['error'] == error", 'True'),
            'verified-write-budget': ("result['writes'] < result['attempts']", 'True'),
            'first-refusal-scope': ("0 if data['root'] else 1, 8 if data['root'] else 0", 'int(bus), int(devfn, 16)'),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-readback-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_READBACK_SCRIPT=str(path))
                run = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                      '-p', 'test_n71_resource_readback.py', '-k', 'ResourceReadbackTests'],
                                     cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = run.stdout + run.stderr
                self.assertNotEqual(run.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_RESOURCE_READBACK_ASSERTION_KILL', name, flush=True)

    def test_selected_contract_and_saved_measurement_mutations(self):
        variants = (
            ('selected-contract-lost', 'n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT',
             "required = records[0].get('assignment_readback', False)", 'required = False'),
            ('assignment-verification-lost', 'n71_resource_stage.py', 'N71_RESOURCE_STAGE_SCRIPT',
             'verify_readback(session, process.stdout)', 'pass'),
            ('saved-readback-lost', 'n71_resource_result.py', 'N71_RESOURCE_RESULT_SCRIPT',
             "result['write_readback'] = readback", 'pass'),
        )
        with tempfile.TemporaryDirectory(prefix='n71-readback-selected-') as directory:
            for name, module, variable, before, after in variants:
                source = (ROOT / 'scripts/host' / module).read_text()
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **{variable: str(path)})
                run = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                      '-p', 'test_n71_resource_readback.py', '-k', 'ResourceReadback'],
                                     cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = run.stdout + run.stderr
                self.assertNotEqual(run.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_RESOURCE_READBACK_STAGE_ASSERTION_KILL', name, flush=True)


class ResourceReadbackJournalTests(unittest.TestCase):
    setUp = journal_fixture.ResourceStageTests.setUp
    execute = journal_fixture.ResourceStageTests.execute
    acquired = journal_fixture.ResourceStageTests.acquired

    def test_negative_readback_survives_private_checkpoint_reuse_and_release(self):
        # Mutation killed: drop required readback verification or omit it from the durable assignment event.
        next(record for record, _ in self.modules if record['module'] == 'n71-pcie-diagnostic.ko')['assignment_readback'] = True
        self.phone.assignment_error = -5

        def report(phone, session, text):
            original = next(line for line in phone.history.splitlines(keepends=True)
                            if 'N71_PCIE_RESOURCE_RESULT ' in line)
            prefix = journal_fixture.held_fixture.timestamp(REFUSAL + REPORT, 58)
            phone.history = phone.history.replace(original, prefix + original)
            return 1, text.replace(original, prefix + original)

        self.phone.overrides['held-assign'] = report
        code, assigned, source = self.execute('readback-assign', self.acquired(), assign=True)
        self.assertEqual(code, 1)
        self.assertTrue(assigned.result['held_verified'])
        state = json.loads((source / 'held-state-private.json').read_text())
        measured = state['result']['resource_assignment']['event']['write_readback']
        self.assertEqual((measured['after_valid'], measured['after']), (1, 0))
        proof = source / (journal_fixture.STAGE.PROOF + '-proof-private.log')
        self.assertIn(REPORT, proof.read_text())
        code, reused, continuation = self.execute('readback-reuse', source, assign=True)
        self.assertEqual(code, 1)
        self.assertTrue(reused.result['resource_assignment_reused'])
        self.assertEqual(self.phone.assignments, 1)
        code, released, _ = self.execute('readback-release', continuation)
        self.assertEqual(code, 1)
        self.assertTrue(released.result['cleanup_verified'])
        self.assertEqual(released.result['resource_assignment']['event']['write_readback'], measured)
        self.assertFalse(self.phone.pcie or self.phone.reg or self.phone.active)

    def test_selected_readback_module_cannot_save_an_incomplete_proof(self):
        # Mutation killed: accept a legacy-format log from a module that promises a readback report.
        next(record for record, _ in self.modules if record['module'] == 'n71-pcie-diagnostic.ko')['assignment_readback'] = True
        code, session, source = self.execute('missing-report', self.acquired(), assign=True)
        self.assertEqual(code, 1)
        self.assertIsNone(session.resource_assignment)
        self.assertFalse((source / (journal_fixture.STAGE.PROOF + '-proof-private.log')).exists())
        self.assertTrue(self.phone.pcie and self.phone.reg and self.phone.active)


if __name__ == '__main__':
    unittest.main()
