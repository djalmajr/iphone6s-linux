"""Qualified files and the real composer emit an explicit private runtime profile."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_profile as fixture
import test_n71_diagnostic_held_profile as held_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_compose as COMPOSE
import n71_driver_runtime_build as BUILD
import n71_driver_modules as WLAN
SOURCE = ROOT / 'scripts/host/n71_driver_runtime_compose.py'
COMPOSER_SOURCE = ROOT / 'scripts/build/compose-n71-diagnostic.py'
SPEC = importlib.util.spec_from_file_location('runtime_file_composer', COMPOSER_SOURCE)
COMPOSER = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(COMPOSER)


class RuntimeComposeTests(unittest.TestCase):
    subject = COMPOSE
    composer = COMPOSER

    def setUp(self):
        data=fixture.RuntimeProfileTests('test_real_session_owns_two_diagnostics_and_five_drivers_separately')
        data.setUp(); self.addCleanup(data.doCleanups); self.data=data; self.root=data.root.resolve()
        self.directory=data.output.resolve()
        held=held_fixture.HeldProfileTests('test_complete_pair_provenance_payload_and_private_modes')
        held.setUp(); self.addCleanup(held.doCleanups); self.held=held
        for name in ('runtime/source','runtime/diagnostic','artifacts'):
            shutil.copytree(held.root/name,self.root/name,dirs_exist_ok=True)
        shutil.copyfile(held.root/'docs/evidence/m1n1-rebuild.json',self.root/'docs/evidence/m1n1-rebuild.json')
        self.source={k:self.root/v.relative_to(held.root) if isinstance(v,Path) else v for k,v in held.source.items()}
        self.request={'directory':self.directory,'release':WLAN.RELEASE,'pcie_sha256':data.selected['diagnostics'][0]['sha256']}
        self.args=[arg.replace(str(held.root),str(self.root)) for arg in held.args]
        self.args+=['--module',str(self.directory/'n71-pcie-diagnostic.ko'),'--module-sha256',self.request['pcie_sha256']]
        self.flags=['--pcie-aspm-off','--pcie-scan-hold','--pcie-resource-capable','--pcie-iommu-parent',
            '--pcie-driver-runtime','--wcc-dir',str(self.directory),'--reg-on-module',str(self.directory/'n71-wlan-power-diagnostic.ko')]
        for hook in (patch.object(self.composer,'ROOT',self.root),
            patch.object(self.composer.DIAGNOSTIC.TUNABLES,'ROOT',self.root),
            patch.object(self.composer,'n71_driver_runtime_compose',self.subject)):
            hook.start(); self.addCleanup(hook.stop)

    def selected(self):
        try: return self.subject.select(self.root,self.request)
        except (ValueError,OSError) as error: self.fail('Qualified private WCC files refused: '+str(error))

    def invoke(self, name, flags=None, identity=None):
        output=self.root/'runtime'/name
        argv=self.args+(self.flags if flags is None else flags)+['--output-dir',str(output)]
        # Kernel/identity I/O are synthetic here; production composition separately uses all real gates.
        with (patch.object(self.composer.device_profile,'verify',identity or (lambda:self.source)),
            patch.object(self.composer.KERNEL,'kernel_inputs',return_value=(self.held.kernel,self.held.record)),
            patch.object(self.composer.n71_iommu_build,'kernel_image',return_value=None),
            patch.object(sys,'argv',argv),patch.dict(os.environ),contextlib.redirect_stdout(io.StringIO())):
            self.composer.main()
        return output

    def test_exact_selection_owns_five_files_and_does_not_copy_foreign_vendors(self):
        # Mutations: select a foreign stack, omit a selected file or overwrite private inputs.
        before={p.name:p.read_bytes() for p in self.directory.iterdir() if p.is_file()}
        selected=self.selected()
        self.assertEqual(selected['diagnostics'],self.data.selected['diagnostics'])
        self.assertEqual(selected['drivers'],self.data.drivers)
        self.assertTrue(all(type(raw) is bytes for _,raw in selected['drivers']))
        selected['drivers'][0][0]['sha256']='f'*64
        self.assertNotEqual(self.selected()['drivers'][0][0]['sha256'],'f'*64)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.directory.iterdir() if p.is_file()})

    def test_schema_release_and_caller_base_are_revalidated(self):
        # Mutations: bypass explicit selection or accept an unqualified caller/kernel pair.
        for request in (None,dict(self.request,extra=True),dict(self.request,release='foreign'),
            dict(self.request,pcie_sha256='f'*64),dict(self.request,directory='runtime')):
            with self.subTest(request=request),self.assertRaises(ValueError): self.subject.select(self.root,request)
        path=self.root/'docs/evidence/n71-brcmfmac-pcie-modules-qualified.json'; proof=json.loads(path.read_text())
        proof['baseline']['source_head']='f'*40; path.write_text(json.dumps(proof))
        with self.assertRaises(ValueError): self.subject.select(self.root,self.request)

    def test_missing_hash_size_permissions_and_links_refuse_before_output(self):
        # Mutations: drop private-file protection or ignore WCC size/SHA checks.
        path=self.data.output/self.data.selected['drivers'][0]['module']; raw=path.read_bytes()
        path.unlink()
        with self.assertRaises(OSError): self.subject.select(self.root,self.request)
        for changed in (raw+b'x',raw[:64]+bytes([raw[64]^1])+raw[65:]):
            path.write_bytes(changed); path.chmod(0o600)
            with self.assertRaises(ValueError): self.subject.select(self.root,self.request)
        path.write_bytes(raw); path.chmod(0o644)
        with self.assertRaises(ValueError): self.subject.select(self.root,self.request)
        path.chmod(0o600); other=self.data.output/'original.ko'; path.rename(other); path.symlink_to(other)
        with self.assertRaises(ValueError): self.subject.select(self.root,self.request)
        path.unlink(); os.link(other,path)
        with self.assertRaises(ValueError): self.subject.select(self.root,self.request)
        path.unlink(); other.rename(path); self.data.output.chmod(0o755)
        with self.assertRaises(ValueError): self.subject.select(self.root,self.request)

    def test_real_elf_and_vermagic_must_match_even_if_metadata_claims_qualification(self):
        # Mutation: trust metadata/SHA alone and omit real ELF/AArch64/vermagic validation.
        path=self.data.output/self.data.selected['drivers'][0]['module']; original=path.read_bytes()
        proof_path=self.root/'docs/evidence/n71-brcmfmac-pcie-modules-qualified.json'; proof=json.loads(proof_path.read_text())
        proof['modules'][WLAN.MODULE_PATHS[0]]['bytes']=len(original)+1; proof_path.write_text(json.dumps(proof))
        with self.assertRaisesRegex(ValueError,'file size differs'): self.subject.select(self.root,self.request)
        cases=[b'not ELF'+original[7:],original[:4]+b'\x01'+original[5:],original+b'\0vermagic='+self.data.drivers[0][0]['vermagic'].encode()+b'\0']
        machine=bytearray(original); struct.pack_into('<H',machine,18,62); cases.append(bytes(machine))
        for changed in cases:
            path.write_bytes(changed); entry=proof['modules'][WLAN.MODULE_PATHS[0]]
            entry.update(bytes=len(changed),sha256=hashlib.sha256(changed).hexdigest()); proof_path.write_text(json.dumps(proof))
            BUILD.select(self.root,{k:v for k,v in self.request.items() if k!='directory'})
            with self.assertRaisesRegex(ValueError,'relocatable AArch64 ABI'): self.subject.select(self.root,self.request)

    def test_real_composer_selects_runtime_diagnostics_and_emits_complete_profile(self):
        # Mutations: keep the legacy caller, omit WCC files/provenance or introduce automatic load.
        original={k:v.read_bytes() for k,v in self.source.items() if isinstance(v,Path)}
        environment=dict(os.environ)
        try: output=self.invoke('complete')
        except (ValueError,OSError) as error: self.fail('Qualified runtime composition refused: '+str(error))
        expected=held_fixture.PROFILE_FILES|{record['module'] for record,_ in self.data.drivers}
        self.assertEqual({p.name for p in output.iterdir()},expected)
        for name,raw in self.data.files.items(): self.assertEqual((output/name).read_bytes(),raw)
        metadata=json.loads((output/'provenance.json').read_text())
        self.assertIs(metadata.get('pcie_driver_runtime'),True); self.assertEqual(metadata.get('driver_modules'),self.data.selected['drivers'])
        self.assertIs(metadata['module_automatic_load'],False); self.assertIs(metadata['default_profile_changed'],False)
        self.assertIs(metadata['physical_boot_tested'],False); self.assertIs(metadata['wifi_verified'],False)
        self.assertEqual((output/'initramfs.gz').read_bytes(),original['initramfs'])
        self.assertEqual((output/'client_ed25519').read_bytes(),original['client_key'])
        self.assertEqual((output/'known_hosts').read_bytes(),original['known_hosts'])
        self.assertEqual(original,{k:v.read_bytes() for k,v in self.source.items() if isinstance(v,Path)})
        self.assertTrue(dict(os.environ)==environment, 'Composer changed its process environment')
        self.assertEqual(output.stat().st_mode&0o777,0o700)
        self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in output.iterdir()))

    def test_runtime_scope_refuses_before_identity_access_or_output(self):
        # Mutations: remove opt-in guards and touch identities before checking runtime scope.
        def identity(): self.fail('Identity accessed before runtime scope was validated')
        for flag in ('--pcie-aspm-off','--pcie-scan-hold','--pcie-resource-capable','--pcie-iommu-parent','--pcie-driver-runtime'):
            flags=list(self.flags); flags.remove(flag)
            with self.subTest(flag=flag),self.assertRaises(ValueError): self.invoke('refused',flags,identity)
        flags=self.flags[:-2]
        with self.assertRaises(ValueError): self.invoke('refused',flags,identity)
        flags=[flag for flag in self.flags if flag not in ('--wcc-dir',str(self.directory))]
        with self.assertRaises(ValueError): self.invoke('refused',flags,identity)
        self.assertFalse((self.root/'runtime/refused').exists())


class RuntimeComposeMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeComposeTests))
        self.assertTrue(baseline.wasSuccessful(),baseline.failures+baseline.errors)
        files='test_missing_hash_size_permissions_and_links_refuse_before_output'
        elf='test_real_elf_and_vermagic_must_match_even_if_metadata_claims_qualification'
        full='test_real_composer_selects_runtime_diagnostics_and_emits_complete_profile'
        scope='test_runtime_scope_refuses_before_identity_access_or_output'
        sources={'subject':SOURCE,'composer':COMPOSER_SOURCE}
        mutations=[
            ('request-schema','subject',"set(request) == {'directory', 'pcie_sha256', 'release'}",'True','test_schema_release_and_caller_base_are_revalidated'),
            ('private-directory','subject','device_profile.protected(folder, directory=True)','pass',files),
            ('private-file','subject','device_profile.protected(path)','pass',files),
            ('file-size','subject',"path.stat().st_size == record['bytes']",'True',elf),
            ('file-sha','subject',"hashlib.sha256(raw).hexdigest() == record['sha256']",'True',files),
            ('elf-header','subject',"raw[:7] == b'\\x7fELF\\x02\\x01\\x01'",'True',elf),
            ('aarch64','subject',"struct.unpack_from('<HH', raw, 16) == (1, 183)",'True',elf),
            ('unique-vermagic','subject','raw.count(magic) == 1','raw.count(magic) >= 1',elf),
            ('five-owned-files','subject','drivers.append((record, raw))','pass','test_exact_selection_owns_five_files_and_does_not_copy_foreign_vendors'),
            ('runtime-diagnostic','composer',"if getattr(options, 'pcie_driver_runtime', False):",'if False:',full),
            ('wcc-output','composer',"for entry, raw in runtime_modules['drivers']:",'for entry, raw in []:',full),
            ('runtime-provenance','composer',"provenance.update(pcie_driver_runtime=True, driver_modules=[entry for entry, _ in runtime_modules['drivers']])",'pass',full),
            ('explicit-iommu','composer','not options.pcie_iommu_parent or options.wcc_dir is None','options.wcc_dir is None',scope),
            ('wcc-directory-required','composer','not options.pcie_iommu_parent or options.wcc_dir is None','not options.pcie_iommu_parent',scope),
            ('explicit-runtime','composer','if options.wcc_dir is not None and not options.pcie_driver_runtime:','if False:',scope),
        ]
        for name,field,before,after,method in mutations:
            with self.subTest(name=name):
                path=sources[field]; source=path.read_text(); self.assertEqual(source.count(before),1,name)
                module=ModuleType('runtime_compose_mutant'); module.__file__=str(path)
                exec(compile(ast.parse(source.replace(before,after,1)),str(path),'exec'),module.__dict__)
                case=type('MutatedRuntimeComposeTests',(RuntimeComposeTests,),{field:module})
                result=unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors,[],name); self.assertGreater(len(result.failures),0,name)
                print('N71_RUNTIME_COMPOSE_MUTATION_KILLED',name,'AssertionError')


if __name__=='__main__': unittest.main()
