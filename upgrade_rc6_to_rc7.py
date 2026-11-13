#!/usr/bin/env python3
"""RC6 -> RC7 project-local update. Dry run by default. Won't overwrite modified RC6 files."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, shutil, argparse

BASE=Path(__file__).resolve().parent
SOURCES=['AGENTS.md', 'docs/workflow/WORKFLOW.md', '.opencode/agents/coordinator.md', '.claude/agents/coordinator.md', '.ai-dev/README.md', '.agentflow/README.md', 'agentflow_console/ai.py', 'agentflow_console/server.py', 'agentflow_console/ui.html', 'agentflow_console.py', '.opencode/commands/agentflow-mngr.md']
PREVIOUS={'AGENTS.md': 'd13bbb749bf0ffc9d1ad89f349f2c05a647b1c7d24cdc903f51c8461546d4548', 'docs/workflow/WORKFLOW.md': '5d98398d39ae5aceba0666677033304fd842feb06a94a8ec1478903ada9f546d', '.opencode/agents/coordinator.md': '70d0fd4d9fd7eaf8ed4402adcc6429c39c4865ee722073da2cb4c3d26a5d55ec', '.claude/agents/coordinator.md': 'b307e7319a37de5a8f853dae326a0a6d09c13df470b9d4819896b14559c7cc20', '.ai-dev/README.md': 'e6ed1aa6fe4b6d969e1fbdb3e2f2d9d8ff733976a54f2e0ccad87784bf49eb18', '.agentflow/README.md': '8b17ae62b7dc37fcaf77c30ec264023e6aeff6445d89bb72e9d2b28b358a4366', 'agentflow_console/ai.py': '1af3199099375f5513a4693274255c4e72f6ec0679413a4124817feb945471de', 'agentflow_console/server.py': '9b1ade2b783f955dfba421a97a8417951a78d8330984f524610d677f2780371b', 'agentflow_console/ui.html': 'de9177cd9a2b9f5372ce80c184d6b51807f746addcb0982b05211a11afa84fb5', 'agentflow_console.py': 'd549c933fe3d0017aab39064556e83fbbaaa8b265ea7674d6aead10deaa34975'}
NEW={'AGENTS.md': '34658a896a161d13fa3496a272ec4e7166ef3ae12d6a0108e200c2bc77600df8', 'docs/workflow/WORKFLOW.md': 'f21acaebebabb70c6dda87886595b314d54809d6cbbda8d166e6d80d40d1c8d4', '.opencode/agents/coordinator.md': 'ef2ef38b9cce36d79dfe6af064e8a6e75435d614e83e65ed484e0457e6e837c4', '.claude/agents/coordinator.md': 'a362710038ec6b14c79487da43a13a1d88dd262479ed95442accf203cef7d46e', '.ai-dev/README.md': '9b07338cce3d6efa3c8d77e8969881131a21013931f7742560d68e18214ddcb3', '.agentflow/README.md': 'f3d281e0542415412b75a9c620d47faccc9495df3e39b8e750082f82cb45c401', 'agentflow_console/ai.py': '7acdf7add8caa501662758372f142297c66e39e94ac596ed38b1d814aacfd683', 'agentflow_console/server.py': '156df6910df7093b58a7e5646f4b319c0bc70f6a6a994f02d7dbdd0f7e8e1f57', 'agentflow_console/ui.html': 'd8d2347b963568736703aed7a17e14dfa0e18dc6af84a570eb2787cfbd6a5095', 'agentflow_console.py': '639931bc95fd6ec2662181cfe6780c1ef09c60d7716b1ca88a83467dbb510b65', '.opencode/commands/agentflow-mngr.md': 'd16cc4d11687f81b94808279e5af31377dbfa10189a70ae40f02c4ea21e9aa45'}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description='Upgrade RC6 AgentFlow console to RC7')
    parser.add_argument('project')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    project=Path(args.project).expanduser().resolve()
    if not (project/'agentflow_console.py').is_file() or not (project/'AGENTS.md').is_file():
        raise SystemExit('BLOCKED: AgentFlow installed project not found')
    if (project/'agentflow_console/lifecycle.py').is_file():
        import importlib.util
        spec=importlib.util.spec_from_file_location('agentflow_rc7_lifecycle',project/'agentflow_console/lifecycle.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        if mod.info(project)['running']:
            raise SystemExit('BLOCKED: Stop managed web console before upgrade')
    for rel in SOURCES:
        target=project/rel
        if any(p.is_symlink() for p in [target,*list(target.parents)[:len(target.parents)-len(project.parents)] ]):
            raise SystemExit('BLOCKED: Symlink in target path '+rel)
        if target.is_file():
            expected=PREVIOUS.get(rel)
            current=digest(target)
            if current not in (expected,NEW[rel]):
                raise SystemExit('BLOCKED: Existing file changed; manual merge required: '+rel)
        elif target.exists():
            raise SystemExit('BLOCKED: Not a regular file: '+rel)
    print('Project:',project)
    print('Files to check:',len(SOURCES))
    if not args.apply:
        print('DRY_RUN: No files changed. Stop any foreground console before --apply.')
        return
    backup=project/'.agentflow/backups'/('rc7-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True,exist_ok=False)
    changed=0
    for rel in SOURCES:
        dest=project/rel
        if dest.is_file() and digest(dest)==NEW[rel]:
            continue
        if dest.exists():
            b=backup/rel;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,b)
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(BASE/'scaffold'/rel,dest)
        changed+=1
    print('APPLIED. Changed:',changed,'Backup:',backup)
    print('Profile, Skill Tree, Gate, TASK and skill registry are unchanged.')

if __name__=='__main__': main()
