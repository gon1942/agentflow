"""Synthetic archives only; not claims of access to live upstream GitHub ZIPs."""
import copy, hashlib, io, json, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
import architect_sources as arch
import upgrade_project_architect as upgrade
from test_install import make_fixture, installer
from scaffold.agentflow_console.core import Manager
ROOT=Path(__file__).resolve().parents[1]

def synthetic_archives():
 repos=copy.deepcopy(arch.REPOS)
 skills=copy.deepcopy(arch.SKILLS)
 original={name:f'---\nname: {name}\ndescription: synthetic test fixture\n---\n'.encode() for name in skills}
 for name,(key,path,_) in skills.items():skills[name]=(key,path,arch.git_blob_sha1(original[name]))
 source={}
 for key,info in repos.items():
  license_content=b'MIT fixture license\n' if info['license'] else None
  if license_content:info['license_sha']=arch.git_blob_sha1(license_content)
  buff=io.BytesIO()
  with zipfile.ZipFile(buff,'w') as z:
   for name,(s_key,path,_) in skills.items():
    if s_key!=key:continue
    z.writestr('repo-'+info['commit']+'/'+path+'/SKILL.md',original[name])
    z.writestr('repo-'+info['commit']+'/'+path+'/references/guide.md',b'companion for '+name.encode())
   if license_content:z.writestr('repo-'+info['commit']+'/'+info['license'],license_content)
  source[key]=buff.getvalue()
 return repos,skills,source

class ArchitectSources(unittest.TestCase):
 def load(self):
  repos,skills,archives=synthetic_archives()
  with patch.object(arch,'REPOS',repos),patch.object(arch,'SKILLS',skills):
   p=arch.load_package(blobs=archives)
  return p
 def test_all_eight_full_directories_and_licenses(self):
  package=self.load()
  self.assertEqual(len([k for k in package['files'] if k.endswith('/SKILL.md')]),8)
  self.assertEqual(len([k for k in package['files'] if k.endswith('/guide.md')]),8)
  self.assertEqual(len(package['licenses']),2)
  self.assertEqual(package['sources']['skills']['license_status'],'NO_EXPLICIT_REPOSITORY_LICENSE_CHECKED')
 def test_source_commit_hashes_are_pinned(self):
  self.assertEqual(len(arch.SKILLS),8)
  for key,obj in arch.REPOS.items():self.assertEqual(len(obj['commit']),40)
 def test_wrong_source_hash_rejected_before_files(self):
  repos,skills,archives=synthetic_archives()
  # Original pinned hash vs synthetic content MUST be rejected.
  with patch.object(arch,'REPOS',repos):
   with self.assertRaisesRegex(ValueError,'EXTERNAL_SKILL_HASH_MISMATCH'):
    arch.load_package(blobs=archives)
 def test_missing_license_rejected(self):
  repos,skills,archives=synthetic_archives()
  repos['MUSUBI']['license_sha']='f'*40
  with patch.object(arch,'REPOS',repos),patch.object(arch,'SKILLS',skills):
   with self.assertRaisesRegex(ValueError,'EXTERNAL_LICENSE_MISMATCH'):
    arch.load_package(blobs=archives)
 def test_zip_traversal_and_symlink_rejected(self):
  repos,skills,archives=synthetic_archives()
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:
   z.writestr('repo/../../../../etc/passwd',b'not safe')
  archives['skills']=buf.getvalue()
  with patch.object(arch,'REPOS',repos),patch.object(arch,'SKILLS',skills):
   with self.assertRaisesRegex(ValueError,'UNSAFE_ARCHIVE_PATH'):
    arch.load_package(blobs=archives)
 def test_native_3_roots_and_contract_via_fresh_install_fixture(self):
  package=self.load()
  upstream, hashes, helper_hashes, files=make_fixture()
  with tempfile.TemporaryDirectory() as tmp, patch.object(installer,'EXPECTED_SKILLS',hashes),patch.object(installer,'EXPECTED_HELPERS',helper_hashes):
   root=Path(tmp)/'fresh'
   output=installer.install(root,ROOT,upstream,architect_package=package)
   self.assertEqual(output['architect_skills'],8)
   manager=Manager(root)
   tree=manager.tree('project-architect')
   self.assertEqual(manager.missing_skills(tree,manager.profile('project-architect')),[])
   for name in arch.SKILLS:
    self.assertTrue(manager.verify_skill(name)['verified'])
    for runtime in arch.ROOTS:
     self.assertTrue((root/runtime/name/'SKILL.md').exists())
     self.assertTrue((root/runtime/name/'references/guide.md').exists())
   self.assertEqual([s['name'] for st in tree['stages'] for s in st['skills'] if s['name'] in arch.SKILLS],list(arch.SKILLS))
   self.assertFalse((root/'.opencode/skills/af-project-discovery').exists())
 def test_upgrade_preserves_custom_and_stage_selection(self):
  pkg=self.load()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for f in ['docs/workflow/WORKFLOW.md']:(root/f).parent.mkdir(parents=True,exist_ok=True);(root/f).write_text('fixture')
   tree={'id':'project-architect','stages':[{'id':sid,'enabled':False,'agent':'coordinator','skills':[{'name':'af-project-discovery','required':True,'condition':'always'},{'name':'custom-user-skill','required':False,'condition':'optional'}]} for sid in arch.STAGE_MAP]}
   for rel,obj in [(upgrade.TREE,tree),(upgrade.LOCK,{'managed_skills':{}})]:
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj))
   first=upgrade.migrate(root,apply=False)
   self.assertEqual(first['status'],'PREVIEW')
   self.assertEqual(json.loads((root/upgrade.TREE).read_text()),tree)
   result=upgrade.migrate(root,apply=True,package=pkg)
   self.assertEqual(result['status'],'INSTALLED')
   saved=json.loads((root/upgrade.TREE).read_text())
   for stage in saved['stages']:
    self.assertFalse(stage['enabled'])
    self.assertIn('custom-user-skill',[s['name'] for s in stage['skills']])
    self.assertNotIn('af-project-discovery',[s['name'] for s in stage['skills']])
   self.assertTrue(Path(result['backup']).is_dir())
 def test_upgrade_safe_legacy_cleanup_and_lock_prune(self):
  pkg=self.load()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for rel,data in [('docs/workflow/WORKFLOW.md','contract'),(upgrade.TREE,json.dumps({'id':'project-architect','stages':[]}))]:
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
   name='af-project-discovery';old=b'legitimate old skill\n';digest=hashlib.sha256(old).hexdigest()
   lock={'managed_skills':{name:{'source':'agentflow-local-bundled-v0.7.7','files_sha256':{'SKILL.md':digest}}}}
   p=root/upgrade.LOCK;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(lock))
   for rt in arch.ROOTS:
    oldpath=root/rt/name/'SKILL.md';oldpath.parent.mkdir(parents=True,exist_ok=True);oldpath.write_bytes(old)
   result=upgrade.migrate(root,apply=True,package=pkg)
   self.assertEqual(result['removed_unused_legacy_files'],3)
   self.assertFalse(any((root/rt/name/'SKILL.md').exists() for rt in arch.ROOTS))
   self.assertNotIn(name,json.loads((root/upgrade.LOCK).read_text())['managed_skills'])
   self.assertTrue((Path(result['backup'])/'removed'/arch.ROOTS[0]/name/'SKILL.md').exists())
 def test_upgrade_existing_conflict_no_mutation(self):
  pkg=self.load()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for rel,data in [('docs/workflow/WORKFLOW.md','x'),(upgrade.TREE,json.dumps({'id':'project-architect','stages':[]})),(upgrade.LOCK,'{}'),('.opencode/skills/system-architect/SKILL.md','custom conflict')]:
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
   before=(root/upgrade.TREE).read_bytes()
   with self.assertRaisesRegex(ValueError,'EXISTING_FILE_CONFLICT'):
    upgrade.migrate(root,apply=True,package=pkg)
   self.assertEqual((root/upgrade.TREE).read_bytes(),before)
 def test_active_task_upgrade_blocked(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for rel in ('docs/workflow/WORKFLOW.md',upgrade.TREE,upgrade.LOCK):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
   (root/'docs/tasks/active/T-1').mkdir(parents=True)
   with self.assertRaisesRegex(ValueError,'TASK_ACTIVE'):upgrade.migrate(root,apply=False)
if __name__=='__main__':unittest.main()
