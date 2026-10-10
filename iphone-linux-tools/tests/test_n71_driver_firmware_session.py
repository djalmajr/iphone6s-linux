"""Real capture, journal and generated shell; SSH, UID0 and sysfs are modeled."""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import test_n71_driver_firmware as package_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_held_session as held
import n71_driver_modules as wlan
SOURCE = ROOT / 'scripts/host/n71_driver_firmware_session.py'
SPEC = importlib.util.spec_from_file_location('firmware_lifetime', SOURCE)
LINK_SPEC = importlib.util.spec_from_file_location('firmware_real_capture', ROOT / 'scripts/host/n71-link-session.py')
LINK = importlib.util.module_from_spec(LINK_SPEC); LINK_SPEC.loader.exec_module(LINK)
BOOT = '00000000-1111-2222-3333-444444444444'
DIRECTORY = '/run/n71-link-' + 'a' * 24

TOOLS = r'''
import hashlib, os, stat, sys
from pathlib import Path
action=sys.argv[1]
if action=='stat':
    metadata=os.stat(sys.argv[4]); values=[oct(stat.S_IMODE(metadata.st_mode))[2:],str(0 if metadata.st_uid==os.geteuid() else metadata.st_uid)]
    if sys.argv[3]=='%a:%u:%h': values.append(str(metadata.st_nlink))
    print(':'.join(values))
elif action=='sha':
    valid=True
    for row in sys.stdin:
        expected,path=row.rstrip('\n').split('  ',1)
        ok=hashlib.sha256(Path(path).read_bytes()).hexdigest()==expected
        print(path+(': OK' if ok else ': FAILED')); valid &= ok
    raise SystemExit(0 if valid else 1)
else:
    value=Path(sys.argv[2]).read_bytes().split(b'\0',1)[0]
    prefix=str(Path(__file__).parent/'phone').encode()
    sys.stdout.buffer.write(value.replace(prefix,b'')+b'\n')
'''

TRANSPORT = r'''
import json, re, shlex, subprocess, sys
from pathlib import Path
base=Path(__file__).parent; settings=json.loads((base/'transport-settings-private.json').read_text())
original=sys.argv[1]; command=original.replace('$(uname -r)',settings['release'])
phone=str(base/'phone')
command=re.sub(r'(?<![A-Za-z0-9_/])/(run|proc|sys|lib)(?=[/; "])',lambda match:phone+match.group(0),command)
parameter=phone+'/sys/module/firmware_class/parameters/path'
tool=shlex.quote(sys.executable)+' '+shlex.quote(str(base/'tools-private.py'))
command=command.replace('od -An -tx1 -v '+parameter,tool+' getter '+shlex.quote(parameter)+' | od -An -tx1 -v')
command='stat(){ '+tool+' stat "$@"; }; sha256sum(){ '+tool+' sha "$@"; }; '+command
raw=sys.stdin.buffer.read() if 'cat > ' in original else b''
process=subprocess.run(['bash','-c',command],input=raw,capture_output=True)
sys.stdout.buffer.write(process.stdout.replace(phone.encode(),b'')); sys.stderr.buffer.write(process.stderr)
fail=base/'fail-private'
broken=fail.read_text() if fail.exists() else ''
if broken and ((broken=='transfer' and 'cat > ' in original) or
    (broken=='bind' and 'printf %s ' in original) or (broken=='restore' and "printf '\\000'" in original)):
    raise SystemExit(1)
raise SystemExit(process.returncode)
'''


class FirmwareSessionTests(unittest.TestCase):
    def setUp(self):
        fixture=package_fixture.FirmwareTests('test_exact_order_owned_records_immutable_bytes_and_no_effects')
        fixture.setUp(); self.addCleanup(fixture.doCleanups); self.fixture=fixture; self.root=fixture.root
        self.subject=getattr(self,'subject',importlib.util.module_from_spec(SPEC))
        if not hasattr(self.subject,'stage'): SPEC.loader.exec_module(self.subject)
        self.subject.firmware=fixture.subject
        self.phone=self.root/'phone'; (self.phone/DIRECTORY.lstrip('/')).mkdir(mode=0o700,parents=True)
        for name in ('lib','sys/module','sys/bus/pci/drivers','proc/sys/kernel/random'):
            (self.phone/name).mkdir(parents=True,exist_ok=True)
        self.parameter=self.phone/self.subject.PARAMETER.lstrip('/'); self.parameter.parent.mkdir(parents=True)
        self.parameter.write_bytes(b''); self.parameter.chmod(0o644)
        (self.phone/'proc/sys/kernel/random/boot_id').write_text(BOOT+'\n')
        for name,raw in [('tools-private.py',TOOLS),('transport-private.py',TRANSPORT)]:
            (self.root/name).write_text(raw); (self.root/name).chmod(0o600)
        (self.root/'transport-settings-private.json').write_text(json.dumps({'release':self.subject.firmware.RELEASE}))
        self.calls=[]; self.serial=0; self.session=None; self.fresh()
        self.subject.configure(self.session,{'root':self.root,'directory':fixture.folder})

    def fresh(self):
        previous=self.session; self.serial+=1; output=self.root/'runtime'/('operation-'+str(self.serial)); output.mkdir(mode=0o700)
        self.session=SimpleNamespace(output=output,ssh=[sys.executable,str(self.root/'transport-private.py')],history=None,
            release=self.subject.firmware.RELEASE,module_directory=DIRECTORY,driver_runtime=True,
            scan_hold=True,resource_capable=True,iommu_parent=True,resource_attempted=False,resource_assignment=None,
            driver_modules=wlan.qualified(ROOT),driver_module_journal=[],driver_runtime_journal=[],
            reg_attempted=False,activation_attempted=False,pcie_attempted=False,result={'kernel_release':self.subject.firmware.RELEASE,'boot_id':BOOT})
        if previous:
            self.session.result=copy.deepcopy(previous.result); self.session.firmware_data=copy.deepcopy(previous.firmware_data)
        self.journal=held.Journal(self.session,{'modules':{}}); self.session.before_effect=self.journal.save
        self.session.capture=self.capture

    def capture(self,name,command,raw=None):
        self.calls.append((name,command))
        saved=json.loads(self.journal.path.read_text())['result'].get(self.subject.KEY)
        if name=='firmware-directory' or name.startswith('firmware-transfer-'):
            self.assertIsNotNone(saved,'Data effect preceded durable intent'); self.assertEqual(saved['status'],'intent')
        elif name=='firmware-bind': self.assertEqual(saved['path'],'binding','Binding preceded durable intent')
        elif name=='firmware-restore': self.assertEqual(saved['path'],'restoring','Restore preceded durable intent')
        with contextlib.redirect_stdout(io.StringIO()):
            return LINK.Session.capture(self.session,name,command,raw)

    def accepted(self,function,*args):
        try: return function(*args)
        except (ValueError,OSError) as error: self.fail('Qualified firmware lifetime refused: '+str(error))

    def stage(self): self.accepted(self.subject.stage,self.session)
    def target(self,name): return self.phone/(DIRECTORY+'/firmware/'+name).lstrip('/')

    def test_stage_bind_verify_restore_in_one_boot_and_keep_private_data(self):
        # Mutations: omit durable intent or clear with newline/zero bytes instead of NUL.
        self.stage(); self.assertEqual(self.session.result[self.subject.KEY]['status'],'ready')
        for name,raw in self.fixture.values.items(): self.assertEqual(self.target(name).read_bytes(),raw)
        self.accepted(self.subject.bind,self.session,self.journal)
        self.assertEqual(self.parameter.read_bytes(),(str(self.phone)+DIRECTORY+'/firmware').encode())
        self.assertEqual(self.session.result[self.subject.KEY]['path'],'bound')
        before=self.parameter.read_bytes(); self.fresh(); self.accepted(self.subject.bind,self.session,self.journal)
        self.assertEqual(self.parameter.read_bytes(),before); self.assertEqual(sum(n=='firmware-bind' for n,_ in self.calls),1)
        self.accepted(self.subject.verify,self.session,self.journal)
        self.fresh(); self.accepted(self.subject.restore,self.session,self.journal)
        self.assertEqual(self.parameter.read_bytes(),b'\0'); self.assertEqual(self.session.result[self.subject.KEY]['path'],'restored')
        for name,raw in self.fixture.values.items(): self.assertEqual(self.target(name).read_bytes(),raw)
        self.fresh(); self.accepted(self.subject.restore,self.session,self.journal)
        self.assertEqual(sum(n=='firmware-restore' for n,_ in self.calls),1)
        self.assertEqual(self.session.result['boot_id'],BOOT)

    def test_changed_local_bytes_are_refused_before_wire_effect(self):
        # Mutation: disregard the pinned bytes before writing data remotely.
        record,raw=self.session.firmware_data[0]; self.session.firmware_data[0]=(record,b'x'*len(raw))
        with self.assertRaises(ValueError): self.subject.stage(self.session)
        self.assertEqual(self.calls,[]); self.assertNotIn(self.subject.KEY,self.session.result)

    def test_transfer_failure_is_retained_and_never_replayed(self):
        # Mutation: allow a repeated staging intent to emit another mkdir/transfer.
        (self.root/'fail-private').write_text('transfer')
        with self.assertRaises(ValueError): self.subject.stage(self.session)
        self.assertEqual(self.session.result[self.subject.KEY]['status'],'intent')
        self.fresh(); before=list(self.calls)
        with self.assertRaises(ValueError): self.subject.stage(self.session)
        self.assertEqual(self.calls,before); self.assertEqual(self.parameter.read_bytes(),b'')

    def test_ready_hash_and_boot_are_proved_from_real_generated_shell(self):
        # Mutations: skip ready state, filesystem hashing, or remote boot identity.
        self.stage(); self.session.result[self.subject.KEY]['status']='intent'
        with self.assertRaises(ValueError): self.subject.verify(self.session)
        self.session.result[self.subject.KEY]['status']='ready'; path=self.target('regulatory.db'); original=path.read_bytes()
        path.write_bytes(b'x'*len(original))
        with self.assertRaises(ValueError): self.subject.verify(self.session)
        path.write_bytes(original); (self.phone/'proc/sys/kernel/random/boot_id').write_text('99999999-1111-2222-3333-444444444444\n')
        with self.assertRaises(ValueError): self.subject.verify(self.session)
        self.assertEqual(self.parameter.read_bytes(),b'')

    def test_interrupted_binding_and_restore_reconcile_by_read_without_replay(self):
        # Mutation: repeat a parameter write after its effect completed but reply failed.
        self.stage(); flag=self.root/'fail-private'; flag.write_text('bind')
        with self.assertRaises(ValueError): self.subject.bind(self.session,self.journal)
        self.assertEqual(self.session.result[self.subject.KEY]['path'],'binding')
        flag.unlink(); self.fresh(); self.accepted(self.subject.bind,self.session,self.journal)
        self.assertEqual(sum(n=='firmware-bind' for n,_ in self.calls),1)
        flag.write_text('restore')
        with self.assertRaises(ValueError): self.subject.restore(self.session,self.journal)
        self.assertEqual(self.session.result[self.subject.KEY]['path'],'restoring')
        flag.unlink(); self.fresh(); self.accepted(self.subject.restore,self.session,self.journal)
        self.assertEqual(sum(n=='firmware-restore' for n,_ in self.calls),1)

    def test_foreign_files_links_modes_path_and_busy_stack_retain_ownership(self):
        # Mutation: restore the loader while any WCC/foreign module remains alive.
        self.stage(); self.accepted(self.subject.bind,self.session,self.journal); before=self.parameter.read_bytes()
        busy=self.phone/'sys/module/brcmfmac_wcc'; busy.mkdir()
        with self.assertRaises(ValueError): self.subject.restore(self.session,self.journal)
        self.assertEqual(self.parameter.read_bytes(),before); busy.rmdir(); self.fresh()
        self.parameter.write_bytes(b'/foreign')
        with self.assertRaises(ValueError): self.subject.restore(self.session,self.journal)
        self.assertEqual(self.parameter.read_bytes(),b'/foreign'); self.parameter.write_bytes(before)
        for change in ('extra','mode','link'):
            p=self.target('regulatory.db'); raw=p.read_bytes()
            if change=='extra': self.target('extra').write_bytes(b'foreign')
            elif change=='mode': p.chmod(0o644)
            else: p.unlink(); p.symlink_to(self.target('regulatory.db.p7s'))
            with self.assertRaises(ValueError): self.subject.verify(self.session)
            if change=='extra': self.target('extra').unlink()
            elif change=='mode': p.chmod(0o600)
            else: p.unlink(); p.write_bytes(raw); p.chmod(0o600)
        self.assertEqual(self.parameter.read_bytes(),before)

    def test_saved_schema_scope_and_foreign_journal_refuse_before_capture(self):
        # Mutation: accept an edited saved manifest, boot, directory or schema.
        self.stage(); original=copy.deepcopy(self.session.result[self.subject.KEY]); before=list(self.calls)
        for key,value in [('format',True),('boot_id','99999999-1111-2222-3333-444444444444'),
            ('directory','/foreign'),('manifest',[]),('status','foreign'),('path','foreign')]:
            self.session.result[self.subject.KEY]=dict(original,**{key:value})
            with self.assertRaises(ValueError): self.subject.verify(self.session)
            self.assertEqual(self.calls,before)
        self.session.result[self.subject.KEY]=original
        with self.assertRaises(ValueError): self.subject.bind(self.session,SimpleNamespace(session=object()))
        self.assertEqual(self.calls,before)

    def test_legacy_mode_has_no_firmware_effect_or_journal_change(self):
        # Mutation: implicitly enable firmware in the existing runtime mode.
        del self.session.firmware_data; before=self.journal.path.read_bytes()
        for function,args in [(self.subject.stage,(self.session,)),(self.subject.verify,(self.session,)),
            (self.subject.bind,(self.session,self.journal)),(self.subject.restore,(self.session,self.journal))]:
            self.accepted(function,*args)
        self.assertEqual(self.calls,[]); self.assertEqual(self.journal.path.read_bytes(),before)


class FirmwareSessionMutationProof(unittest.TestCase):
    def test_real_source_mutations(self):
        baseline=unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(FirmwareSessionTests).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures)
        cases=[('intent','test_stage_bind_verify_restore_in_one_boot_and_keep_private_data'),
            ('bytes','test_changed_local_bytes_are_refused_before_wire_effect'),
            ('replay','test_transfer_failure_is_retained_and_never_replayed'),
            ('ready','test_ready_hash_and_boot_are_proved_from_real_generated_shell'),
            ('hash','test_ready_hash_and_boot_are_proved_from_real_generated_shell'),
            ('boot','test_ready_hash_and_boot_are_proved_from_real_generated_shell'),
            ('stack','test_foreign_files_links_modes_path_and_busy_stack_retain_ownership'),
            ('nul','test_stage_bind_verify_restore_in_one_boot_and_keep_private_data'),
            ('state','test_saved_schema_scope_and_foreign_journal_refuse_before_capture'),
            ('legacy','test_legacy_mode_has_no_firmware_effect_or_journal_change')]
        for kind,method in cases:
            tree=ast.parse(SOURCE.read_text()); matches=[]
            for node in ast.walk(tree):
                if kind in ('bytes','replay','ready','state') and isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='require':
                    target={'bytes':'Pinned firmware bytes changed','replay':'Firmware transfer intent must not be replayed','ready':'Firmware staging is incomplete','state':'Firmware saved ownership differs'}[kind]
                    if len(node.args)==2 and isinstance(node.args[1],ast.Constant) and node.args[1].value==target:
                        node.args[0]=ast.Constant(True); matches.append(node)
                elif kind=='intent' and isinstance(node,ast.FunctionDef) and node.name=='save':
                    node.body[-1]=ast.Pass(); matches.append(node)
                elif kind=='stack' and isinstance(node,ast.FunctionDef) and node.name=='empty_stack':
                    node.body=[ast.Return(ast.Constant(''))]; matches.append(node)
                elif kind=='legacy' and isinstance(node,ast.FunctionDef) and node.name=='applicable':
                    node.body=[ast.Return(ast.Constant(True))]; matches.append(node)
                elif kind=='hash' and isinstance(node,ast.Constant) and isinstance(node.value,str) and ' | sha256sum -c -; ' in node.value:
                    node.value=node.value.replace(' | sha256sum -c -; ','; '); matches.append(node)
                elif kind=='nul' and isinstance(node,ast.Constant) and isinstance(node.value,str) and "printf '\\000'" in node.value:
                    node.value=node.value.replace("printf '\\000'","printf '\\n'"); matches.append(node)
                elif kind=='boot' and isinstance(node,ast.FunctionDef) and node.name=='header':
                    old=node.body[-1].value
                    guard=ast.BinOp(ast.BinOp(ast.Constant('test "$(cat /proc/sys/kernel/random/boot_id)" = "'),ast.Add(),ast.Name('boot',ast.Load())),ast.Add(),ast.Constant('"; '))
                    node.body[-1].value=ast.Call(ast.Attribute(old,'replace',ast.Load()),[guard,ast.Constant('')],[]); matches.append(node)
            self.assertEqual(len(matches),1,kind)
            module=importlib.util.module_from_spec(SPEC); exec(compile(ast.fix_missing_locations(tree),str(SOURCE),'exec'),module.__dict__)
            case=FirmwareSessionTests(method); case.subject=module; result=unittest.TestResult(); case.run(result)
            self.assertFalse(result.errors,'Infrastructure error is not a kill: '+kind)
            self.assertTrue(result.failures and all('AssertionError' in text for _,text in result.failures),kind)
        print('N71_FIRMWARE_SESSION_ASSERTION_MUTATIONS_OK 10/10')


if __name__=='__main__': unittest.main()
