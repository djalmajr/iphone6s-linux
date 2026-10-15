"""Real Session/staging and selectors with synthetic ELF data and phone replies."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_build as build_fixture
import test_n71_link_session as link_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_profile as PROFILE
import n71_driver_runtime_build as BUILD
import n71_driver_modules as WLAN
import n71_iommu_result as IOMMU
import n71_held_session as HELD
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_profile.py'
LINK_SOURCE = ROOT / 'scripts/host/n71-link-session.py'
SPEC = importlib.util.spec_from_file_location('runtime_profile_link', LINK_SOURCE)
LINK = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(LINK)
BOOT = '12345678-1234-1234-1234-123456789abc'


def elf(name):
    raw = bytearray(b'\x7fELF\x02\x01\x01'.ljust(64, b'\0')); struct.pack_into('<HH',raw,16,1,183)
    return bytes(raw) + name.encode() + b'\0vermagic=' + (WLAN.RELEASE + ' SMP preempt mod_unload aarch64').encode() + b'\0'


class RuntimeProfileTests(unittest.TestCase):
    subject = PROFILE
    link = LINK
    iommu = IOMMU

    def setUp(self):
        case = build_fixture.RuntimeBuildTests('test_exact_selection_preserves_assignment_reg_on_and_ordered_wcc_without_writing')
        case.setUp(); self.addCleanup(case.doCleanups); self.root = case.root; self.folder = case.folder
        self.output = self.root / 'runtime'; self.output.mkdir(mode=0o700); self.remote = self.root / 'remote'
        self.files = {}; self.calls = []; self.bad_hash = None; self.busy = None; self.force_stack_exit = None
        # Keep the selectors real; fixture metadata names synthetic ELF bytes, never production binaries.
        metadata = {p.name:json.loads(p.read_text()) for p in self.folder.glob('*.json')}
        old_hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.folder.glob('*.json')}
        reg = BUILD.select(self.root, case.request)['diagnostics'][1]; reg_raw = elf(reg['module'])
        def replace_reg(value):
            if isinstance(value, dict):
                if value.get('sha256') == reg['sha256'] and value.get('bytes') == reg['bytes']:
                    value.update(bytes=len(reg_raw), sha256=hashlib.sha256(reg_raw).hexdigest())
                for item in value.values(): replace_reg(item)
            elif isinstance(value,list):
                for item in value: replace_reg(item)
        for data in metadata.values(): replace_reg(data)
        caller = metadata[build_fixture.CALLER]['module']; caller_raw = elf('n71-pcie-diagnostic.ko')
        caller.update(bytes=len(caller_raw),sha256=hashlib.sha256(caller_raw).hexdigest())
        self.files = {'n71-pcie-diagnostic.ko':caller_raw, reg['module']:reg_raw}
        for name in WLAN.MODULE_PATHS:
            record = metadata[build_fixture.WCC]['modules'][name]; filename = name.rsplit('/',1)[-1]; raw = elf(filename)
            record.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()); self.files[filename] = raw
        def replace_refs(value, changed):
            if isinstance(value,dict): return {k:replace_refs(v,changed) for k,v in value.items()}
            if isinstance(value,list): return [replace_refs(v,changed) for v in value]
            return changed.get(value,value) if isinstance(value,str) else value
        previous = old_hashes
        for _ in range(20):
            for name,data in metadata.items(): (self.folder/name).write_text(json.dumps(data))
            current = {name:hashlib.sha256((self.folder/name).read_bytes()).hexdigest() for name in metadata}
            changed = {previous[name]:current[name] for name in metadata if previous[name]!=current[name]}
            if not changed: break
            metadata = {name:replace_refs(data,changed) for name,data in metadata.items()}; previous = current
        self.selected = BUILD.select(self.root, {'release':WLAN.RELEASE,'pcie_sha256':caller['sha256']})
        self.modules = [(r,self.files[r['module']]) for r in self.selected['diagnostics']]
        self.drivers = [(r,self.files[r['module']]) for r in self.selected['drivers']]
        for name,raw in self.files.items(): p=self.output/name; p.write_bytes(raw); p.chmod(0o600)
        for hook in (patch.object(self.link,'ROOT',self.root),patch.object(self.link,'n71_driver_runtime_profile',self.subject),
            patch.object(self.link,'n71_iommu_result',self.iommu),patch.object(self.link.device_profile,'ssh_options',return_value=[]),
            patch.dict(sys.modules,{'n71_driver_runtime_profile':self.subject})):
            hook.start(); self.addCleanup(hook.stop)

    def session(self, options=None):
        settings = dict(host_scan=True,scan_link_target=True,scan_pme_disable=True,scan_hold=True,
            resource_capable=True,iommu_parent=True,release=WLAN.RELEASE,runtime=self.drivers)
        settings.update(options or {})
        return self.link.Session(self.output,self.modules,**settings)

    def accepted(self, function, *args):
        try: return function(*args)
        except (ValueError,OSError) as error: self.fail('Qualified runtime profile refused: '+str(error))

    def capture(self, stage, command, raw=None):
        self.calls.append((stage,command)); code=0; text=''
        if stage=='preflight': text=WLAN.RELEASE+'\nN71_BOOT_ID '+BOOT+'\n'
        elif stage=='aspm': text='N71_PCIE_CMDLINE rdinit=/init pcie_aspm=off\nN71_PCIE_ASPM_DISABLED\n'
        elif stage=='module-directory': self.remote.mkdir(mode=0o700)
        elif stage=='pci-empty': text='N71_PCI_PREFLIGHT_EMPTY\n'
        elif stage=='runtime-stack-empty':
            sysroot=self.root/'sys'; (sysroot/'module').mkdir(parents=True,exist_ok=True)
            if self.busy:
                target=sysroot/('bus/pci/drivers/brcmfmac' if self.busy=='driver' else 'module/'+self.busy); target.mkdir(parents=True,exist_ok=True)
            process=subprocess.run(['sh','-c',command.replace('/sys/',str(sysroot)+'/')],capture_output=True,text=True,timeout=5)
            code=process.returncode if self.force_stack_exit is None else self.force_stack_exit; text=process.stdout
        elif stage.startswith('transfer-'):
            name=stage.removeprefix('transfer-'); path=self.remote/name
            with path.open('xb') as file: file.write(raw)
        elif stage.startswith('hash-'):
            name=stage.removeprefix('hash-'); data=(self.remote/name).read_bytes()
            expected=next(r['sha256'] for r in self.selected['diagnostics']+self.selected['drivers'] if r['module']==name)
            code=int(hashlib.sha256(data).hexdigest()!=expected or name==self.bad_hash)
        elif stage=='observe': text=link_fixture.OBSERVE
        elif stage=='activate': text=link_fixture.ACTIVE
        elif stage=='pcie': code=1
        else: self.fail('Unexpected phone dependency: '+stage)
        path=self.output/(stage+'-private.log'); path.write_text(text+'\nSTDERR\n'); path.chmod(0o600)
        return SimpleNamespace(returncode=code,stdout=text)

    def module_snapshot(self, session):
        hasher=self.root/'hash-private.py'
        hasher.write_text('import hashlib,sys\nprint(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()+"  "+sys.argv[1])\n')
        command='set -e; '+WLAN.getter(session.driver_modules,session.module_directory)
        command=command.replace(session.module_directory,shlex.quote(str(self.remote)))
        command=command.replace('uname -r','printf '+shlex.quote(WLAN.RELEASE))
        command=command.replace('cat /proc/sys/kernel/random/boot_id','printf '+BOOT)
        command=command.replace('/sys/',str(self.root/'sys')+'/')
        command=command.replace('sha256sum ','python3 '+shlex.quote(str(hasher))+' ')
        return subprocess.run(['sh','-c',command],capture_output=True,text=True,timeout=5)

    def test_real_session_owns_two_diagnostics_and_five_drivers_separately(self):
        # Mutations: omit configure/dispatch, retain a caller alias or mix WCC into diagnostic ownership.
        modules=copy.deepcopy(self.modules); drivers=copy.deepcopy(self.drivers)
        session=self.accepted(self.session)
        self.assertTrue(session.driver_runtime); self.assertEqual(session.driver_modules,self.selected['drivers'])
        self.assertEqual(session.modules,self.modules); self.assertEqual(len(session.modules),2)
        self.assertEqual(session.driver_runtime_journal,[]); self.assertEqual(session.driver_module_journal,[])
        self.drivers[0][0]['sha256']='f'*64
        self.assertEqual(session.driver_modules[0],drivers[0][0]); self.assertEqual(session.modules,modules)
        self.accepted(self.subject.selected,session,self.root); self.assertEqual(self.calls,[])

    def test_default_session_has_no_runtime_commands_or_extra_transfers(self):
        # Mutation: configure runtime or transfer WCC without explicit selection.
        session=self.link.Session(self.output,[(dict(module='n71-pcie-diagnostic.ko',sha256=hashlib.sha256(b'legacy').hexdigest()),b'legacy')])
        self.assertFalse(session.driver_runtime); self.assertIsNone(session.driver_modules)
        self.assertEqual(self.subject.staged(session),[])
        def capture(stage,command,raw=None):
            self.calls.append((stage,command))
            return SimpleNamespace(returncode=0,stdout=self.link.RELEASE+'\nN71_BOOT_ID '+BOOT+'\n')
        session.capture=capture
        with patch.object(self.link.n71_driver_runtime_profile,'preflight_command',side_effect=AssertionError('Legacy runtime effect')):
            self.accepted(session.preflight)
        self.assertEqual([name for name,_ in self.calls],['preflight','transfer-n71-pcie-diagnostic.ko','hash-n71-pcie-diagnostic.ko'])

    def test_mode_records_and_immutable_bytes_refuse_before_phone_effect(self):
        # Mutations: drop capability checks or trust mismatched, incomplete, reordered or mutable module bytes.
        for options in ({'scan_hold':False},{'resource_capable':False},{'iommu_parent':False},{'runtime':False}):
            with self.subTest(options=options), self.assertRaises(ValueError): self.session(options)
        original=self.drivers
        for data in (original[:-1],list(reversed(original)),[(dict(r),bytearray(raw)) for r,raw in original],
            [(dict(original[0][0]),b'wrong')]+original[1:]):
            with self.subTest(data_len=len(data)), self.assertRaises(ValueError): self.session({'runtime':data})
        saved=copy.deepcopy(self.modules)
        for key,value in (('driver_runtime',1),('vermagic','foreign'),('extra',True)):
            self.modules=copy.deepcopy(saved); self.modules[0][0][key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): self.session()
        self.modules=saved
        self.assertEqual(self.calls,[])

    def test_preflight_transfers_all_seven_before_probe_and_never_loads_wcc(self):
        # Mutations: skip WCC staging, hash verification or enable probe before the files exist.
        session=self.accepted(self.session); session.capture=self.capture
        self.assertNotEqual(self.module_snapshot(session).returncode,0)
        self.accepted(session.preflight)
        expected=self.selected['diagnostics']+self.selected['drivers']
        self.assertEqual([name.removeprefix('transfer-') for name,_ in self.calls if name.startswith('transfer-')],[r['module'] for r in expected])
        self.assertEqual({p.name:p.read_bytes() for p in self.remote.iterdir()},self.files)
        self.assertFalse(any('insmod ' in command for _,command in self.calls))
        getter=HELD.snapshot_command(session)
        for record in self.selected['drivers']: self.assertIn(session.module_directory+'/'+record['module'],getter)
        process=self.module_snapshot(session); self.assertEqual(process.returncode,0,process.stderr)
        state=WLAN.live(process.stdout,{'manifest':session.driver_modules,'directory':session.module_directory,'boot':BOOT})
        self.assertEqual(state['registered'],0); self.assertEqual([s['present'] for s in state['states'].values()],[0]*8)

    def test_failed_remote_hash_and_busy_stack_block_all_probe_effects(self):
        # Mutations: ignore a failed hash or runtime stack guard before REG_ON/PCI insmod.
        for busy in WLAN.OBSERVED+('driver',):
            self.calls=[]; self.busy=busy; session=self.session(); session.capture=self.capture
            with self.assertRaises(ValueError): session.experiment()
            self.assertFalse(any('insmod ' in command for _,command in self.calls))
            self.assertFalse(any(name.startswith('transfer-') for name,_ in self.calls))
            if self.remote.exists(): self.remote.rmdir()
            if (self.root/'sys').exists(): shutil.rmtree(self.root/'sys')
        self.busy=None; self.calls=[]; self.bad_hash=self.selected['drivers'][0]['module']
        session=self.session(); session.capture=self.capture
        with self.assertRaises(ValueError): session.experiment()
        self.assertFalse(session.reg_attempted or session.activation_attempted or session.pcie_attempted)
        self.assertFalse(any('insmod ' in command for _,command in self.calls))

    def test_probe_parameter_is_only_explicit_and_follows_all_hashes(self):
        # Mutation: omit driver_runtime=1 or perform driver prepare/publish or a WCC insmod during probe.
        session=self.accepted(self.session); session.capture=self.capture
        with self.assertRaises(ValueError): session.experiment()
        pcie=next(command for name,command in self.calls if name=='pcie')
        self.assertIn(' driver_runtime=1',pcie); self.assertIn('msi_parent=1 iommu_parent=1',pcie)
        self.assertEqual(len([name for name,_ in self.calls if name.startswith('hash-')]),7)
        self.assertFalse(any('driver-prepare' in command or 'driver-publish' in command for _,command in self.calls))
        for record in self.selected['drivers']: self.assertNotIn('insmod '+session.module_directory+'/'+record['module'],pcie)

    def test_stack_exit_and_marker_must_both_agree_before_transfer(self):
        # Mutations: accept an exit failure with a marker or a zero exit without the complete marker.
        for busy,exit_code in ((None,1),('rfkill',0)):
            self.calls=[]; self.busy=busy; self.force_stack_exit=exit_code
            session=self.session(); session.capture=self.capture
            with self.assertRaises(ValueError): session.experiment()
            self.assertFalse(session.reg_attempted or session.activation_attempted or session.pcie_attempted)
            self.assertFalse(any(name.startswith('transfer-') for name,_ in self.calls))
            if self.remote.exists(): self.remote.rmdir()
            if (self.root/'sys').exists(): shutil.rmtree(self.root/'sys')

    def test_changed_session_data_refuses_before_first_ssh(self):
        # Mutation: skip preflight's fresh validation after constructor while owned bytes or manifest drift.
        session=self.session(); session.capture=self.capture
        record,raw=session.driver_module_data[0]; session.driver_module_data[0]=(record,raw[:-1]+b'x')
        with self.assertRaises(ValueError): session.preflight()
        self.assertEqual(self.calls,[])


class RuntimeProfileMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeProfileTests))
        self.assertTrue(baseline.wasSuccessful(),baseline.failures+baseline.errors)
        owned='test_real_session_owns_two_diagnostics_and_five_drivers_separately'
        refuse='test_mode_records_and_immutable_bytes_refuse_before_phone_effect'
        stack='test_failed_remote_hash_and_busy_stack_block_all_probe_effects'
        sources={'subject':SOURCE,'link':LINK_SOURCE,'iommu':ROOT/'scripts/host/n71_iommu_result.py'}
        mutations=[
            ('exact-record','subject','pair[0] == expected','True',refuse),
            ('record-types','subject','all(type(pair[0][key]) is type(expected[key]) for key in expected)','True',refuse),
            ('immutable-bytes','subject','type(raw) is bytes','isinstance(raw,(bytes,bytearray))',refuse),
            ('owned-records','subject','copy.deepcopy(expected)','pair[0]',owned),
            ('explicit-mode','subject',"all(getattr(session, name, None) is True for name in ('scan_hold', 'resource_capable', 'iommu_parent'))",'True',refuse),
            ('fresh-sha','subject',"hashlib.sha256(raw).hexdigest() == expected['sha256']",'True','test_changed_session_data_refuses_before_first_ssh'),
            ('foreign-stack','subject','for name in wlan.OBSERVED','for name in wlan.NAMES',stack),
            ('driver-registry','subject','test ! -d /sys/bus/pci/drivers/brcmfmac; ','',stack),
            ('configure','link',"n71_driver_runtime_profile.configure(self, {'root': ROOT, 'modules': runtime})",'pass',owned),
            ('fresh-validation','link','n71_driver_runtime_profile.selected(self, ROOT)','pass','test_changed_session_data_refuses_before_first_ssh'),
            ('all-seven-files','link','self.modules + n71_driver_runtime_profile.staged(self)','self.modules','test_preflight_transfers_all_seven_before_probe_and_never_loads_wcc'),
            ('stack-exit','link',"p.returncode == 0 and p.stdout.splitlines().count('N71_RUNTIME_STACK_EMPTY') == 1", "p.stdout.splitlines().count('N71_RUNTIME_STACK_EMPTY') == 1",'test_stack_exit_and_marker_must_both_agree_before_transfer'),
            ('stack-marker','link',"p.returncode == 0 and p.stdout.splitlines().count('N71_RUNTIME_STACK_EMPTY') == 1",'p.returncode == 0','test_stack_exit_and_marker_must_both_agree_before_transfer'),
            ('remote-hash','link',"p.returncode == 0, 'Remote module hash not proved'","True, 'Remote module hash not proved'",stack),
            ('runtime-parameter','link',"parameters += ' driver_runtime=1'","parameters += ''",'test_probe_parameter_is_only_explicit_and_follows_all_hashes'),
            ('selected-dispatch','iommu','if n71_driver_runtime_result.capable(session):\n        import n71_driver_runtime_profile','if False:\n        import n71_driver_runtime_profile',owned),
        ]
        for name,field,before,after,method in mutations:
            with self.subTest(name=name):
                path=sources[field]; source=path.read_text(); self.assertEqual(source.count(before),1,name)
                module=ModuleType('runtime_profile_mutant'); module.__file__=str(path)
                exec(compile(ast.parse(source.replace(before,after,1)),str(path),'exec'),module.__dict__)
                case=type('MutatedRuntimeProfileTests',(RuntimeProfileTests,),{field:module})
                result=unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors,[],name); self.assertGreater(len(result.failures),0,name)
                print('N71_RUNTIME_PROFILE_MUTATION_KILLED',name,'AssertionError')


if __name__=='__main__': unittest.main()
