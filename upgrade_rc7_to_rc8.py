#!/usr/bin/env python3
"""Upgrade an unmodified RC7 installation to RC8 AI Skill Manager (dry run default)."""
import argparse
from pathlib import Path
from datetime import datetime,timezone
import hashlib,shutil
BASE=Path(__file__).resolve().parent
FILES=['agentflow_console/ai.py', 'agentflow_console/server.py', 'agentflow_console/core.py', 'agentflow_console/ui.html', 'agentflow_console/external.py']
PREVIOUS={'agentflow_console/ai.py': '7acdf7add8caa501662758372f142297c66e39e94ac596ed38b1d814aacfd683', 'agentflow_console/server.py': '156df6910df7093b58a7e5646f4b319c0bc70f6a6a994f02d7dbdd0f7e8e1f57', 'agentflow_console/core.py': 'b20301f982cdafddd52eca8caed9d0c93e0f27ea3083d0369304e141832c773f', 'agentflow_console/ui.html': 'd8d2347b963568736703aed7a17e14dfa0e18dc6af84a570eb2787cfbd6a5095'}
CURRENT={'agentflow_console/ai.py': '2cbe7ec598e2824dadead83486a129efb0e4eb25e59c46fe539e8725a8313657', 'agentflow_console/server.py': '85e7224e4fb72d4e35ac4f86a1532befea42c081aaee1131237873418c72b6f0', 'agentflow_console/core.py': '74ea6833d67c95f35015b5c87cd7b57b6643ca3b7ab3171eb67dda400dae8e47', 'agentflow_console/ui.html': 'f5097e36bce62614bf4d836a62b7e619d871fb4b3368d7b252fccfbad1994f66', 'agentflow_console/external.py': 'ee94250ecc51e792aa11e6158b10430cbf0352ed4d70f8d418f2ae68fc7a3307'}

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('project')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    project=Path(args.project).expanduser().resolve()
    if not (project/'agentflow_console.py').is_file() or not (project/'.agentflow/active-profile.json').is_file():
        raise SystemExit('BLOCKED: AgentFlow project not found')
    # The existing console daemon must be stopped before replacing its modules.
    path=project/'agentflow_console/lifecycle.py'
    if path.is_file():
        import importlib.util
        spec=importlib.util.spec_from_file_location('lifecycle_upgrade_check',path)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        if mod.info(project)['running']:
            raise SystemExit('BLOCKED: stop console before upgrading')
    for rel in FILES:
        target=project/rel
        cur=project
        for part in Path(rel).parts:
            cur=cur/part
            if cur.is_symlink():raise SystemExit('BLOCKED: symlink at '+rel)
        if target.is_file():
            if digest(target) not in (PREVIOUS.get(rel),CURRENT[rel]):
                raise SystemExit('BLOCKED: existing file modified; manual merge required: '+rel)
        elif target.exists():
            raise SystemExit('BLOCKED: not a regular file: '+rel)
    print('Project:',project,'Files:',len(FILES))
    if not args.apply:
        print('DRY_RUN: no changes, pass --apply after stopping console')
        return
    backup=project/'.agentflow/backups'/('rc8-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True,exist_ok=False)
    count=0
    for rel in FILES:
        source=BASE/'scaffold'/rel
        dest=project/rel
        if dest.is_file() and digest(dest)==CURRENT[rel]:continue
        if dest.is_file():
            back=backup/rel;back.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,back)
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        count+=1
    print('APPLIED:',count,'Backup:',backup)
    print('Existing Profiles, Trees, Skills, Gate policies and TASK data untouched.')

if __name__=='__main__':main()
