"""WCC ownership and pre-effect guards use real POSIX shell and synthetic kernel tools."""
import ast
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_modules as MODULES
from test_n71_driver_runtime_stage import BOOT, PREPARED
import n71_driver_runtime_stage as DRIVER
SOURCE = ROOT / 'scripts/host/n71_driver_modules.py'
DIRECTORY = '/run/n71-link-' + 'a' * 24


class DriverModuleTests(unittest.TestCase):
    subject = MODULES

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / 'staged'; self.target.mkdir(mode=0o700)
        self.tools = self.root / 'tools'; self.tools.mkdir()
        self.modules = self.root / 'sys/module'; self.modules.mkdir(parents=True)
        (self.root / 'proc/sys/kernel/random').mkdir(parents=True)
        (self.root / 'proc/sys/kernel/random/boot_id').write_text(BOOT + '\n')
        self.control = self.modules / 'n71_pcie_diagnostic/parameters'; self.control.mkdir(parents=True)
        (self.control / 'driver_runtime').write_text('Y\n'); (self.control / 'held').write_text('held=1\n')
        (self.control / 'driver_runtime_status').write_text(DRIVER.state_text(PREPARED).splitlines()[0].removeprefix(DRIVER.result.MARKER) + '\n')
        self.records = copy.deepcopy(self.subject.qualified(ROOT))
        for record in self.records:
            raw = ('synthetic kernel input ' + record['name']).encode()
            (self.target / record['module']).write_bytes(raw)
            record.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        (self.tools / 'uname').write_text('#!/bin/sh\nprintf "%s\\n" "' + MODULES.RELEASE + '"\n')
        (self.tools / 'uname').chmod(0o700)
        hashing = '#!' + sys.executable + '\nimport hashlib,sys\nfrom pathlib import Path\nfor name in sys.argv[1:]:\n print(hashlib.sha256(Path(name).read_bytes()).hexdigest()+"  "+name)\n'
        (self.tools / 'sha256sum').write_text(hashing); (self.tools / 'sha256sum').chmod(0o700)
        script = ('#!' + sys.executable + '\nimport json,sys,shutil\nfrom pathlib import Path\n'
                  'root=Path(' + repr(str(self.root)) + ')\nrecords=json.loads(' + repr(json.dumps(self.records)) + ')\n'
                  'base=root/"sys/module"\naction=Path(sys.argv[0]).name\n'
                  'name=Path(sys.argv[1]).stem.replace("-","_") if action=="insmod" else sys.argv[1]\n'
                  'kind="load" if action=="insmod" else "unload"\n'
                  'receipts=[p for p in (root/"staged").glob("*receipt-private.log") if "action="+kind+" name="+name+" " in p.read_text() and "N71_WLAN_EXIT " not in p.read_text()]\n'
                  'assert len(receipts)==1, "Kernel effect preceded remote receipt"\n'
                  'with (root/"effects").open("a") as log: log.write(kind+" "+name+"\\n")\n'
                  'path=base/name\n'
                  'if action=="insmod":\n'
                  ' assert not path.exists()\n path.mkdir(); (path/"holders").mkdir(); (path/"initstate").write_text("live\\n"); (path/"refcnt").write_text("0\\n")\n'
                  'else:\n'
                  ' if int((path/"refcnt").read_text()) or list((path/"holders").iterdir()): sys.exit(1)\n shutil.rmtree(path)\n'
                  'registry=root/"sys/bus/pci/drivers/brcmfmac"\n'
                  'if name=="brcmfmac":\n'
                  ' if action=="insmod": registry.mkdir(parents=True)\n else: registry.rmdir()\n'
                  'for record in records:\n'
                  ' path=base/record["name"]\n'
                  ' if not path.exists(): continue\n'
                  ' for holder in (path/"holders").iterdir(): holder.unlink()\n'
                  ' holders=[other["name"] for other in records if (base/other["name"]).exists() and record["name"] in other["depends"]]\n'
                  ' for holder in holders: (path/"holders"/holder).touch()\n'
                  ' (path/"refcnt").write_text(str(len(holders))+"\\n")\n')
        for name in ('insmod', 'rmmod'):
            (self.tools / name).write_text(script); (self.tools / name).chmod(0o700)
        self.environment = dict(os.environ, PATH=str(self.tools) + os.pathsep + os.environ.get('PATH', ''))

    def run_shell(self, command):
        command = re.sub(r'/(sys|proc)/', lambda match: str(self.root / match[1]) + '/', command)
        command = command.replace(DIRECTORY, str(self.target))
        return subprocess.run(['sh', '-c', command], env=self.environment, capture_output=True, text=True, timeout=12)

    def observation(self):
        process = self.run_shell('set -e; ' + self.subject.getter(self.records, DIRECTORY))
        self.assertEqual(process.returncode, 0, process.stderr)
        return process.stdout, self.subject.live(process.stdout, {'manifest': self.records, 'directory': DIRECTORY, 'boot': BOOT})

    def operation(self, action, name, index):
        _, before = self.observation()
        return {'action': action, 'name': name, 'index': index, 'boot': BOOT,
                'directory': DIRECTORY, 'release': MODULES.RELEASE, 'before': before}

    def populate(self):
        for index, name in enumerate(MODULES.NAMES):
            process = self.run_shell(self.subject.command(self.records, self.operation('load', name, index)))
            self.assertEqual(process.returncode, 0, process.stderr)

    def test_qualified_build_and_manifest_select_only_the_wcc_stack(self):
        # Mutations: bypass qualified/audit/import/alias flags, module order, bool bytes or ABI validation.
        records = self.subject.qualified(ROOT)
        self.assertEqual([x['module'] for x in records], ['rfkill.ko', 'cfg80211.ko', 'brcmutil.ko', 'brcmfmac.ko', 'brcmfmac-wcc.ko'])
        self.assertEqual(sum(x['bytes'] for x in records), 1211120)
        for field, value in [('name', 'other'), ('bytes', True), ('vermagic', 'different ABI'), ('depends', ['rfkill'])]:
            altered = copy.deepcopy(records); altered[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.subject.manifest(altered)
        public = ROOT / 'docs/evidence/n71-brcmfmac-pcie-modules-qualified.json'
        proof = json.loads(public.read_text()); directory = self.root / 'proof/docs/evidence'; directory.mkdir(parents=True)
        target = directory / public.name
        for key in ('qualified', 'mac_bytes_elf_and_hash_audit', 'source_and_baseline_preserved'):
            altered = copy.deepcopy(proof); altered[key] = False; target.write_text(json.dumps(altered))
            with self.subTest(key=key), self.assertRaises(ValueError): self.subject.qualified(self.root / 'proof')
        for field in ('imports_verified', 'endpoint_pci_alias_verified'):
            altered = copy.deepcopy(proof); altered['modules']['module-brcmfmac/brcmfmac.ko'][field] = False
            target.write_text(json.dumps(altered))
            with self.subTest(field=field), self.assertRaises(ValueError): self.subject.qualified(self.root / 'proof')

    def test_getter_and_parser_preserve_order_identity_and_canonical_states(self):
        # Mutations: ignore boot/file hash/order, duplicate rows, noncanonical refs or impossible absent owners.
        text, actual = self.observation()
        self.assertEqual(actual['registered'], 0)
        self.assertEqual(actual['states']['rfkill'], {'present': 0, 'state': '-', 'refs': 0, 'holders': []})
        row = 'N71_WLAN_MODULE name=rfkill present=0 state=- refs=0 holders=-\n'
        other = 'N71_WLAN_MODULE name=cfg80211 present=0 state=- refs=0 holders=-\n'
        invalid = [text.replace(BOOT, '87654321-1234-1234-1234-123456789abc'), text + row,
                   text.replace(row, ''), text.replace(row + other, other + row),
                   text.replace(row, row.replace('refs=0', 'refs=00')),
                   text.replace(row, row.replace('state=-', 'state=live')),
                   text.replace(self.records[0]['sha256'], '0' * 64), text + 'N71_WLAN_REGISTERED=0\n']
        for value in invalid:
            with self.subTest(value=value[:80]), self.assertRaises(ValueError):
                self.subject.live(value, {'manifest': self.records, 'directory': DIRECTORY, 'boot': BOOT})

    def test_real_shell_loads_in_order_and_unloads_normally_in_reverse(self):
        # Mutations: reorder dependencies, omit exclusive receipt, use force/unbind or leave stale owners.
        for index, name in enumerate(MODULES.NAMES):
            request = self.operation('load', name, index)
            command = self.subject.command(self.records, request)
            self.assertNotIn('modprobe', command); self.assertNotIn('unbind', command); self.assertNotIn('rmmod -', command)
            process = self.run_shell(command); self.assertEqual(process.returncode, 0, process.stderr)
            actual = self.subject.live(process.stdout, {'manifest': self.records, 'directory': DIRECTORY, 'boot': BOOT})
            self.assertEqual(actual['states'][name]['present'], 1)
            receipt = self.target / Path(self.subject.receipt_path(request)).name
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            self.assertIn('N71_WLAN_STARTED index=' + str(index), receipt.read_text())
            self.assertIn('exit=0', receipt.read_text())
        for index, name in enumerate(reversed(MODULES.NAMES), 5):
            process = self.run_shell(self.subject.command(self.records, self.operation('unload', name, index)))
            self.assertEqual(process.returncode, 0, process.stderr)
            actual = self.subject.live(process.stdout, {'manifest': self.records, 'directory': DIRECTORY, 'boot': BOOT})
            self.assertEqual(actual['states'][name]['present'], 0)
        _, actual = self.observation()
        self.assertTrue(all(not state['present'] for state in actual['states'].values()))
        self.assertEqual(actual['registered'], 0)
        self.assertEqual((self.root / 'effects').read_text().splitlines(),
                         ['load ' + name for name in MODULES.NAMES] + ['unload ' + name for name in reversed(MODULES.NAMES)])

    def test_operation_order_and_occupied_snapshot_refuse_before_building_a_command(self):
        # Mutations: bypass prefix ownership, permit a foreign module, or disregard target/firmware pins.
        request = self.operation('load', 'cfg80211', 0)
        with self.assertRaises(ValueError): self.subject.command(self.records, request)
        self.populate()
        request = self.operation('unload', 'brcmfmac_wcc', 5)
        for name, changes in [('brcmfmac_wcc', {'refs': 1}), ('brcmfmac', {'refs': 2}),
                              ('brcmfmac_cyw', {'present': 1, 'state': 'live'}),
                              ('rfkill', {'holders': []})]:
            altered = copy.deepcopy(request); altered['before']['states'][name].update(changes)
            with self.subTest(name=name), self.assertRaises(ValueError): self.subject.command(self.records, altered)
        self.assertFalse(any(self.target.glob('*unload*receipt-private.log')))
        self.assertTrue((self.modules / 'brcmfmac_wcc').is_dir())

    def test_existing_partial_receipt_blocks_replay_and_preserves_original_bytes(self):
        # Mutation: remove noclobber and replay an intent whose remote receipt already exists.
        request = self.operation('load', 'rfkill', 0)
        receipt = self.target / Path(self.subject.receipt_path(request)).name
        receipt.write_text('interrupted original receipt\n'); receipt.chmod(0o600)
        process = self.run_shell(self.subject.command(self.records, request))
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(receipt.read_text(), 'interrupted original receipt\n')
        self.assertFalse((self.modules / 'rfkill').exists())
        self.assertFalse((self.root / 'effects').exists())

    def test_live_boot_hash_and_publication_guards_precede_receipt_and_kernel_effect(self):
        # Mutations: drop remote boot/hash checks or permit loading after publication/first cause.
        request = self.operation('load', 'rfkill', 0); command = self.subject.command(self.records, request)
        original = (self.control / 'driver_runtime_status').read_text()
        for field in ('published', 'operation_error', 'error'):
            changed = original.replace(field + '=0', field + '=' + ('1' if field == 'published' else '-5'))
            (self.control / 'driver_runtime_status').write_text(changed)
            process = self.run_shell(command)
            self.assertNotEqual(process.returncode, 0, field)
            self.assertFalse((self.modules / 'rfkill').exists())
            self.assertFalse(any(self.target.glob('*receipt-private.log')))
        (self.control / 'driver_runtime_status').write_text(original)
        (self.root / 'proc/sys/kernel/random/boot_id').write_text('87654321-1234-1234-1234-123456789abc\n')
        self.assertNotEqual(self.run_shell(command).returncode, 0)
        self.assertFalse((self.modules / 'rfkill').exists())
        (self.root / 'proc/sys/kernel/random/boot_id').write_text(BOOT + '\n')
        (self.target / 'rfkill.ko').write_bytes(b'tampered bytes')
        self.assertNotEqual(self.run_shell(command).returncode, 0)
        self.assertFalse((self.modules / 'rfkill').exists())
        self.assertFalse((self.root / 'effects').exists())

    def test_pins_acquired_after_observation_block_normal_unload_before_receipt(self):
        # Mutations: omit remote recheck of target refs/holders or the core firmware pin.
        self.populate(); request = self.operation('unload', 'brcmfmac_wcc', 5)
        command = self.subject.command(self.records, request); before = (self.root / 'effects').read_bytes()
        for name, value in [('brcmfmac', 2), ('brcmfmac_wcc', 1)]:
            path = self.modules / name / 'refcnt'; original = path.read_bytes(); path.write_text(str(value) + '\n')
            process = self.run_shell(command)
            self.assertNotEqual(process.returncode, 0, name)
            self.assertTrue((self.modules / 'brcmfmac_wcc').is_dir())
            self.assertEqual((self.root / 'effects').read_bytes(), before)
            self.assertFalse(any(self.target.glob('*unload*receipt-private.log')))
            path.write_bytes(original)

    def test_receipt_identity_complete_exit_and_unknown_transport_are_distinct(self):
        # Mutations: ignore receipt boot/SHA/index or equate incomplete receipt with an operation/SSH success.
        request = self.operation('load', 'rfkill', 0)
        started = ('N71_WLAN_STARTED index=0 action=load name=rfkill boot=' + BOOT
                   + ' sha256=' + self.records[0]['sha256'] + '\n')
        exited = 'N71_WLAN_EXIT index=0 action=load name=rfkill exit=0\n'
        self.assertEqual(self.subject.receipt(started, self.records, request), {'operation_exit': None})
        self.assertEqual(self.subject.receipt(started + exited, self.records, request), {'operation_exit': 0})
        self.assertEqual(self.subject.receipt(started + exited.replace('exit=0', 'exit=1'), self.records, request), {'operation_exit': 1})
        self.assertIsNone(self.subject.receipt('N71_WLAN_RECEIPT_MISSING\n', self.records, request))
        invalid = [started + started, started + exited + exited, started + exited.replace('exit=0', 'exit=256'),
                   started.replace('index=0', 'index=1') + exited,
                   started.replace(self.records[0]['sha256'], '0' * 64),
                   started.replace(BOOT, '87654321-1234-1234-1234-123456789abc'),
                   started + exited.replace('exit=0', 'exit=00'), 'N71_WLAN_RECEIPT_MISSING\n' + exited]
        for text in invalid:
            with self.subTest(text=text[:80]), self.assertRaises(ValueError):
                self.subject.receipt(text, self.records, request)


class DriverModuleMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        base = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(DriverModuleTests))
        self.assertTrue(base.wasSuccessful(), base.failures + base.errors)
        source = SOURCE.read_text()
        mutations = [
            ('name', "record['name'] == name", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('bool-bytes', "type(record['bytes']) is int", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('abi', "record['vermagic'] == RELEASE + ' SMP preempt mod_unload aarch64'", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('qualified', "proof.get('qualified') is True", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('audit', "proof.get('mac_bytes_elf_and_hash_audit') is True", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('imports', "record.get('imports_verified') is True", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('alias', "name != 'brcmfmac' or record.get('endpoint_pci_alias_verified') is True", 'True', 'test_qualified_build_and_manifest_select_only_the_wcc_stack'),
            ('module-order', 'tuple(row[0] for row in rows) == OBSERVED', 'True', 'test_getter_and_parser_preserve_order_identity_and_canonical_states'),
            ('prefix', "states[name]['present'] == int(position < count)", 'True', 'test_operation_order_and_occupied_snapshot_refuse_before_building_a_command'),
            ('foreign', "all(not states[name]['present'] for name in FOREIGN)", 'True', 'test_operation_order_and_occupied_snapshot_refuse_before_building_a_command'),
            ('holders', "state['holders'] == holders", 'True', 'test_operation_order_and_occupied_snapshot_refuse_before_building_a_command'),
            ('target-pin', "states[operation['name']]['refs'] == 0", 'True', 'test_operation_order_and_occupied_snapshot_refuse_before_building_a_command'),
            ('firmware-pin', "states['brcmfmac']['refs'] == 1", 'True', 'test_operation_order_and_occupied_snapshot_refuse_before_building_a_command'),
            ('remote-receipt', 'set -C;', '', 'test_existing_partial_receipt_blocks_replay_and_preserves_original_bytes'),
            ('remote-core-pin', 'test "$(cat /sys/module/brcmfmac/refcnt)" -eq 1;', 'true;', 'test_pins_acquired_after_observation_block_normal_unload_before_receipt'),
            ('receipt-identity', 'rows[0] == expected', 'True', 'test_receipt_identity_complete_exit_and_unknown_transport_are_distinct'),
            ('receipt-exit-budget', 'int(row[3]) <= 255', 'True', 'test_receipt_identity_complete_exit_and_unknown_transport_are_distinct'),
            ('receipt-exit-unknown', "int(exits[0][3]) if exits else None", "int(exits[0][3]) if exits else 0", 'test_receipt_identity_complete_exit_and_unknown_transport_are_distinct'),
        ]
        for name, old, new, method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(old), 1, name)
                subject = ModuleType('wcc_module_mutant')
                exec(compile(ast.parse(source.replace(old, new, 1)), str(SOURCE), 'exec'), subject.__dict__)
                case = type('MutatedDriverModuleTests', (DriverModuleTests,), {'subject': subject})
                result = unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors, [], name)
                self.assertGreater(len(result.failures), 0, name)
                print('N71_WCC_MODULE_MUTATION_KILLED', name, 'AssertionError')


if __name__ == '__main__':
    unittest.main()
