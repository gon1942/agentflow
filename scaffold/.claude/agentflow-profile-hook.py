#!/usr/bin/env python3
"""Claude UserPromptSubmit hook; prints only selected contract (never user prompt)."""
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from agentflow_console.core import Manager
from agentflow_console.sessionbridge import prompt_event

try:
    payload=json.load(sys.stdin)
    if pathlib.Path(payload.get('cwd') or ROOT).resolve() != ROOT.resolve():
        sys.exit(0)  # Nested unrelated worktrees must not inherit the wrong project's profile.
    result=prompt_event(Manager(ROOT),'claude',payload.get('session_id'),payload.get('prompt'))
    if result.get('status')=='PROFILE_UNKNOWN':
        print(result['instruction'])
    else:
        print('AgentFlow Session Profile: '+result['profile']+'; session='+result['session_id']+'; contract='+result['configuration_sha256'])
        print(result['instruction'])
except Exception as exc:
    # Error is visible to the agent, not silently represented as success.
    print('AgentFlow Profile hook BLOCKED: '+str(exc),file=sys.stderr)
    sys.exit(2)
