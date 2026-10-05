"""Held acquisition must never be confused with completed cleanup or a different build."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
SOURCE = ROOT / 'scripts/host/n71_scan_held_result.py'
SPEC = importlib.util.spec_from_file_location('held_result_under_test', os.environ.get('N71_HELD_RESULT_SCRIPT', SOURCE))
HELD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELD)

TARGET = 'N71_PCIE_SCAN_TARGET_PREPARED error=0 pending=1 prepared=1; no retrain\n'
PME = 'N71_PCIE_SCAN_PME_PREPARED error=0 pending=1 prepared=1; no W1C\n'
DEVICES = ('N71_PCIE_SCAN_DEVICE bus=0 devfn=08 id=1004106b class=060400 command=0000 driver=none\n'
           'N71_PCIE_SCAN_DEVICE bus=1 devfn=00 id=43a314e4 class=028000 command=0000 driver=none\n')
BARS = ''.join(f'N71_PCIE_SCAN_BAR index={index} start=0000000000000000 '
               f'end={size - 1 if size else 0:016x} flags={0x200 if size else 0:08x}; no MMIO\n'
               for index, size in enumerate((0x8000, 0, 0x400000, 0, 0, 0)))
BUS = 'N71_PCIE_SCAN_HELD devices=2 endpoints=1; no bind, DMA or radio\n'
OWNER = ('N71_PCIE_SESSION_HELD retained=1 scan_pending=1 reset_pending=1 powered=4 attached=4 '
         'power_put_pending=0 primary_error=0 cleanup_error=0; no bind, DMA or radio\n')
ACTIVE = ('N71_PCIE_STATUS ready=1 retained=1 scan_pending=1 reset_pending=1 powered=4 attached=4 '
          'power_put_pending=0 primary_error=0 cleanup_error=0\n')
CLEAN = ('N71_PCIE_STATUS ready=1 retained=0 scan_pending=0 reset_pending=0 powered=0 attached=0 '
         'power_put_pending=0 primary_error=0 cleanup_error=0\n')
ACQUIRED = TARGET + PME + DEVICES + BARS + BUS + OWNER
OPEN = 'N71_PCIE_HELD held=1\n' + ACTIVE + ACQUIRED
REMOVED = 'N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=0\n'
CONFIG = 'N71_PCIE_SCAN_CONFIG_RESTORED error=0; decode/readback checked\n'
PME_RESTORED = 'N71_PCIE_SCAN_PME_RESTORED error=0 pending=0; no W1C\n'
TLS_RESTORED = 'N71_PCIE_SCAN_TARGET_RESTORED error=0 pending=0; no retrain\n'
RESET = 'N71_PCIE_RESET_RESTORED asserted=1 readback=1\n'
POWER = 'N71_PCIE_POWER_RELEASED powered=0 attached=0\n'
FINISHED = ('N71_PCIE_SESSION_CLEANUP error=0 retained=0 scan_pending=0 reset_pending=0 powered=0 '
            'attached=0 power_put_pending=0 primary_error=0\n')
CLOSED = ('N71_PCIE_HELD held=0\n' + CLEAN + ACQUIRED + REMOVED + CONFIG
          + PME_RESTORED + TLS_RESTORED + RESET + POWER + FINISHED)


class HeldResultTests(unittest.TestCase):
    def test_live_owners_and_resources_have_no_fabricated_scan_counts(self):
        # Mutations killed: trust a stale getter, incomplete owners or assigned/decode-enabled resources.
        result = HELD.parse(OPEN)
        self.assertEqual((result['devices'], result['endpoints']), (2, 1))
        self.assertEqual([bar['bytes'] for bar in result['bars']], [0x8000, 0, 0x400000, 0, 0, 0])
        self.assertEqual([row['identity'] for row in result['device_details']], ['1004106b', '43a314e4'])
        self.assertTrue(result['held_verified'])
        self.assertEqual(result['caller_state'], HELD.ACTIVE)
        self.assertTrue(result['target_prepare_verified'] and result['pme_prepare_verified'])
        self.assertTrue({'reads', 'attempts', 'writes', 'refusals', 'cleanup_verified'}.isdisjoint(result))

    def test_acquisition_rejects_stale_or_missing_owner(self):
        # Mutations killed: ignore the live getter, pinned module or any acquired power/reset reference.
        invalid = [OPEN.replace('held=1', 'held=0'), OPEN.replace(ACTIVE, 'N71_PCIE_STATUS ready=0 retained=0\n')]
        for marker in ('retained=1', 'scan_pending=1', 'reset_pending=1', 'powered=4', 'attached=4'):
            value = marker.split('=')[0] + '=0'
            invalid += [OPEN.replace(ACTIVE, ACTIVE.replace(marker, value)),
                        OPEN.replace(OWNER, OWNER.replace(marker, value))]
        for marker in ('power_put_pending=0', 'primary_error=0', 'cleanup_error=0'):
            value = marker.split('=')[0] + '=1'
            invalid += [OPEN.replace(ACTIVE, ACTIVE.replace(marker, value)),
                        OPEN.replace(OWNER, OWNER.replace(marker, value))]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                HELD.parse(text)

    def test_complete_unique_records_are_required(self):
        # Mutation killed: accept the first of duplicate or malformed live/kernel proof records.
        rows = OPEN.splitlines(keepends=True)
        for row in rows:
            for text in (OPEN.replace(row, '', 1), OPEN + row, OPEN + row.split('=')[0] + '=broken\n',
                         OPEN.replace(row, row.rstrip() + ' unexpected\n')):
                with self.subTest(row=row, text=text), self.assertRaises(ValueError):
                    HELD.parse(text)

    def test_preparation_and_event_order_cannot_be_weakened(self):
        # Mutations killed: accept failed PME/TLS preparation or preparation after scanning.
        invalid = [OPEN.replace(TARGET + PME, PME + TARGET),
                   OPEN.replace(ACQUIRED, DEVICES + TARGET + PME + BARS + BUS + OWNER),
                   OPEN.replace(BARS + BUS, BUS + BARS), OPEN.replace(BUS + OWNER, OWNER + BUS),
                   OPEN.replace(DEVICES + BARS, DEVICES.splitlines(keepends=True)[0] + BARS
                                + DEVICES.splitlines(keepends=True)[1])]
        for row in (TARGET, PME):
            for before, after in (('error=0', 'error=-5'), ('pending=1', 'pending=0'), ('prepared=1', 'prepared=0')):
                invalid.append(OPEN.replace(row, row.replace(before, after)))
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                HELD.parse(text)

    def test_acquisition_refuses_cleanup_temporary_scan_or_refusal(self):
        # Mutation killed: keep a bus after failure, removal or restoration already started.
        for marker in ('N71_PCIE_SCAN_RESULT ', 'N71_PCIE_SCAN_WRITE_REFUSED ', 'N71_PCIE_SCAN_BUS_REMOVED ',
                       'N71_PCIE_SCAN_CONFIG_RESTORED ', 'N71_PCIE_SCAN_PME_RESTORED ',
                       'N71_PCIE_SCAN_TARGET_RESTORED ', 'N71_PCIE_SCAN_CLEANUP ',
                       'N71_PCIE_SESSION_CLEANUP ', 'N71_PCIE_RESET_RESTORED ', 'N71_PCIE_POWER_RELEASED '):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                HELD.parse(OPEN + marker + 'unexpected\n')

    def test_topology_decode_and_measured_unassigned_bars(self):
        # Mutations killed: allow decode, binding, foreign identity, assigned BARs or a different BAR size.
        self.assertEqual([bar['bytes'] for bar in HELD.parse(OPEN.replace('flags=00000200', 'flags=00140204'))['bars']],
                         [0x8000, 0, 0x400000, 0, 0, 0])
        invalid = [OPEN.replace('command=0000', 'command=0001', 1),
                   OPEN.replace('command=0000', 'command=0004', 1),
                   OPEN.replace('driver=none', 'driver=brcmfmac', 1),
                   OPEN.replace('43a314e4', 'ffffffff'), OPEN.replace('class=028000', 'class=060400'),
                   OPEN.replace('start=0000000000000000 end=0000000000007fff',
                                'start=0000000000008000 end=000000000000ffff'),
                   OPEN.replace('end=0000000000007fff', 'end=0000000000000fff'),
                   OPEN.replace('flags=00000200', 'flags=00000100', 1)]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                HELD.parse(text)

    def test_cleanup_requires_all_owners_zero_and_ordered_restoration(self):
        # Mutations killed: accept a held/pending caller or release reset/power before removing/restoring bus.
        self.assertEqual(HELD.cleanup(CLOSED), {'stop_error': 0, 'held_acquired': True})
        invalid = [CLOSED.replace('held=0', 'held=1'), CLOSED.replace(CLEAN, ACTIVE),
                   CLOSED.replace(REMOVED + CONFIG, CONFIG + REMOVED),
                   CLOSED.replace(CONFIG + PME_RESTORED, PME_RESTORED + CONFIG),
                   CLOSED.replace(PME_RESTORED + TLS_RESTORED, TLS_RESTORED + PME_RESTORED),
                   CLOSED.replace(TLS_RESTORED + RESET, RESET + TLS_RESTORED),
                   CLOSED.replace(RESET + POWER, POWER + RESET),
                   CLOSED.replace(POWER + FINISHED, FINISHED + POWER),
                   CLOSED.replace(FINISHED, FINISHED.replace('error=0', 'error=-5')),
                   CLOSED + 'N71_PCIE_SCAN_RESULT error=0\n',
                   CLOSED + 'N71_PCIE_SCAN_CLEANUP error=0 retained=0\n']
        for row in (REMOVED, CONFIG, PME_RESTORED, TLS_RESTORED, RESET, POWER, FINISHED):
            invalid += [CLOSED.replace(row, ''), CLOSED + row.split('=')[0] + '=broken\n',
                        CLOSED.replace(row, row.rstrip() + ' unexpected\n')]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                HELD.cleanup(text)

    def test_cleanup_retries_preserve_pending_state_and_negative_stop_error(self):
        # Mutations killed: mask callback refusal, skip final TLS or accept a successful earlier retry.
        pending = ('N71_PCIE_SESSION_CLEANUP error=-5 retained=1 scan_pending=1 reset_pending=1 powered=4 '
                   'attached=4 power_put_pending=0 primary_error=0\n')
        retried = CLOSED.replace(CONFIG, CONFIG.replace('error=0', 'error=-5') + pending + CONFIG)
        self.assertEqual(HELD.cleanup(retried)['stop_error'], 0)
        for row in (PME_RESTORED, TLS_RESTORED):
            failed = row.replace('error=0 pending=0', 'error=-5 pending=1')
            self.assertEqual(HELD.cleanup(CLOSED.replace(row, failed + pending + row))['stop_error'], 0)
            with self.assertRaises(ValueError):
                HELD.cleanup(CLOSED.replace(row, failed))
        refusal = 'N71_PCIE_SCAN_WRITE_REFUSED bus=0 devfn=08 where=044 size=2 value=00000001 error=-1\n'
        refused = CLOSED.replace(REMOVED, refusal + REMOVED.replace('stop-error=0', 'stop-error=-1'))
        self.assertEqual(HELD.cleanup(refused), {'stop_error': -1, 'held_acquired': True})
        invalid = [refused.replace(refusal, ''), refused.replace(refusal, refusal.replace('error=-1', 'error=-5')),
                   CLOSED.replace(REMOVED, refusal + REMOVED),
                   CLOSED.replace(CONFIG, CONFIG + CONFIG),
                   CLOSED.replace(TLS_RESTORED, TLS_RESTORED.replace('pending=0', 'pending=1')),
                   CLOSED.replace(TLS_RESTORED, TLS_RESTORED.replace('pending=0', 'pending=1') + TLS_RESTORED),
                   CLOSED.replace(FINISHED, pending.replace('error=-5', 'error=0') + FINISHED)]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                HELD.cleanup(text)

    def test_failure_before_hold_uses_existing_pme_cleanup(self):
        # Mutation killed: claim acquisition after a negative link that never registered a held bus.
        failed = 'N71_PCIE_HELD held=0\nN71_PCIE_STATUS ready=0 retained=0\nN71_PCIE_LINK_RESULT error=-110\n'
        self.assertEqual(HELD.cleanup(failed), {'stop_error': 0, 'held_acquired': False})
        early = failed.split('N71_PCIE_LINK_RESULT ')[0] + FINISHED.replace('primary_error=0', 'primary_error=-5')
        self.assertEqual(HELD.cleanup(early), {'stop_error': 0, 'held_acquired': False})
        with self.assertRaises(ValueError):
            HELD.cleanup(failed.replace('error=-110', 'error=0'))

    def policy(self, evidence, release=HELD.RELEASE):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'docs/evidence/n71-pci-held-caller.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(evidence))
            return HELD.selected_records(root, release=release)

    def test_qualified_build_and_exact_module_shapes(self):
        # Mutations killed: choose another build, unsupported ABI or malformed module identity.
        evidence = json.loads((ROOT / 'docs/evidence/n71-pci-held-caller.json').read_text())
        records = self.policy(evidence)
        self.assertEqual([row['module'] for row in records], ['n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko'])
        self.assertEqual(records[0]['bytes'], 76112)
        self.assertEqual(records[0]['sha256'], 'b7e51d4d8ee281ace121c11dc60af04265a63c7395613fa8503af590927520b3')
        self.assertEqual(records[1]['sha256'], 'fdf887e7572b70d09e76f770272bee5dc9ffcde799277e894ee8965007c5a8f1')
        for key in ('werror', 'modpost_passed', 'elf_vermagic_verified', 'source_config_image_exports_preserved', 'reg_on_unchanged'):
            for value in (False, 1, 'true', None):
                bad = copy.deepcopy(evidence); bad['kernel_build'][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.policy(bad)
        for module in records:
            for key, value in (('bytes', 63), ('bytes', 256 * 1024 + 1), ('bytes', True), ('bytes', '76112'),
                               ('sha256', module['sha256'].upper()), ('sha256', '0' * 63),
                               ('vermagic', '7.0.12 SMP preempt mod_unload aarch64')):
                bad = copy.deepcopy(evidence); bad['kernel_build']['modules'][module['module']][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.policy(bad)

    def test_caller_flags_are_booleans_and_scope_is_fixed(self):
        # Mutations killed: truthy metadata, enabled defaults, relaxed binding/DMA or unsupported power ABI.
        evidence = json.loads((ROOT / 'docs/evidence/n71-pci-held-caller.json').read_text())
        for key, original in evidence['api'].items():
            if original is True or key in ('default_enabled', 'parameter', 'held_getter_mode'):
                for value in (None, 'true', 1, 0):
                    bad = copy.deepcopy(evidence); bad['api'][key] = value
                    with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                        self.policy(bad)
        for key in ('caller_exposes_hold', 'resources_assigned', 'pci_bus_add_devices_called',
                    'enable_device_allowed', 'dma_enabled', 'firmware_loaded'):
            bad = copy.deepcopy(evidence); bad['limits'][key] = not bad['limits'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.policy(bad)
        for value in (True, 0, 2, '1'):
            bad = copy.deepcopy(evidence); bad['format'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.policy(bad)
        legacy = '7.2.0-iphone6s-dart-serdev1'
        bad = copy.deepcopy(evidence); bad['kernel_release'] = legacy
        for row in bad['kernel_build']['modules'].values():
            row['vermagic'] = legacy + ' SMP preempt mod_unload aarch64'
        with self.assertRaises(ValueError):
            self.policy(bad, legacy)


class HeldMutationsTests(unittest.TestCase):
    def test_guards_fail_assertions_when_weakened(self):
        variants = {
            'duplicate-proof': ('len(rows) == text.count(marker) == 1', 'len(rows) == text.count(marker) and len(rows) >= 1'),
            'live-held': ('live_held(text) == 1', 'live_held(text) in (0, 1)'),
            'live-owners': ('state == ACTIVE', 'True'),
            'session-owners': ('tuple(map(int, session.groups())) == (1, 1, 1, 4, 4, 0, 0, 0)', 'True'),
            'target-preparation': ("target.groups() == ('0', '1', '1')", 'True'),
            'pme-preparation': ("prepared[0].groups() == ('0', '1', '1')", 'True'),
            'acquisition-order': ('events == sorted(events) and len(events) == len(set(events))', 'True'),
            'decode-clear': ("all(row['command'] == 0 for row in devices['device_details'])", 'True'),
            'bar-unassigned': ("all(row['start'] == 0 for row in devices['bars'])", 'True'),
            'bar-measured-size': ("[row['bytes'] for row in devices['bars']] == [0x8000, 0, 0x400000, 0, 0, 0]", 'True'),
            'held-not-cleaned': ('not any(marker in text for marker in forbidden)', 'True'),
            'cleanup-not-held': ('live_held(text) == 0', 'live_held(text) in (0, 1)'),
            'cleanup-owners': ('n71_scan_target_result.is_clean(state)', 'True'),
            'remove-before-config': ("text.index('N71_PCIE_SESSION_HELD ') < removed.start() < configs[0].start()", 'True'),
            'config-retry-negative': ('all(int(row.group(1)) < 0 for row in configs[:-1])', 'True'),
            'tls-final': ("targets[-1].groups() == ('0', '0')", 'True'),
            'tls-retry-negative': ("all(int(row.group(1)) < 0 and row.group(2) == '1' for row in targets[:-1])", 'True'),
            'caller-final': ('tuple(map(int, sessions[-1].groups())) == (0, 0, 0, 0, 0, 0, 0, 0)', 'True'),
            'caller-retry-negative': ("all(int(row.group(1)) < 0 and row.group(2) == '1' and row.group(8) == '0'\n                    for row in sessions[:-1])", 'True'),
            'release-order': ('targets[-1].start() < reset.start() < power.start() < sessions[-1].start()', 'True'),
            'stop-refusal-preserved': ("(not refusals and stop_error == 0)\n            or (refusals and stop_error < 0 and int(refusals[0].group(1)) == stop_error\n                and all(text.index('N71_PCIE_SESSION_HELD ') < row.start() < removed.start()\n                        for row in refusals))", 'True'),
            'power2-scope': ('release == RELEASE', 'True'),
            'api-booleans': ('all(api.get(name) is True for name in flags)', 'all(api.get(name) for name in flags)'),
            'default-disabled-boolean': ("api.get('default_enabled') is False", "not api.get('default_enabled')"),
            'build-boolean': ("build.get('werror') is True", "bool(build.get('werror'))"),
            'module-size-boundary': ("64 <= row['bytes']", "63 <= row['bytes']"),
            'module-sha-canonical': ("r'[0-9a-f]{64}'", "r'[0-9a-fA-F]{64}'"),
            'module-abi': ("row.get('vermagic') == release + ' SMP preempt mod_unload aarch64'", 'True'),
            'negative-before-hold': ('any(int(error) < 0 for error in failed) or caller_failed', 'True'),
        }
        source = SOURCE.read_text()
        with tempfile.TemporaryDirectory(prefix='n71-held-mutations-') as directory:
            for name, (before, after) in variants.items():
                self.assertEqual(source.count(before), 1, name)
                path = Path(directory) / (name + '.py')
                path.write_text(source.replace(before, after, 1))
                compile(path.read_text(), str(path), 'exec')
                environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', N71_HELD_RESULT_SCRIPT=str(path))
                result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests',
                                         '-p', 'test_n71_scan_held_result.py', '-k', 'HeldResultTests'],
                                        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn('AssertionError', output, name + output)
                self.assertNotIn('ERROR:', output, name + output)
                print('N71_HELD_RESULT_ASSERTION_KILL', name, flush=True)


if __name__ == '__main__':
    unittest.main()
