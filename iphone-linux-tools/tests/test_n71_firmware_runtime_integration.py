"""Real firmware shell/journals meet the existing modeled PCI/WCC coordinator."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_driver_firmware_session as firmware_fixture
import test_n71_driver_runtime_session as runtime_fixture
import test_n71_driver_runtime_cli as cli_fixture

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/host'))
import n71_driver_runtime_session as coordinator
import n71_driver_runtime_cli as cli
import n71_held_session as held
COORDINATOR=ROOT/'scripts/host/n71_driver_runtime_session.py'
LINK=ROOT/'scripts/host/n71-link-session.py'
REAL_RUN=subprocess.run


class FirmwareIntegrationTests(unittest.TestCase):
    def firmware_case(self):
        case=firmware_fixture.FirmwareSessionTests('test_stage_bind_verify_restore_in_one_boot_and_keep_private_data')
        case.setUp(); self.addCleanup(case.doCleanups); return case

    def runtime_case(self):
        fw=self.firmware_case(); rt=runtime_fixture.RuntimeSessionTests('test_start_observe_and_stop_share_one_boot_and_preserve_origin')
        rt.setUp(); self.addCleanup(rt.doCleanups); rt.subject=getattr(self,'subject',coordinator)
        restored=rt.case.restored
        def restore_session(output):
            session=restored(output); session.scan_hold=True; return session
        rt.case.restored=restore_session; rt.session.scan_hold=True
        directory=rt.session.module_directory; boot=rt.session.result['boot_id']
        fw.session.module_directory=directory; fw.session.result['boot_id']=boot
        (fw.phone/directory.lstrip('/')).mkdir(mode=0o700,parents=True,exist_ok=True)
        (fw.phone/'proc/sys/kernel/random/boot_id').write_text(boot+'\n'); fw.stage()
        rt.session.result[fw.subject.KEY]=copy.deepcopy(fw.session.result[fw.subject.KEY]); rt.phone.journal.save()
        original=rt.capture
        def capture(name,command,raw=None):
            if name.startswith('firmware-'):
                rt.calls.append((name,command)); rt.session.ssh=[sys.executable,str(fw.root/'transport-private.py')]
                saved=json.loads((rt.session.output/'held-state-private.json').read_text())['result'][fw.subject.KEY]
                if name=='firmware-bind': self.assertEqual(saved['path'],'binding')
                elif name=='firmware-restore': self.assertEqual(saved['path'],'restoring')
                with contextlib.redirect_stdout(io.StringIO()):
                    return firmware_fixture.LINK.Session.capture(rt.session,name,command,raw)
            if name.startswith('wlan-module-') and '-load-' in name and not name.endswith('-after'):
                self.assertEqual(fw.parameter.read_bytes(),(str(fw.phone)+directory+'/firmware').encode(),'WCC load preceded firmware binding')
            if name=='held-cleanup':
                self.assertEqual(fw.parameter.read_bytes(),b'\0','Provider cleanup preceded firmware restoration')
            process=original(name,command)
            for module in rt.phone.present | set(runtime_fixture.WLAN.modules.NAMES):
                path=fw.phone/'sys/module'/module
                if module in rt.phone.present: path.mkdir(exist_ok=True)
                elif path.exists(): path.rmdir()
            return process
        rt.capture=capture
        hook=patch.object(rt.subject,'firmware',fw.subject); hook.start(); self.addCleanup(hook.stop)
        return fw,rt

    def test_start_observe_stop_order_one_boot_and_source_immutability(self):
        # Mutations: drop firmware bind/restore around actual coordinator actions.
        fw,rt=self.runtime_case(); before={p.name:p.read_bytes() for p in rt.origin.iterdir()}
        self.assertTrue(rt.accepted('start')['successful']); self.assertEqual(rt.session.result[fw.subject.KEY]['path'],'bound')
        effects=rt.effects(); self.assertTrue(rt.accepted('observe')['successful']); self.assertEqual(rt.effects(),effects)
        self.assertEqual(rt.accepted('stop')['phase'],'stopped'); self.assertEqual(fw.parameter.read_bytes(),b'\0')
        self.assertEqual(rt.session.result[fw.subject.KEY]['path'],'restored')
        self.assertEqual(before,{p.name:p.read_bytes() for p in rt.origin.iterdir()})
        self.assertEqual(rt.session.result['boot_id'],fw.session.result['boot_id'])

    def test_observe_refuses_changed_data_and_stop_still_restores(self):
        # Mutation: skip firmware verification during an observe action.
        fw,rt=self.runtime_case(); rt.accepted('start')
        path=fw.phone/(rt.session.module_directory+'/firmware/regulatory.db').lstrip('/'); path.write_bytes(b'x'*path.stat().st_size)
        with self.assertRaises(ValueError): rt.run_action('observe')
        self.assertEqual(rt.session.result[fw.subject.KEY]['path'],'bound'); rt.source=rt.session.output
        self.assertEqual(rt.accepted('stop')['phase'],'stopped'); self.assertEqual(fw.parameter.read_bytes(),b'\0')

    def cli_case(self):
        fw=self.firmware_case(); case=cli_fixture.RuntimeCliTests('test_real_entry_and_local_check_preserve_files_without_handler_or_output')
        case.setUp(); self.addCleanup(case.doCleanups)
        directory=case.root/'runtime/firmware'; directory.mkdir(mode=0o700); (directory/'brcm').mkdir(mode=0o700)
        for name,data in fw.fixture.values.items():
            p=directory/name; p.write_bytes(data); p.chmod(0o600)
        for name in ('n71-wlan-firmware-origin.json','n71-regdb-calibration-source-audit.json'):
            (case.root/'docs/evidence'/name).write_bytes((fw.root/'docs/evidence'/name).read_bytes())
        hook=patch.object(cli,'firmware',fw.subject); hook.start(); self.addCleanup(hook.stop)
        return fw,case,directory

    def test_cli_check_selects_real_private_data_without_effect_or_output(self):
        # Mutation: ignore the optional package or perform stage during --check.
        fw,case,directory=self.cli_case(); selected=[]; configure=fw.subject.configure
        def witness(session,request):
            configure(session,request); selected.append(session.firmware_data)
        before={str(p.relative_to(case.root)):p.read_bytes() for p in case.root.rglob('*') if p.is_file()}
        with patch.object(fw.subject,'configure',witness):
            code,text=case.accepted(dict(case.request(),firmware=directory))
        self.assertEqual(code,0); self.assertIn('N71_RUNTIME_LOCAL_GATE_OK',text)
        self.assertEqual([data for _,data in selected[0]],list(fw.fixture.values.values()))
        self.assertEqual(before,{str(p.relative_to(case.root)):p.read_bytes() for p in case.root.rglob('*') if p.is_file()})

    def test_session_preflight_transfers_firmware_before_any_module(self):
        # Mutation: remove the firmware stage call from actual Session.preflight.
        fw,case,directory=self.cli_case(); calls=[]; kept=[]
        def handler(session,identity,**request):
            kept.append(session); session.ssh=[sys.executable,str(fw.root/'transport-private.py')]
            journal=held.Journal(session,identity); session.before_effect=journal.save
            def capture(name,command,raw=None):
                calls.append(name)
                if name=='preflight': return SimpleNamespace(returncode=0,stdout=session.release+'\nN71_BOOT_ID '+firmware_fixture.BOOT+'\n')
                if name=='aspm': return SimpleNamespace(returncode=0,stdout='N71_PCIE_CMDLINE pcie_aspm=off\nN71_PCIE_ASPM_DISABLED\n')
                if name=='pci-empty': return SimpleNamespace(returncode=0,stdout='N71_PCI_PREFLIGHT_EMPTY\n')
                if name.startswith('transfer-'):
                    self.assertEqual(session.result.get(fw.subject.KEY,{}).get('status'),'ready','Module transfer preceded firmware staging')
                with contextlib.redirect_stdout(io.StringIO()):
                    return firmware_fixture.LINK.Session.capture(session,name,command,raw)
            session.capture=capture
            def transport(args,**options):
                self.assertEqual(args[:2],session.ssh,'Process escaped the isolated transport')
                return REAL_RUN(args,**options)
            with patch.object(subprocess,'run',side_effect=transport): session.preflight()
            return 0
        def link(root):
            subject=self.link_subject; subject.ROOT=root; subject.n71_driver_firmware_session=fw.subject; return subject
        hooks=[patch.object(cli.held,'run',handler)]
        if hasattr(self,'link_subject'): hooks.append(patch.object(cli,'link_module',link))
        else: hooks.append(patch.object(firmware_fixture.LINK,'n71_driver_firmware_session',fw.subject))
        with contextlib.ExitStack() as stack:
            for hook in hooks: stack.enter_context(hook)
            # The normal loader creates another module instance, so configure its stage dependency.
            original=cli.link_module
            if not hasattr(self,'link_subject'):
                def scoped(root):
                    result=original(root); result.n71_driver_firmware_session=fw.subject; return result
                stack.enter_context(patch.object(cli,'link_module',scoped))
            code,_=case.accepted(dict(case.request(check=False),firmware=directory))
        self.assertEqual(code,0); self.assertEqual(kept[0].result[fw.subject.KEY]['status'],'ready')
        self.assertLess(next(i for i,n in enumerate(calls) if n.startswith('firmware-staged-')),next(i for i,n in enumerate(calls) if n.startswith('transfer-')))


class FirmwareIntegrationMutationProof(unittest.TestCase):
    def test_actual_coordinator_and_session_mutations(self):
        baseline=unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(FirmwareIntegrationTests).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures)
        cases=[('bind','test_start_observe_stop_order_one_boot_and_source_immutability'),
            ('restore','test_start_observe_stop_order_one_boot_and_source_immutability'),
            ('verify','test_observe_refuses_changed_data_and_stop_still_restores'),
            ('stage','test_session_preflight_transfers_firmware_before_any_module')]
        for action,method in cases:
            path=LINK if action=='stage' else COORDINATOR; tree=ast.parse(path.read_text()); matches=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute):
                    call=node.value.func
                    if call.attr==action and isinstance(call.value,ast.Name) and call.value.id in ('firmware','n71_driver_firmware_session'):
                        node.value=ast.Constant(None); matches.append(node)
            self.assertEqual(len(matches),1,action)
            spec=importlib.util.spec_from_file_location('firmware_integration_mutant',path); module=importlib.util.module_from_spec(spec)
            exec(compile(ast.fix_missing_locations(tree),str(path),'exec'),module.__dict__)
            case=FirmwareIntegrationTests(method)
            if action=='stage': case.link_subject=module
            else: case.subject=module
            result=unittest.TestResult(); case.run(result)
            self.assertFalse(result.errors,'Infrastructure error is not a kill: '+action)
            self.assertTrue(result.failures and all('AssertionError' in text for _,text in result.failures),action)
        print('N71_FIRMWARE_INTEGRATION_ASSERTION_MUTATIONS_OK 4/4')


if __name__=='__main__': unittest.main()
