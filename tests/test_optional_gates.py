"""Optional gates: policy, JSON/HTTP, UI, and archival guard regression."""
import copy
import json
import subprocess
import tempfile
from pathlib import Path
from test_console_rc3 import RC3HTTPTests
from test_skill_studio import ConsoleTests
from scaffold.agentflow_console.core import ManagementError

ROOT = Path(__file__).resolve().parents[1]

class GatePolicyTests(ConsoleTests):
    def test_custom_profile_gate_defaults_on(self):
        self.manager.create_profile('ux-mngr','화면 설계 전문가')
        p=self.manager.profile('ux-mngr')
        self.assertEqual(p['approval_gates'],{'GATE1':True,'GATE2':True})
        self.manager.activate('ux-mngr',1)
        c=self.manager.runtime_contract()
        self.assertEqual(c['protected_workflow']['human_gates'],['GATE1','GATE2'])
        self.assertTrue(next(s for s in c['tree']['stages'] if s['id']=='GATE1')['enabled'])

    def test_custom_profile_can_independently_toggle_both_gates(self):
        self.manager.create_profile('ux-mngr','화면 설계 전문가')
        for g1,g2 in ((False,True),(True,False),(False,False),(True,True)):
            p=self.manager.profile('ux-mngr');p['approval_gates']={'GATE1':g1,'GATE2':g2}
            self.manager.save_profile(p)
            self.manager.activate('ux-mngr',self.manager.active()['generation'])
            c=self.manager.runtime_contract()
            self.assertEqual(c['approval_gates'],{'GATE1':g1,'GATE2':g2})
            self.assertEqual(c['protected_workflow']['skipped_gates'],[g for g,v in [('GATE1',g1),('GATE2',g2)] if not v])
            self.assertEqual([x['enabled'] for x in c['tree']['stages'] if x['id'] in ('GATE1','GATE2')],[g1,g2])
            self.assertEqual(c['protected_workflow']['independent_roles'],['verifier','reviewer'])

    def test_development_must_keep_both_gates(self):
        p=self.manager.profile('development')
        p['approval_gates']={'GATE1':False,'GATE2':False}
        with self.assertRaisesRegex(Exception,'PROTECTED_HUMAN_GATE'):self.manager.save_profile(p)
        self.assertEqual(self.manager.runtime_contract()['protected_workflow']['human_gates'],['GATE1','GATE2'])

    def test_malformed_gate_settings_denied(self):
        self.manager.create_profile('ux-mngr','UX')
        for value in ({'GATE1':'false','GATE2':True},{'GATE1':False},{'GATE1':False,'GATE2':False,'GATE3':False},None,[]):
            p=self.manager.profile('ux-mngr');p['approval_gates']=value
            with self.assertRaisesRegex(Exception,'APPROVAL_GATES_INVALID'):self.manager.save_profile(p)

    def test_system_stages_never_accept_skills(self):
        self.manager.create_profile('ux-mngr','UX')
        for sid in ('SESSION','GATE1','GATE2','COMPLETE'):
            tree=self.manager.tree('ux-mngr')
            next(st for st in tree['stages'] if st['id']==sid)['skills']=[{'name':'brainstorming','required':False,'condition':'optional'}]
            with self.assertRaisesRegex(Exception,'SYSTEM_STAGE_SKILLS_FORBIDDEN'):self.manager.save_tree(tree)

    def test_legacy_profile_gates_default_true(self):
        self.manager.create_profile('ux-mngr','UX')
        p=self.manager.profile('ux-mngr');p.pop('approval_gates')
        self.manager.save_profile(p)
        self.manager.activate('ux-mngr',1)
        self.assertEqual(self.manager.runtime_contract()['approval_gates'],{'GATE1':True,'GATE2':True})

    def test_busy_task_blocks_gate_change(self):
        self.manager.create_profile('ux-mngr','UX')
        (self.root/'docs/tasks/active/UX-001').mkdir()
        p=self.manager.profile('ux-mngr');p['approval_gates']={'GATE1':False,'GATE2':True}
        with self.assertRaisesRegex(Exception,'TASK_ACTIVE'):self.manager.save_profile(p)
        self.assertTrue(self.manager.profile('ux-mngr')['approval_gates']['GATE1'])

    def test_clone_inherits_configured_gates(self):
        self.manager.create_profile('ux-mngr','UX')
        p=self.manager.profile('ux-mngr');p['approval_gates']={'GATE1':False,'GATE2':True}
        self.manager.save_profile(p)
        q=self.manager.clone_profile('ux-mngr','ux-copy','UX copy')
        self.assertEqual(q['approval_gates'],{'GATE1':False,'GATE2':True})

class GateHTTPTests(RC3HTTPTests):
    def test_http_profile_toggle_and_contract(self):
        self.assertEqual(self.post('/api/profile/create',{'id':'ux-mngr','name':'UX Manager'})[0],200)
        p=self.manager.profile('ux-mngr');p['approval_gates']={'GATE1':False,'GATE2':False}
        self.assertEqual(self.post('/api/profile/save',p)[0],200)
        self.assertEqual(self.post('/api/profile/activate',{'profile':'ux-mngr','generation':1})[0],200)
        self.assertEqual(self.manager.runtime_contract()['protected_workflow']['human_gates'],[])

    def test_http_development_skip_rejected(self):
        p=self.manager.profile('development');p['approval_gates']={'GATE1':False,'GATE2':True}
        status,data=self.post('/api/profile/save',p)
        self.assertEqual(status,409);self.assertEqual(data['error'],'PROTECTED_HUMAN_GATE')

class GateUIContractTests(ConsoleTests):
    def test_edit_controls_and_policy_guidance_present(self):
        ui=(ROOT/'scaffold/agentflow_console/ui.html').read_text()
        for token in ('gate-toggle','setGateSetting','GATE1','GATE2','NON_SKILL_STAGES' if False else 'stageEditControls','SESSION','COMPLETE'):
            self.assertIn(token,ui)
        for token in ('SKIPPED_BY_PROFILE_POLICY','approval_gates'):
            self.assertIn(token,(ROOT/'scaffold/docs/workflow/WORKFLOW.md').read_text())

class GateStageEditorTests(ConsoleTests):
    def test_stage_flow_renders_live_gate_controls_and_keeps_skill_stage_separate(self):
        ui=(ROOT/'scaffold/agentflow_console/ui.html').read_text()
        self.assertIn("st.id==='GATE1'||st.id==='GATE2'",ui)
        self.assertIn('stage-gate-control',ui)
        self.assertIn('await setGateSetting(profile.id,st.id,intended)',ui)
        self.assertIn('cb.disabled=protectedGate||busy',ui)
        self.assertIn('시스템 단계 · 스킬 사용 없음',ui)
        self.assertIn("if(['SESSION','GATE1','GATE2','COMPLETE'].includes(st.id)||!stageInScope(profile,st.id))continue",ui)
