"""Assignment must retain its owners and prove extra rollback before release."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import test_n71_scan_held_result as fixture

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/host/n71_resource_result.py'
SPEC = importlib.util.spec_from_file_location('resource_result_under_test',
                                             os.environ.get('N71_RESOURCE_RESULT_SCRIPT', SOURCE))
RESOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RESOURCE)
ACTION = 'N71_PCIE_RESOURCE_ACTION exit=0\n'
RESULT = ('N71_PCIE_RESOURCE_RESULT error=0 assigned=1 pending=1 claimed=1 attempts=12 writes=8; '
          'no decode, bind or DMA\n')
GETTER = 'N71_PCIE_RESOURCES ready=1 attempted=1 assigned=1 pending=1 claimed=1 active=0 error=0\n'
EMPTY = 'N71_PCIE_RESOURCES ready=0 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=0\n'
RESTORE = 'N71_PCIE_RESOURCE_RESTORED error=0 pending=0\n'
RELEASE = 'N71_PCIE_RESOURCE_WINDOW_RELEASED claimed=0\n'
OPEN = fixture.OPEN + RESULT + ACTION + GETTER
CLOSED = (fixture.CLOSED.replace(fixture.REMOVED, RESULT + fixture.REMOVED + RESTORE)
          .replace(fixture.CONFIG, fixture.CONFIG + RELEASE) + EMPTY)


def failed(*, pending=1, claimed=1):
    result = (RESULT.replace('error=0 assigned=1', 'error=-13 assigned=0')
              .replace('pending=1 claimed=1', f'pending={pending} claimed={claimed}'))
    if not claimed:
        result = result.replace('attempts=12 writes=8', 'attempts=0 writes=0')
    active = (fixture.OPEN.replace(fixture.ACTIVE, fixture.ACTIVE.replace('primary_error=0', 'primary_error=-13'))
              + result + ACTION.replace('exit=0', 'exit=1')
              + GETTER.replace('assigned=1', 'assigned=0').replace('error=0', 'error=-13')
              .replace('pending=1 claimed=1', f'pending={pending} claimed={claimed}'))
    closed = (fixture.CLOSED.replace(fixture.CLEAN, fixture.CLEAN.replace('primary_error=0', 'primary_error=-13'))
              .replace(fixture.FINISHED, fixture.FINISHED.replace('primary_error=0', 'primary_error=-13'))
              .replace(fixture.REMOVED, result + fixture.REMOVED.replace('stop-error=0', 'stop-error=-13')
                       + (RESTORE if pending else ''))
              .replace(fixture.CONFIG, fixture.CONFIG + (RELEASE if claimed else ''))
              + EMPTY.replace('error=0', 'error=-13'))
    return active, closed


class ResourceResultTests(unittest.TestCase):
    def test_success_keeps_live_owners_and_measured_result(self):
        # Mutations killed: accept nonzero action exit, missing assignment event, stale owners or zero writes.
        result = RESOURCE.outcome(OPEN)
        self.assertEqual(result, {'error': 0, 'action_exit': 0,
                                 'event': {'error': 0, 'assigned': 1, 'pending': 1, 'claimed': 1,
                                           'attempts': 12, 'writes': 8},
                                 'assignment_verified': True, 'early_refusal': False})
        self.assertEqual(RESOURCE.cleanup(CLOSED, result),
                         {'stop_error': 0, 'held_acquired': True,
                          'resource_cleanup_verified': True, 'assignment_error': 0})
        self.assertEqual(RESOURCE.cleanup(fixture.CLOSED + EMPTY)['assignment_error'], 0)

    def test_getter_and_result_records_are_complete_unique_and_consistent(self):
        # Mutations killed: parse partial/duplicate getters, historical assignment or an open phase.
        for row in (RESULT, ACTION, GETTER):
            invalid = (OPEN.replace(row, ''), OPEN + row, OPEN.replace(row, row.rstrip() + ' unexpected\n'))
            for text in invalid:
                with self.subTest(row=row, text=text), self.assertRaises(ValueError):
                    RESOURCE.outcome(text)
        for name, value in (('ready', 0), ('attempted', 0), ('assigned', 0), ('pending', 0),
                            ('claimed', 0), ('active', 1), ('error', -5), ('error', 1), ('error', -4096)):
            old = name + '=' + ('0' if name in ('active', 'error') else '1')
            bad = OPEN.replace(GETTER, GETTER.replace(old, name + '=' + str(value)))
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                RESOURCE.outcome(bad)
        for changed in (ACTION.replace('exit=0', 'exit=1'), ACTION.replace('exit=0', 'exit=256')):
            with self.assertRaises(ValueError):
                RESOURCE.outcome(OPEN.replace(ACTION, changed))

    def test_result_budget_order_and_scope_refuse_invalid_allocation(self):
        # Mutations killed: let the allocator exceed64, claim uncaptured state, skip writes or run before hold.
        for before, after in (('attempts=12', 'attempts=65'), ('attempts=12', 'attempts=7'),
                              ('writes=8', 'writes=0'), ('assigned=1', 'assigned=0'),
                              ('claimed=1', 'claimed=0'), ('pending=1', 'pending=0'),
                              ('error=0', 'error=1'), ('error=0', 'error=-4096')):
            with self.subTest(before=before, after=after), self.assertRaises(ValueError):
                RESOURCE.outcome(OPEN.replace(RESULT, RESULT.replace(before, after)))
        reordered = OPEN.replace(RESULT, '').replace(fixture.OWNER, RESULT + fixture.OWNER)
        with self.assertRaises(ValueError):
            RESOURCE.outcome(reordered)
        for row in (RESTORE, RELEASE, 'N71_PCIE_RESOURCE_UNKNOWN pending=0\n', fixture.REMOVED):
            with self.subTest(row=row), self.assertRaises(ValueError):
                RESOURCE.outcome(OPEN + row)

    def test_negative_assignment_retains_error_and_requires_its_rollback(self):
        # Mutations killed: mask an assignment error, require fictitious extra owners or lose negative stop error.
        for pending, claimed in ((1, 1), (1, 0), (0, 0)):
            active, closed = failed(pending=pending, claimed=claimed)
            assignment = RESOURCE.outcome(active)
            self.assertEqual((assignment['error'], assignment['assignment_verified']), (-13, False))
            self.assertEqual(RESOURCE.cleanup(closed, assignment),
                             {'stop_error': -13, 'held_acquired': True,
                              'resource_cleanup_verified': True, 'assignment_error': -13})
            for before, after in (('primary_error=-13', 'primary_error=-5'), ('stop-error=-13', 'stop-error=0')):
                with self.subTest(before=before), self.assertRaises(ValueError):
                    RESOURCE.cleanup(closed.replace(before, after), assignment)
            with self.assertRaises(ValueError):
                RESOURCE.outcome(active.replace('exit=1', 'exit=0'))
        active, closed = failed()
        refusal = 'N71_PCIE_SCAN_WRITE_REFUSED bus=1 devfn=00 where=010 size=4 value=c0000004 error=-13\n'
        result = active[active.index('N71_PCIE_RESOURCE_RESULT '):].splitlines(keepends=True)[0]
        active = active.replace(result, refusal + result)
        assignment = RESOURCE.outcome(active)
        self.assertEqual(RESOURCE.cleanup(closed.replace(result, refusal + result), assignment)['stop_error'], -13)
        for bad in (active.replace('error=-13\n', 'error=-5\n', 1),
                    active.replace(refusal, '').replace(result, result + refusal),
                    active + 'N71_PCIE_SCAN_WRITE_REFUSED broken\n'):
            with self.assertRaises(ValueError):
                RESOURCE.outcome(bad)
        active, closed = failed(pending=0, claimed=0)
        active = active.replace('attempts=12 writes=8', 'attempts=0 writes=0')
        closed = closed.replace('attempts=12 writes=8', 'attempts=0 writes=0')
        assignment = RESOURCE.outcome(active)
        self.assertEqual((assignment['event']['attempts'], assignment['event']['writes']), (0, 0))
        self.assertTrue(RESOURCE.cleanup(closed, assignment)['resource_cleanup_verified'])
        with self.assertRaises(ValueError):
            RESOURCE.outcome(failed(pending=0, claimed=1)[0])
        with self.assertRaises(ValueError):
            RESOURCE.outcome(failed(pending=1, claimed=0)[0].replace('attempts=0 writes=0', 'attempts=1 writes=0'))

    def test_early_refusal_has_no_invented_counts_or_new_restore_owner(self):
        # Mutations killed: fabricate success without an allocator event or forget an early primary error.
        active = (fixture.OPEN.replace(fixture.ACTIVE, fixture.ACTIVE.replace('primary_error=0', 'primary_error=-16'))
                  + ACTION.replace('exit=0', 'exit=1')
                  + 'N71_PCIE_RESOURCES ready=1 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=-16\n')
        assignment = RESOURCE.outcome(active)
        self.assertEqual(assignment, {'error': -16, 'action_exit': 1, 'event': None,
                                     'assignment_verified': False, 'early_refusal': True})
        closed = (fixture.CLOSED.replace(fixture.CLEAN, fixture.CLEAN.replace('primary_error=0', 'primary_error=-16'))
                  .replace(fixture.FINISHED, fixture.FINISHED.replace('primary_error=0', 'primary_error=-16'))
                  + EMPTY.replace('error=0', 'error=-16'))
        self.assertEqual(RESOURCE.cleanup(closed, assignment)['stop_error'], 0)
        for row in (RESTORE, RELEASE):
            with self.assertRaises(ValueError):
                RESOURCE.cleanup(closed + row, assignment)
        for value in (1, True, -4096):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fixture.HELD.parse(fixture.OPEN, primary_error=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                fixture.HELD.cleanup(fixture.CLOSED, primary_error=value)
        with self.assertRaises(ValueError):
            RESOURCE.outcome(active.replace('error=-16', 'error=0').replace('primary_error=-16', 'primary_error=0'))

    def test_extra_config_and_window_release_are_ordered_and_retryable(self):
        # Mutations killed: restore before removal, release before generic config or clear pending on failed retry.
        assignment = RESOURCE.outcome(OPEN)
        retry = CLOSED.replace(RESTORE, RESTORE.replace('error=0 pending=0', 'error=-5 pending=1') + RESTORE)
        self.assertTrue(RESOURCE.cleanup(retry, assignment)['resource_cleanup_verified'])
        bad = [CLOSED.replace(RESTORE, ''), CLOSED.replace(RELEASE, ''), CLOSED + RELEASE,
               CLOSED.replace(fixture.REMOVED + RESTORE, RESTORE + fixture.REMOVED),
               CLOSED.replace(RESTORE + fixture.CONFIG, fixture.CONFIG + RESTORE),
               CLOSED.replace(fixture.CONFIG + RELEASE, RELEASE + fixture.CONFIG),
               CLOSED.replace(RELEASE + fixture.PME_RESTORED, fixture.PME_RESTORED + RELEASE),
               CLOSED.replace(RESTORE, RESTORE + RESTORE),
               retry.replace('error=-5 pending=1', 'error=-5 pending=0'),
               retry.replace('error=-5 pending=1', 'error=0 pending=1'),
               CLOSED.replace(RESTORE, RESTORE.replace('pending=0', 'pending=1')),
               CLOSED.replace(RESTORE, RESTORE.replace('error=0', 'error=-5')),
               CLOSED.replace(RESULT, RESULT.replace('attempts=12', 'attempts=11')),
               CLOSED + 'N71_PCIE_RESOURCE_UNKNOWN claimed=0\n']
        for text in bad:
            with self.subTest(text=text), self.assertRaises(ValueError):
                RESOURCE.cleanup(text, assignment)
        for name in RESOURCE.FIELDS[:-1]:
            bad = CLOSED.replace(EMPTY, EMPTY.replace(name + '=0', name + '=1'))
            with self.subTest(name=name), self.assertRaises(ValueError):
                RESOURCE.cleanup(bad, assignment)

    def test_later_cleanup_refusal_preserves_negative_stop_after_restoration(self):
        # Mutation killed: allow a refused assignment to be declared successful, or erase its cleanup error.
        assignment = RESOURCE.outcome(OPEN)
        refusal = 'N71_PCIE_SCAN_WRITE_REFUSED bus=0 devfn=08 where=044 size=2 value=00000001 error=-1\n'
        closed = CLOSED.replace(fixture.REMOVED, refusal + fixture.REMOVED.replace('stop-error=0', 'stop-error=-1'))
        self.assertEqual(RESOURCE.cleanup(closed, assignment),
                         {'stop_error': -1, 'held_acquired': True,
                          'resource_cleanup_verified': True, 'assignment_error': 0})
        before_assignment = closed.replace(refusal, '').replace(RESULT, refusal + RESULT)
        with self.assertRaises(ValueError):
            RESOURCE.cleanup(before_assignment, assignment)
        with self.assertRaises(ValueError):
            RESOURCE.cleanup(closed.replace(refusal, refusal.replace('error=-1', 'error=-5')), assignment)

    def policy(self, evidence, release=fixture.HELD.RELEASE):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); folder = root / 'docs/evidence'; folder.mkdir(parents=True)
            (folder / 'n71-pci-resource-assignment.json').write_text(json.dumps(evidence))
            (folder / 'n71-pci-held-caller.json').write_bytes((ROOT / 'docs/evidence/n71-pci-held-caller.json').read_bytes())
            return RESOURCE.selected_records(root, release=release)

    def test_build_selection_is_explicit_and_matches_qualified_modules(self):
        # Mutations killed: select an unsupported ABI, unqualified module, foreign REG_ON or truthy flags.
        evidence = json.loads((ROOT / 'docs/evidence/n71-pci-resource-assignment.json').read_text())
        records = self.policy(evidence)
        self.assertEqual(records[0]['bytes'], 84696)
        self.assertEqual(records[0]['sha256'], '2dcdebc2251b272246c4b6ae7ee58449ef2973ffe01d66fa5398392730a2f31d')
        self.assertEqual(records[1]['sha256'], 'fdf887e7572b70d09e76f770272bee5dc9ffcde799277e894ee8965007c5a8f1')
        for name, value in evidence['contract'].items():
            values = (False, 1, None) if value is True else ([], None)
            for changed in values:
                bad = copy.deepcopy(evidence); bad['contract'][name] = changed
                with self.subTest(name=name, changed=changed), self.assertRaises(ValueError):
                    self.policy(bad)
        for key in ('werror', 'modpost_passed', 'elf_vermagic_verified', 'source_config_image_exports_preserved'):
            for value in (False, 1, None):
                bad = copy.deepcopy(evidence); bad['real_module_build'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.policy(bad)
        for key in ('adapter_and_caller_integrated',) + RESOURCE.FALSE_LIMITS:
            bad = copy.deepcopy(evidence); bad['limits'][key] = not bad['limits'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.policy(bad)
        for module in records:
            for key, value in (('bytes', 63), ('bytes', True), ('bytes', 262145),
                               ('sha256', '0' * 63), ('sha256', module['sha256'].upper()),
                               ('vermagic', '7.0.12 SMP preempt mod_unload aarch64')):
                bad = copy.deepcopy(evidence); bad['real_module_build']['modules'][module['module']][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.policy(bad)
        bad = copy.deepcopy(evidence); bad['real_module_build']['modules'][records[1]['module']]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.policy(bad)
        bad = copy.deepcopy(evidence); bad['module_interface']['allocator_exports_linked'].pop()
        with self.assertRaises(ValueError):
            self.policy(bad)
        bad = copy.deepcopy(evidence); bad['module_interface']['parameters'].pop()
        with self.assertRaises(ValueError):
            self.policy(bad)
        for field, value in (('format', True), ('format', 2), ('format', '1')):
            bad = copy.deepcopy(evidence); bad[field] = value
            with self.assertRaises(ValueError):
                self.policy(bad)
        for value in (True, 1, -1):
            bad = copy.deepcopy(evidence); bad['real_module_build']['exit_code'] = value
            with self.assertRaises(ValueError):
                self.policy(bad)
        with self.assertRaises(ValueError):
            self.policy(evidence, '7.2.0-iphone6s-dart-serdev1')


class ResourceMutationsTests(unittest.TestCase):
    def test_assertions_detect_weakened_guards(self):
        variants = {
            'duplicate-getter': ("len(found) == 1, 'Unique resource getter", "len(found) >= 1, 'Unique resource getter"),
            'getter-state': ('state == dict(ready=1, attempted=int(result is not None),', 'True or state == dict(ready=1, attempted=int(result is not None),'),
            'action-exit': ('(int(action[0].group(1)) == 0) == (error == 0)', 'True'),
            'result-budget': ('0 <= writes <= attempts <= 64', '0 <= writes <= attempts <= 65'),
            'result-writes': ('and writes > 0', 'and writes >= 0'),
            'uncaptured-claim': ('not claimed or pending', 'True'),
            'unclaimed-attempts': ('claimed or attempts == 0', 'True'),
            'assignment-order': ("text.index('N71_PCIE_SESSION_HELD ') < found[0].start()", 'True'),
            'no-unknown-active-events': ("text.count('N71_PCIE_RESOURCE_') == 1 + int(result is not None)", 'True'),
            'first-refusal-error': ('int(row.group(1)) == error', 'True'),
            'refusal-order': ("< text.index('N71_PCIE_RESOURCE_RESULT ')", '< len(text)'),
            'cleanup-history': ("result == (assignment['event'] if assignment else None)", 'True'),
            'cleanup-getter': ("state == dict.fromkeys(FIELDS, 0) | {'error': error}", 'True'),
            'no-unknown-cleanup-events': ("text.count('N71_PCIE_RESOURCE_') == int(result is not None) + len(restored) + len(released)", 'True'),
            'extra-restore-final': ("restored[-1].groups() == ('0', '0')", 'True'),
            'extra-restore-retry': ("-4095 <= int(row.group(1)) < 0 and row.group(2) == '1'", 'True'),
            'extra-restore-order': ('removed[0].start() < restored[0].start()', 'True'),
            'extra-before-generic': ('restored[-1].start() < configs[0].start()', 'True'),
            'release-unique': ('len(released) == 1 and configs and pme', 'len(released) >= 1 and configs and pme'),
            'release-after-generic': ('configs[-1].start() < released[0].start() < pme[0].start()', 'released[0].start() < pme[0].start()'),
            'release-before-pme': ('configs[-1].start() < released[0].start() < pme[0].start()', 'configs[-1].start() < released[0].start()'),
            'preserve-assignment-stop-error': ("base['stop_error'] == error", 'True'),
            'cleanup-refusal-after-assignment': ("all(row.start() > text.index('N71_PCIE_RESOURCE_RESULT ') for row in refusals)", 'True'),
            'contract-boolean': ('all(contract.get(name) is True for name in flags)', 'all(contract.get(name) for name in flags)'),
            'qualified-build': ("all(build.get(name) is True for name in ('werror'", "all(bool(build.get(name)) for name in ('werror'"),
            'module-size': ("64 <= row['bytes']", "63 <= row['bytes']"),
            'module-sha': ("r'[0-9a-f]{64}'", "r'[0-9a-fA-F]{64}'"),
            'reg-on-fixed': ('records[1] == previous[1]', 'True'),
            'module-interface': ("interface.get('allocator_exports_linked') == ['pci_bus_size_bridges', 'pci_bus_assign_resources',\n                                                        'request_resource', 'release_resource']", 'True'),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-resource-mutations-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py'); path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_RESOURCE_RESULT_SCRIPT=str(path))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                         '-p', 'test_n71_resource_result.py', '-k', 'ResourceResultTests'],
                                        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_RESOURCE_RESULT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
