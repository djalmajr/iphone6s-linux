"""Real argparse and selectors transport optional firmware without local-check effects."""
import ast
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_n71_firmware_runtime_integration as integration

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'scripts/host/n71-runtime-session.py'
SPEC=importlib.util.spec_from_file_location('firmware_cli_entry',SOURCE)


class FirmwareEntryTests(unittest.TestCase):
    def setUp(self):
        fixture=integration.FirmwareIntegrationTests('test_cli_check_selects_real_private_data_without_effect_or_output')
        self.addCleanup(fixture.doCleanups); self.firmware,self.cli,self.package=fixture.cli_case()
        self.entry=getattr(self,'entry',importlib.util.module_from_spec(SPEC))
        if not hasattr(self.entry,'main'): SPEC.loader.exec_module(self.entry)
        self.entry.__file__=str(self.cli.root/'scripts/host/n71-runtime-session.py')
        self.requests=[]; self.selected=[]; real_run=self.entry.runtime.run; configure=self.firmware.subject.configure
        def witness(root,request):
            self.assertEqual(root,self.cli.root); self.requests.append(request.copy()); return real_run(root,request)
        def selected(session,request):
            configure(session,request); self.selected.append((request.copy(),session.firmware_data))
        for hook in (patch.object(self.entry.runtime,'run',witness),patch.object(self.firmware.subject,'configure',selected)):
            hook.start(); self.addCleanup(hook.stop)
        self.previous=os.getcwd(); os.chdir(self.cli.root); self.addCleanup(os.chdir,self.previous)

    def invoke(self,extra):
        argv=['n71-runtime-session.py','--profile',str(self.cli.profile.relative_to(self.cli.root)),
            '--action','acquire','--check']+extra
        with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()) as output:
            code=self.entry.main()
        return code,output.getvalue()

    def accepted(self,extra):
        try: return self.invoke(extra)
        except (ValueError,OSError) as error: self.fail('Qualified firmware entry refused: '+str(error))

    def before(self):
        return {str(p.relative_to(self.cli.root)):p.read_bytes() for p in self.cli.root.rglob('*') if p.is_file()}

    def test_relative_firmware_reaches_real_selection_without_output_or_effects(self):
        # Mutations: omit the firmware request or fail to make its path absolute.
        before=self.before(); code,text=self.accepted(['--firmware-dir','runtime/firmware'])
        self.assertEqual(code,0); self.assertIn('N71_RUNTIME_LOCAL_GATE_OK',text)
        self.assertIn('firmware',self.requests[0])
        self.assertEqual(self.requests[0]['firmware'],self.package)
        self.assertEqual(self.selected[0][0]['directory'],self.package)
        self.assertEqual([raw for _,raw in self.selected[0][1]],list(self.firmware.fixture.values.values()))
        self.assertEqual(before,self.before()); self.assertIsNone(self.requests[0]['output'])
        self.assertTrue(self.requests[0]['check']); self.assertEqual(self.cli.identity_reads,1)

    def test_absent_option_keeps_exact_legacy_request_and_no_firmware_selection(self):
        # Mutation: add firmware=None to the legacy request instead of omitting it.
        before=self.before(); code,_=self.accepted([])
        self.assertEqual(code,0); self.assertEqual(set(self.requests[0]),{'action','check','profile','source','output'})
        self.assertEqual(self.selected,[]); self.assertEqual(before,self.before())

    def test_invalid_paths_permissions_and_argument_refuse_before_identity(self):
        # Mutations: normalize away scope or accept a public package directory.
        before=self.before()
        for value in ['.',str(self.cli.root/'runtime'/'..'/'firmware')]:
            with self.assertRaises(ValueError): self.invoke(['--firmware-dir',value])
        self.package.chmod(0o755)
        with self.assertRaises(ValueError): self.invoke(['--firmware-dir',str(self.package)])
        self.package.chmod(0o700)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as error:
            self.invoke(['--firmware-dir'])
        self.assertEqual(error.exception.code,2); self.assertEqual(self.cli.identity_reads,0)
        self.assertEqual(self.selected,[]); self.assertEqual(before,self.before())


class FirmwareEntryMutationProof(unittest.TestCase):
    def test_actual_entry_mutations(self):
        baseline=unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(FirmwareEntryTests).run(baseline)
        self.assertFalse(baseline.errors or baseline.failures)
        for kind,method in [('omit','test_relative_firmware_reaches_real_selection_without_output_or_effects'),
            ('relative','test_relative_firmware_reaches_real_selection_without_output_or_effects'),
            ('legacy','test_absent_option_keeps_exact_legacy_request_and_no_firmware_selection')]:
            tree=ast.parse(SOURCE.read_text()); matches=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.If) and any(isinstance(n,ast.Attribute) and n.attr=='firmware_dir' for n in ast.walk(node.test)):
                    if kind=='omit': node.body=[ast.Pass()]; matches.append(node)
                    elif kind=='legacy':
                        node.test=ast.Constant(True)
                        assignment=node.body[0]; assignment.value=ast.Constant(None); matches.append(node)
                elif kind=='relative' and isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='absolute':
                    value=node.func.value
                    if isinstance(value,ast.Attribute) and value.attr=='firmware_dir':
                        node.func=ast.Name('identity',ast.Load()); node.args=[value]; matches.append(node)
            self.assertEqual(len(matches),1,kind)
            module=importlib.util.module_from_spec(SPEC); module.identity=lambda value:value
            exec(compile(ast.fix_missing_locations(tree),str(SOURCE),'exec'),module.__dict__)
            case=FirmwareEntryTests(method); case.entry=module; result=unittest.TestResult(); case.run(result)
            self.assertFalse(result.errors,'Infrastructure error is not a kill: '+kind)
            self.assertTrue(result.failures and all('AssertionError' in text for _,text in result.failures),kind)
        print('N71_FIRMWARE_ENTRY_ASSERTION_MUTATIONS_OK 3/3')


if __name__=='__main__': unittest.main()
