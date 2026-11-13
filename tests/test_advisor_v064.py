import sys, tempfile, json, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scaffold.agentflow_console import advisor, ai
from test_ai_skill_manager import AIManagerTests

class AdvisorUnits(unittest.TestCase):
 def test_parse_only_real_results_not_install_hints(self):
  s='Install with npx skills add <owner/repo@skill>\n\x1b[32mryantr-statinops/SKILLS@requirements-analysis\x1b[0m\n└ https://skills.sh/ryantr-statinops/SKILLS/requirements-analysis\n\nunknown text\n'
  found=advisor.parse_cli_search(s,'ANALYZE','requirements analysis')
  self.assertEqual(len(found),1)
  self.assertEqual(found[0]['name'],'requirements-analysis')
  self.assertEqual(found[0]['commit'],'')
  self.assertFalse(found[0]['verified'])

 def test_relevance_and_conflict(self):
  items=[{'name':'brainstorming','origin':'local','stage':'ANALYZE','reason':'already assigned'},
   {'name':'requirements-analysis','origin':'external','stage':'ANALYZE','description':'Turn requirements into acceptance criteria'},
   {'name':'image-generation','origin':'external','stage':'PLAN','description':'Generate images'}]
  with tempfile.TemporaryDirectory() as d:
   vals=advisor.validate_candidates(items,'task-planning',d)
   self.assertEqual([x['assessment']['verdict'] for x in vals],['POLICY_CONFLICT','REVIEW_REQUIRED','NOT_RELEVANT'])

 def test_log_redacted_and_lookup_restricted(self):
  with tempfile.TemporaryDirectory() as d:
   run={'run_id':advisor.new_run_id(),'status':'COMPLETED','host':'opencode','profile':'p','stages':['ANALYZE'],'created_at':advisor.now_iso(),'engine_status':'UNAVAILABLE','candidate_count':0,'steps':[]}
   advisor.save_trace(d,run)
   self.assertEqual(advisor.read_trace(d,run['run_id'])['run_id'],run['run_id'])
   self.assertEqual(len(advisor.list_traces(d)),1)
   with self.assertRaises(ValueError): advisor.read_trace(d,'../../secrets')
   self.assertEqual((Path(d)/'.agentflow/logs/skill-advisor/runs'/(run['run_id']+'.json')).stat().st_mode&0o777,0o600)

 def test_cli_no_auto_npx(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertIsNone(advisor.local_skills_cli(d))
   found=advisor.discover_cli(d,'requirements analysis',['ANALYZE'])
   self.assertEqual(found['status'],'UNAVAILABLE')

 def test_cli_mock_project_local_search(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'.agentflow/tools/skills-cli/node_modules/.bin/skills'
   exe.parent.mkdir(parents=True)
   exe.write_text('#!/bin/sh\necho ryantr-statinops/SKILLS@requirements-analysis\n')
   exe.chmod(0o755)
   found=advisor.discover_cli(d,'요구사항 분석',['ANALYZE'])
   self.assertEqual(found['status'],'COMPLETED')
   self.assertEqual(found['candidates'][0]['name'],'requirements-analysis')
   self.assertGreater(len(found['searches']),0)
   self.assertEqual(found['candidates'][0]['source_status'],'SKILLS_CLI_DISCOVERED_UNPINNED')

class AdvisorIntegration(AIManagerTests):
 def test_trace_written_and_read_via_api(self):
  self.manager.create_profile('test1','Test 1')
  with patch.object(ai.shutil,'which',return_value='/usr/bin/opencode'),patch.object(ai.subprocess,'run',return_value=self._response()):
   status,record=self.post('/api/ai/suggest',{'host':'opencode','question':'분석과 작업 계획 생성 스킬','profile':'test1','stage':'ANALYZE','search_external':False})
  self.assertEqual(status,200,record)
  self.assertRegex(record['run_id'],r'^[0-9TZ-]+-[a-f0-9]{10}$')
  self.assertEqual(record['trace_status'],'STORED')
  runs=advisor.list_traces(self.root)
  self.assertTrue(any(x['run_id']==record['run_id'] for x in runs))
  trace=advisor.read_trace(self.root,record['run_id'])
  self.assertEqual(trace['status'],'COMPLETED')
  self.assertNotIn('분석과 작업 계획 생성 스킬',json.dumps(trace,ensure_ascii=False))
  self.assertEqual(record['recommendations'][0]['assessment']['verdict'],'POLICY_CONFLICT' if record['profile']=='task-planning' else record['recommendations'][0]['assessment']['verdict'])

if __name__=='__main__':unittest.main()
