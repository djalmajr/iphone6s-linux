"""Runtime CLI validates real files and Session before explicit handler contracts."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_compose as fixture
import test_n71_runtime_unassigned_stop as source_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_cli as CLI
import n71_held_session as HELD
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_cli.py'
ENTRY_SOURCE = ROOT / 'scripts/host/n71-runtime-session.py'


class RuntimeCliTests(unittest.TestCase):
    subject = CLI

    def setUp(self):
        data=fixture.RuntimeComposeTests('test_real_composer_selects_runtime_diagnostics_and_emits_complete_profile')
        data.setUp(); self.addCleanup(data.doCleanups); self.data=data; self.root=data.root
        self.folder=data.invoke('profile'); self.profile=self.folder/'deployment.json'
        self.metadata_path=self.folder/'provenance.json'; self.metadata=json.loads(self.metadata_path.read_text())
        self.source=self.root/'runtime/router-source'; self.source.mkdir(mode=0o700)
        (self.source/'retained-private.json').write_text('source remains unchanged\n'); (self.source/'retained-private.json').chmod(0o600)
        self.serial=0; self.identity_reads=0; self.cause=0; self.raise_handler=False
        for hook in (patch.object(self.subject.device_profile,'verify',self.identity),
            patch.object(self.subject.device_profile,'ssh_options',return_value=[]),
            patch.object(self.subject.iommu,'payload_image',return_value=None),
            patch.object(self.subject.held,'run',self.held_handler),
            patch.object(self.subject.coordinator,'run',self.runtime_handler),
            patch.object(subprocess,'run',side_effect=AssertionError('Network/process effect in local CLI gate'))):
            hook.start(); self.addCleanup(hook.stop)

    def identity(self):
        self.identity_reads+=1
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'),str(self.profile))
        data=json.loads(self.profile.read_text())
        return {'payload':self.folder/data['payload'],'initramfs':self.folder/data['initramfs'],
            'client_key':self.folder/data['client_key'],'known_hosts':self.folder/data['known_hosts'],
            'sha256':data['sha256'],'initramfs_sha256':data['initramfs_sha256'],'host_key_alias':data['host_key_alias']}

    def witness(self, session, data):
        self.assertTrue(session.driver_runtime and session.scan_hold and session.resource_capable and session.iommu_parent)
        self.assertEqual(session.modules,self.data.data.modules); self.assertEqual(session.driver_module_data,self.data.data.drivers)
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'),str(self.profile))
        if self.raise_handler: raise OSError('Synthetic transport interruption')
        path=session.output/'handler-contract-private.json'
        with path.open('x') as file: json.dump(data,file)

    def held_handler(self, session, identity, *, root, source=None, assign=False):
        self.assertEqual(root,self.root)
        self.witness(session,{'handler':'held','action':'assign' if assign else 'acquire',
            'source':str(source) if source else None,'identity':identity,'drivers':session.driver_modules})
        return int(self.cause!=0)

    def runtime_handler(self, session, request):
        self.assertEqual(set(request),{'action','root','source','identity'}); self.assertEqual(request['root'],self.root)
        self.witness(session,{'handler':'runtime','action':request['action'],'source':str(request['source']),
            'identity':request['identity'],'drivers':session.driver_modules})
        return {'action':request['action'],'phase':'retained','primary_error':self.cause,'successful':self.cause==0}

    def request(self, action='acquire', *, check=True):
        self.serial+=1
        return {'action':action,'check':check,'profile':self.profile,'source':None if action=='acquire' else self.source,
            'output':None if check else self.root/'runtime'/('operation-'+str(self.serial))}

    def accepted(self, request):
        try:
            with contextlib.redirect_stdout(io.StringIO()) as stream: code=self.subject.run(self.root,request)
            return code,stream.getvalue()
        except (ValueError,OSError) as error: self.fail('Qualified runtime CLI refused: '+str(error))

    def test_real_entry_and_local_check_preserve_files_without_handler_or_output(self):
        # Mutations: ignore --check, create an output or route it to a handler effect.
        before={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        environment=os.environ.get('IPHONE_LINUX_PROFILE')
        code,text=self.accepted(self.request()); self.assertEqual(code,0); self.assertIn('N71_RUNTIME_LOCAL_GATE_OK',text)
        spec=importlib.util.spec_from_file_location('runtime_cli_entry',ENTRY_SOURCE)
        entry=importlib.util.module_from_spec(spec); spec.loader.exec_module(entry)
        entry.__file__=str(self.root/'scripts/host/n71-runtime-session.py'); entry.runtime=self.subject
        argv=['n71-runtime-session.py','--profile',str(self.profile),'--action','acquire','--check']
        with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()): self.assertEqual(entry.main(),0)
        self.assertEqual(before,{str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'),environment)

    def test_scope_manifest_and_module_hash_refuse_before_identity_or_effect(self):
        # Mutations: bypass exact scope/manifest/bytes gates and read identity before validation.
        before=self.identity_reads
        for key,value in [('format',True),('pcie_driver_runtime',False),('pcie_iommu_parent',1),
            ('module_automatic_load',True),('requires_explicit_run',False),('kernel_release','foreign'),
            ('reg_on_module_sha256','f'*64),('driver_modules',[])]:
            changed=dict(self.metadata,**{key:value}); self.metadata_path.write_text(json.dumps(changed))
            with self.subTest(key=key),self.assertRaises(ValueError): self.subject.run(self.root,self.request())
        self.metadata_path.write_text(json.dumps(self.metadata))
        path=self.folder/'rfkill.ko'; raw=path.read_bytes(); path.write_bytes(raw[:64]+bytes([raw[64]^1])+raw[65:])
        with self.assertRaises(ValueError): self.subject.run(self.root,self.request())
        path.write_bytes(raw); path=self.folder/'n71-pcie-diagnostic.ko'; raw=path.read_bytes(); path.write_bytes(raw+b'x')
        with self.assertRaises(ValueError): self.subject.run(self.root,self.request())
        self.assertEqual(self.identity_reads,before)
        self.assertFalse(any(self.root.rglob('handler-contract-private.json')))

    def test_request_paths_and_private_ownership_refuse_before_identity(self):
        # Mutations: lose source/action scope, allow existing/shared output or bypass private ownership.
        request=self.request(); changes=[dict(request,check=1),dict(request,extra=True),dict(request,action='unknown'),
            dict(request,source=self.source),dict(request,action='observe'),dict(request,check=False),
            dict(request,profile=self.root/'runtime/outside.json'),dict(self.request('observe',check=False),output=self.source),
            dict(self.request(check=False),output=self.folder),dict(self.request(check=False),output=self.root/'outside'),
            dict(self.request(),output=self.source)]
        dangling=self.root/'runtime/dangling'; dangling.symlink_to(self.root/'runtime/missing-output')
        changes.append(dict(self.request(),output=dangling))
        for changed in changes:
            with self.subTest(action=changed.get('action')),self.assertRaises(ValueError): self.subject.run(self.root,changed)
        self.source.chmod(0o755)
        with self.assertRaises(ValueError): self.subject.run(self.root,self.request('observe',check=False))
        self.assertEqual(self.identity_reads,0)

    def test_each_explicit_action_writes_only_its_handler_contract(self):
        # Mutations: route runtime to legacy release, change source/assignment or omit WCC in Session.
        original=(self.source/'retained-private.json').read_bytes()
        for action in ('acquire', 'assign', 'start', 'observe', 'stop'):
            request=self.request(action,check=False); code,_=self.accepted(request); self.assertEqual(code,0)
            self.assertEqual({p.name for p in request['output'].iterdir()},{'handler-contract-private.json'})
            value=json.loads((request['output']/'handler-contract-private.json').read_text())
            self.assertEqual(value['handler'],'held' if action in ('acquire','assign') else 'runtime')
            self.assertEqual(value['action'],action); self.assertEqual(value['source'],None if action=='acquire' else str(self.source))
            self.assertEqual(value['drivers'],self.data.data.selected['drivers'])
            self.assertEqual(set(value['identity']),{'deployment_sha256','payload_sha256','initramfs_sha256','modules'})
            self.assertEqual(value['identity']['modules'],{r['module']:r['sha256'] for r in self.data.data.selected['diagnostics']})
            self.assertEqual(request['output'].stat().st_mode&0o777,0o700)
            self.assertEqual((request['output']/'handler-contract-private.json').stat().st_mode&0o777,0o600)
        self.assertEqual((self.source/'retained-private.json').read_bytes(),original)

    def test_negative_cause_and_transport_restore_environment_and_umask(self):
        # Mutations: turn a negative coordinator outcome into exit0 or skip restoration on failure.
        saved=os.umask(0o022)
        try:
            with patch.dict(os.environ):
                os.environ.pop('IPHONE_LINUX_PROFILE',None)
                self.cause=-13; code,text=self.accepted(self.request('start',check=False))
                self.assertEqual(code,1); self.assertIn('"primary_error": -13',text)
                self.assertIsNone(os.environ.get('IPHONE_LINUX_PROFILE'))
                current=os.umask(0o022); self.assertEqual(current,0o022)
                os.environ['IPHONE_LINUX_PROFILE']='existing-profile.invalid'; self.raise_handler=True
                with self.assertRaises(OSError): self.subject.run(self.root,self.request('observe',check=False))
                self.assertEqual(os.environ.get('IPHONE_LINUX_PROFILE'),'existing-profile.invalid')
                current=os.umask(0o022); self.assertEqual(current,0o022)
        finally: os.umask(saved)

    def test_local_saved_source_uses_real_journal_loader_without_promotion(self):
        # Mutation: skip source validation or run recovery/handler instead of passive load_source.
        data=source_fixture.UnassignedStopTests('test_observe_stop_and_repeated_stop_preserve_one_boot_without_assignment')
        data.setUp(); self.addCleanup(data.doCleanups)
        case=data.phone; session=case.session; source=self.root/'runtime/saved'; source.mkdir(mode=0o700)
        session.output=source; session.modules=self.data.data.modules
        session.driver_modules=self.data.data.selected['drivers']
        case.case.output=source; case.phone.output=source
        with patch.dict(os.environ,{'IPHONE_LINUX_PROFILE':str(self.profile)}):
            identity=HELD.identity(self.profile,self.identity(),session.modules)
        journal=HELD.Journal(session,identity); journal.baseline=case.case.journal.baseline
        case.phone.journal=case.case.journal=journal; journal.save(); journal.finish()
        before={p.name:p.read_bytes() for p in source.iterdir()}
        request=dict(self.request('observe'),source=source)
        code,_=self.accepted(request); self.assertEqual(code,0)
        self.assertEqual(before,{p.name:p.read_bytes() for p in source.iterdir()})
        state=source/'held-state-private.json'; changed=json.loads(state.read_text()); changed['identity']['deployment_sha256']='f'*64
        state.write_text(json.dumps(changed))
        with self.assertRaises(ValueError): self.subject.run(self.root,request)
        self.assertFalse(any(self.root.rglob('handler-contract-private.json')))


class RuntimeCliMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeCliTests))
        self.assertTrue(baseline.wasSuccessful(),baseline.failures+baseline.errors)
        scope='test_scope_manifest_and_module_hash_refuse_before_identity_or_effect'
        paths='test_request_paths_and_private_ownership_refuse_before_identity'
        dispatch='test_each_explicit_action_writes_only_its_handler_contract'
        restore='test_negative_cause_and_transport_restore_environment_and_umask'
        mutations=[
            ('request-schema',"set(request) == {'action', 'check', 'output', 'profile', 'source'}",'True',paths),
            ('check-boolean',"type(request['check']) is bool",'True',paths),
            ('source-action-scope',"(request['action'] == 'acquire')",'True',paths),
            ('new-output','not output.exists()','True',paths),
            ('linked-output','not output.is_symlink()','True',paths),
            ('private-source','device_profile.protected(source, directory=True)','pass',paths),
            ('format-type',"type(metadata.get('format')) is int",'True',scope),
            ('exact-runtime-scope','all(metadata.get(name) is True for name in TRUE_FLAGS)','True',scope),
            ('wcc-manifest',"metadata.get('driver_modules') == [record for record, _ in selected['drivers']]",'True',scope),
            ('reg-identity',"metadata.get('reg_on_module_sha256') == selected['diagnostics'][1]['sha256']",'True',scope),
            ('diagnostic-before-identity',"link.module_bytes(request['profile'].parent, record, release=RELEASE)","(request['profile'].parent / record['module']).read_bytes()",scope),
            ('explicit-session-wcc',"runtime=selected['drivers']",'runtime=None',dispatch),
            ('local-check',"if request['check']:",'if False:','test_real_entry_and_local_check_preserve_files_without_handler_or_output'),
            ('passive-source-loader',"held.load_source(session, root, request['source'], identity)",'pass','test_local_saved_source_uses_real_journal_loader_without_promotion'),
            ('runtime-vs-legacy',"request['action'] in ('acquire', 'assign')",'True',dispatch),
            ('assign-action',"assign=request['action'] == 'assign'",'assign=False',dispatch),
            ('negative-exit',"return 0 if result['successful'] else 1",'return 0',restore),
            ('environment-unset',"os.environ.pop('IPHONE_LINUX_PROFILE', None)",'pass',restore),
            ('environment-restore',"os.environ['IPHONE_LINUX_PROFILE'] = previous",'pass',restore),
            ('umask-restore','os.umask(previous_mask)','pass',restore),
        ]
        source=SOURCE.read_text()
        for name,before,after,method in mutations:
            with self.subTest(name=name):
                self.assertEqual(source.count(before),1,name)
                module=ModuleType('runtime_cli_mutant'); module.__file__=str(SOURCE)
                exec(compile(ast.parse(source.replace(before,after,1)),str(SOURCE),'exec'),module.__dict__)
                case=type('MutatedRuntimeCliTests',(RuntimeCliTests,),{'subject':module})
                result=unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors,[],name); self.assertGreater(len(result.failures),0,name)
                print('N71_RUNTIME_CLI_MUTATION_KILLED',name,'AssertionError')


if __name__=='__main__': unittest.main()
