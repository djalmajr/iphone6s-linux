"""An acquired runtime can be observed and stopped without inventing assignment."""
import ast
import copy
import io
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import test_n71_driver_runtime_session as fixture
import test_n71_driver_runtime_stage as native_fixture
import test_n71_resource_result as resource_fixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_driver_runtime_lifetime as LIFETIME
import n71_driver_runtime_session as COORDINATOR
import n71_held_session as HELD
import n71_session_history as HISTORY
INITIAL = 'N71_PCIE_RESOURCES ready=1 attempted=0 assigned=0 pending=0 claimed=0 active=0 error=0\n'


def no_assignment(text):
    return ''.join(line + '\n' for line in text.splitlines() if 'N71_PCIE_RESOURCE_' not in line)


class UnassignedStopTests(unittest.TestCase):
    lifetime = LIFETIME
    coordinator = COORDINATOR

    def setUp(self):
        class UnassignedPhone(fixture.RuntimeSessionTests):
            def text(self):
                return super().text().replace(resource_fixture.GETTER, INITIAL)
        phone = UnassignedPhone('test_start_observe_and_stop_share_one_boot_and_preserve_origin')
        phone.setUp(); self.addCleanup(phone.doCleanups); self.phone = phone
        phone.subject = self.coordinator
        self.session = phone.session
        self.session.resource_attempted = False; self.session.resource_assignment = None
        self.session.result['resource_assignment'] = None
        phone.phone.kernel_history = no_assignment(phone.phone.kernel_history)
        phone.provider_tail = no_assignment(phone.provider_tail)
        phone.template_history = no_assignment(phone.template_history)
        phone.cleanup_template = no_assignment(phone.cleanup_template)
        phone.case.full_history = no_assignment(phone.case.full_history)
        phone.phone.journal = phone.case.journal
        phone.phone.journal.proofs = {}; phone.phone.journal.save(); phone.phone.journal.finish()
        for hook in (patch.dict(sys.modules, {'n71_driver_runtime_lifetime':self.lifetime}),
            patch.object(self.coordinator, 'lifetime', self.lifetime)):
            hook.start(); self.addCleanup(hook.stop)
        self.origin = {p.name:p.read_bytes() for p in phone.origin.iterdir()}

    def accepted(self, action):
        try: return self.phone.accepted(action)
        except (ValueError, OSError) as error: self.fail('Proved unassigned session refused: ' + str(error))

    def observation(self):
        journal = self.phone.phone.journal
        return {'text':self.phone.text(),'presence':(1,1,0),'context':self.coordinator.context(journal)}

    def removed(self):
        self.accepted('stop'); self.session = self.phone.session
        journal_path = self.session.output / 'held-state-private.json'
        data = json.loads(journal_path.read_text())
        context = {'baseline':data['baseline'], 'checkpoint':HISTORY.read_private(self.session.output,data['checkpoint']['name']),
            'proofs':{name:HISTORY.read_private(self.session.output,name+'-proof-private.log') for name in data['proofs']}}
        return self.phone.text(), context

    def test_observe_stop_and_repeated_stop_preserve_one_boot_without_assignment(self):
        # Mutations: require a fabricated assignment or repeat cleanup after a proved stop.
        self.assertEqual(self.accepted('observe'),dict(action='observe',phase='retained',primary_error=0,successful=True))
        self.assertEqual(self.phone.effects(),[])
        self.assertEqual(self.accepted('stop'),dict(action='stop',phase='stopped',primary_error=0,successful=True))
        self.assertEqual(self.phone.effects(),['held-cleanup','held-pcie-unload','held-restore','held-reg-unload'])
        self.assertFalse(self.phone.case.pcie or self.phone.case.reg or self.phone.case.active)
        self.assertFalse(self.phone.session.resource_attempted); self.assertIsNone(self.phone.session.resource_assignment)
        self.assertEqual(self.phone.session.driver_runtime_journal,[]); self.assertEqual(self.phone.session.driver_module_journal,[])
        effects=list(self.phone.effects()); self.assertEqual(self.accepted('stop')['phase'],'stopped')
        self.assertEqual(self.phone.effects(),effects)
        self.assertEqual(self.origin,{p.name:p.read_bytes() for p in self.phone.origin.iterdir()})
        data=json.loads((self.phone.session.output/'held-state-private.json').read_text())
        self.assertNotIn('resource-assignment',data['proofs']); self.assertIsNone(data['result']['resource_assignment'])

    def test_start_without_assignment_refuses_and_keeps_providers(self):
        # Mutation: allow start before assignment, causing native prepare or WCC effects.
        with self.assertRaisesRegex(ValueError, 'Runtime start requires a successful assignment'):
            self.phone.run_action('start')
        self.assertEqual(self.phone.effects(),[])
        self.assertTrue(self.phone.case.pcie and self.phone.case.reg and self.phone.case.active)
        self.assertEqual(self.origin,{p.name:p.read_bytes() for p in self.phone.origin.iterdir()})

    def test_assignment_intent_summary_and_proof_cannot_be_silently_lost(self):
        # Mutations: treat attempted assignment, a saved summary or a proof as unassigned.
        observation=self.observation(); original=dict(self.session.result)
        for value in (True,0,None):
            self.session.resource_attempted=value
            with self.subTest(intent=value),self.assertRaises(ValueError): self.coordinator.validate(self.session,observation)
        self.session.resource_attempted=False
        self.session.result['resource_assignment']={'error':0}
        with self.assertRaises(ValueError): self.coordinator.validate(self.session,observation)
        self.session.result=original
        altered=copy.deepcopy(observation); altered['context']['proofs']['resource-assignment']='not a valid assignment'
        with self.assertRaises(ValueError): self.coordinator.validate(self.session,altered)
        self.assertEqual(self.phone.effects(),[])

    def test_boot_history_stack_native_and_msi_drift_refuse_without_effect(self):
        # Mutations: skip checkpoint/native ownership or ignore another module/manual MSI lease.
        observation=self.observation(); text=observation['text']
        native=next(line for line in text.splitlines() if line.startswith('N71_PCIE_DRIVER '))
        cases=[text.replace(native_fixture.BOOT,'87654321-1234-1234-1234-123456789abc'),
            text.replace(native_fixture.BASE,''),text+'[ 800.000000] N71_UNREGISTERED_EFFECT\n',
            text.replace('name=rfkill present=0 state=-','name=rfkill present=1 state=live'),
            text.replace(native,native.replace('pending=0 active=0','pending=1 active=1')),
            text.replace('owner=0 phase=0','owner=1 phase=1')]
        for changed in cases:
            self.assertNotEqual(changed,text)
            with self.subTest(tail=changed[-60:]),self.assertRaises(ValueError):
                self.coordinator.validate(self.session,dict(observation,text=changed))
        altered=copy.deepcopy(observation); altered['context']['checkpoint']=None
        with self.assertRaises(ValueError): self.coordinator.validate(self.session,altered)
        altered=copy.deepcopy(observation)
        altered['text']+=native_fixture.native('prepare',native_fixture.PREPARED,{'stamp':8000})
        altered['context']['checkpoint']=altered['text']
        with self.assertRaises(ValueError): self.coordinator.validate(self.session,altered)
        self.assertEqual(self.phone.effects(),[])

    def test_removed_source_requires_genuine_cleanup_and_unload_without_native_effects(self):
        # Mutations: accept an unassigned intent or omit cleanup/unload/native history proof.
        text,context=self.removed()
        self.assertTrue(self.lifetime.removed(self.session,text,context)['resource_cleanup_verified'])
        for name in ('pcie-cleanup','pcie-unload'):
            altered=copy.deepcopy(context); altered['proofs'].pop(name)
            with self.subTest(proof=name),self.assertRaises(ValueError): self.lifetime.removed(self.session,text,altered)
        self.session.resource_attempted=True
        with self.assertRaises(ValueError): self.lifetime.removed(self.session,text,context)
        self.session.resource_attempted=False
        self.session.result['resource_assignment']={'error':0}
        with self.assertRaises(ValueError): self.lifetime.removed(self.session,text,context)
        self.session.result['resource_assignment']=None
        unknown=native_fixture.native('prepare',native_fixture.PREPARED,{'stamp':8000})
        with self.assertRaises(ValueError): self.lifetime.removed(self.session,text+unknown,context)
        self.assertEqual(self.phone.session.driver_runtime_journal,[])


class UnassignedStopMutations(unittest.TestCase):
    def test_source_mutations_fail_by_assertion(self):
        baseline=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnassignedStopTests))
        self.assertTrue(baseline.wasSuccessful(),baseline.failures+baseline.errors)
        cycle='test_observe_stop_and_repeated_stop_preserve_one_boot_without_assignment'
        intent='test_assignment_intent_summary_and_proof_cannot_be_silently_lost'
        drift='test_boot_history_stack_native_and_msi_drift_refuse_without_effect'
        sources={'lifetime':ROOT/'scripts/host/n71_driver_runtime_lifetime.py','coordinator':ROOT/'scripts/host/n71_driver_runtime_session.py'}
        mutations=[
            ('unattempted-intent','lifetime',"getattr(session, 'resource_attempted', None) is False",'True',intent),
            ('saved-summary','lifetime',"session.result.get('resource_assignment') is None",'True',intent),
            ('no-assignment-proof','lifetime',"'resource-assignment' not in proofs",'True',intent),
            ('unassigned-cleanup','lifetime','or (not native and not wlan and unassigned(session, proofs))','or False',cycle),
            ('unassigned-observation','coordinator','if assignment is None:','if False:',cycle),
            ('checkpoint-required','coordinator',"prior = value['checkpoint']; require(isinstance(prior, str)","prior = text; require(isinstance(prior, str)",drift),
            ('native-owners','coordinator',"all(state[name] == 0 for name in native.result.OWNERS\n            + ('pending', 'published', 'operation_error', 'reads', 'error', 'session_error'))",'True',drift),
            ('no-unregistered-action','coordinator','not any(native.result.ACTION_MARKER in line for line in lines[len(baseline):])','True',drift),
            ('start-assignment','coordinator',"session.resource_assignment is not None\n        and session.resource_assignment['assignment_verified'] and session.resource_assignment['error'] == 0",'True','test_start_without_assignment_refuses_and_keeps_providers'),
        ]
        for name,field,before,after,method in mutations:
            with self.subTest(name=name):
                path=sources[field]; source=path.read_text(); self.assertEqual(source.count(before),1,name)
                module=ModuleType('runtime_unassigned_mutant')
                exec(compile(ast.parse(source.replace(before,after,1)),str(path),'exec'),module.__dict__)
                case=type('MutatedUnassignedStopTests',(UnassignedStopTests,),{field:module})
                result=unittest.TextTestRunner(stream=io.StringIO()).run(case(method))
                self.assertEqual(result.errors,[],name); self.assertGreater(len(result.failures),0,name)
                print('N71_UNASSIGNED_STOP_MUTATION_KILLED',name,'AssertionError')


if __name__=='__main__': unittest.main()
