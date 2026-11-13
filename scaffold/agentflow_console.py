#!/usr/bin/env python3
"""Project-local console and experimental managed-subprocess rotation CLI; not native LLM orchestration."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from agentflow_console.core import Manager, ManagementError
from agentflow_console.server import serve


def main(argv=None):
    ap = argparse.ArgumentParser(description='Project-local AgentFlow console; no workflow execution')
    ap.add_argument('--project', default=str(Path(__file__).resolve().parent))
    sub = ap.add_subparsers(dest='action', required=True)
    cmd = sub.add_parser('open', help='Serve loopback web console')
    cmd.add_argument('--port', type=int, default=0)
    cmd.add_argument('--browser', action='store_true')
    start = sub.add_parser('start', help='Start managed console in background; reuse existing instance')
    start.add_argument('--browser', action='store_true', help='Open browser after starting')
    sub.add_parser('console-status', help='Show managed console PID, port, and health')
    sub.add_parser('console-open', help='Open the running managed console in a browser')
    sub.add_parser('stop', help='Stop managed console for this project only')
    sub.add_parser('doctor', help='Check managed server and local AI host presence')
    sub.add_parser('_serve-managed', help=argparse.SUPPRESS)
    sub.add_parser('status')
    contract = sub.add_parser('contract')
    import os
    contract.add_argument('--session', default=os.environ.get('AGENTFLOW_SESSION'))
    contract.add_argument('--profile', default=None)
    task_context = sub.add_parser('task-context', help='Pin or inspect immutable TASK contract')
    task_context.add_argument('task_id')
    task_context.add_argument('--pin', action='store_true')
    task_context.add_argument('--session', default=os.environ.get('AGENTFLOW_SESSION'))
    task_context.add_argument('--profile', default=None)
    session = sub.add_parser('session-profile', help='Bind a session-scoped default for new TASKs')
    session.add_argument('session_id')
    session.add_argument('--host', choices=['opencode','claude','codex'])
    session.add_argument('--profile')
    session.add_argument('--generation', type=int)

    event = sub.add_parser('agent-event', help='Native adapter prompt event; JSON on stdin')
    event.add_argument('--host', choices=['opencode','claude','codex'], required=True)
    event.add_argument('--session-id', required=True)
    event.add_argument('--prompt', default=None)
    event.add_argument('--stdin-json', action='store_true')
    ready = sub.add_parser('task-ready', help='Finalize verified plan without archiving or completing implementation')
    ready.add_argument('task_id')
    begin = sub.add_parser('task-begin', help='Claim PLAN_READY task for Development, stopping at Gate1')
    begin.add_argument('task_id')
    begin.add_argument('--session', default=None)
    rotation = sub.add_parser('rotation', help='Managed subprocess rotation (native agent adapter NOT_VERIFIED)')
    rotation_sub = rotation.add_subparsers(dest='rotation_action', required=True)
    rotation_sub.add_parser('doctor')
    for action in ('status','history','validate','stop','cancel'):
        rotation_sub.add_parser(action).add_argument('task_id')
    first=rotation_sub.add_parser('start')
    first.add_argument('task_id');first.add_argument('stage');first.add_argument('command',nargs=argparse.REMAINDER)
    request=rotation_sub.add_parser('request')
    request.add_argument('task_id');request.add_argument('--reason',choices=['manual','context-pressure','stage-boundary','retry-limit'],default='manual')
    request.add_argument('--completed',action='append',default=[]);request.add_argument('--remaining',action='append',default=[])
    res=rotation_sub.add_parser('resume')
    res.add_argument('task_id');res.add_argument('command',nargs=argparse.REMAINDER)
    sub.add_parser('profiles')
    sub.add_parser('templates')
    template = sub.add_parser('add-template')
    template.add_argument('template')
    sub.add_parser('trees')
    sub.add_parser('skills')
    activate = sub.add_parser('activate')
    activate.add_argument('profile')
    activate.add_argument('--generation', type=int, required=True)
    create = sub.add_parser('create', help='Create a custom profile retaining protected workflow')
    create.add_argument('id')
    create.add_argument('label')
    clone = sub.add_parser('clone')
    clone.add_argument('source')
    clone.add_argument('id')
    clone.add_argument('label')
    inspect = sub.add_parser('inspect')
    inspect.add_argument('kind', choices=['local','zip'])
    inspect.add_argument('source')
    suggest = sub.add_parser('suggest')
    suggest.add_argument('host', choices=['opencode','claude','codex'])
    suggest.add_argument('question')
    suggest.add_argument('--profile', default=None)
    suggest.add_argument('--stage', default=None)
    remove = sub.add_parser('remove')
    remove.add_argument('name')
    remove.add_argument('--approve', action='store_true')
    gitinspect = sub.add_parser('git-inspect')
    gitinspect.add_argument('url')
    gitinspect.add_argument('commit')
    gitinspect.add_argument('subdir')
    gitinstall = sub.add_parser('git-install')
    gitinstall.add_argument('url')
    gitinstall.add_argument('commit')
    gitinstall.add_argument('subdir')
    gitinstall.add_argument('--approve', action='store_true')
    install = sub.add_parser('install')
    install.add_argument('kind', choices=['local','zip'])
    install.add_argument('source')
    install.add_argument('--approve', action='store_true', help='Explicit approval of reviewed files')
    ns = ap.parse_args(argv)
    try:
        if ns.action == 'open':
            serve(ns.project, ns.port, ns.browser)
            return 0
        if ns.action in ('start', 'console-status', 'console-open', 'stop', 'doctor', '_serve-managed'):
            from agentflow_console import lifecycle
            if ns.action == '_serve-managed':
                lifecycle.managed_serve(ns.project)
                return 0
            funcs = {'start': lifecycle.start, 'console-status': lifecycle.info,
                     'console-open': lifecycle.open_existing, 'stop': lifecycle.stop,
                     'doctor': lifecycle.doctor}
            result = funcs[ns.action](ns.project, browser=ns.browser) if ns.action == 'start' else funcs[ns.action](ns.project)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        m = Manager(ns.project)
        actions = {'status':m.status,'profiles':m.list_profiles,'templates':m.list_templates,'trees':m.list_trees,'skills':m.list_skills}
        if ns.action in actions:
            result = actions[ns.action]()
        elif ns.action == 'contract':
            from agentflow_console.contexts import ContextRegistry
            result = ContextRegistry(m).contract(ns.session, ns.profile)
        elif ns.action == 'session-profile':
            from agentflow_console.contexts import ContextRegistry
            registry = ContextRegistry(m)
            if ns.host is not None and ns.profile is not None:
                result = registry.bind_session(ns.session_id, ns.host, ns.profile, ns.generation)
            elif ns.host is None and ns.profile is None:
                result = registry.get_session(ns.session_id)
            else:
                raise ManagementError('SESSION_HOST_AND_PROFILE_REQUIRED')
        elif ns.action == 'task-context':
            from agentflow_console.contexts import ContextRegistry
            registry = ContextRegistry(m)
            result = registry.pin_task(ns.task_id, ns.session, ns.profile) if ns.pin else registry.task_contract(ns.task_id)
        elif ns.action == 'agent-event':
            from agentflow_console.sessionbridge import prompt_event
            incoming = json.load(sys.stdin) if ns.stdin_json else {}
            result = prompt_event(m, ns.host, ns.session_id, incoming.get('prompt') if ns.stdin_json else ns.prompt)
        elif ns.action == 'task-ready':
            result = m.mark_plan_ready(ns.task_id)
        elif ns.action == 'task-begin':
            result = m.begin_planned_task(ns.task_id, ns.session)
        elif ns.action == 'rotation':
            from agentflow_console.rotation import RotationManager
            rm=RotationManager(m)
            a=ns.rotation_action
            if a == 'doctor': result=rm.capabilities()
            elif a == 'status': result=rm.status(ns.task_id)
            elif a == 'history': result=rm.history(ns.task_id)
            elif a == 'request': result=rm.request(ns.task_id,ns.reason,ns.completed,ns.remaining)
            elif a == 'validate': result=rm.validate(ns.task_id)
            elif a == 'stop': result=rm.stop(ns.task_id)
            elif a == 'cancel': result=rm.cancel(ns.task_id)
            elif a == 'start': result=rm.start_managed(ns.task_id,ns.stage,[x for x in ns.command if x!='--'])
            elif a == 'resume': result=rm.resume(ns.task_id,[x for x in ns.command if x!='--'])
        elif ns.action == 'activate':
            result = m.activate(ns.profile, ns.generation)
        elif ns.action == 'add-template':
            result = m.add_template(ns.template)
        elif ns.action == 'create':
            result = m.create_profile(ns.id, ns.label)
        elif ns.action == 'clone':
            result = m.clone_profile(ns.source, ns.id, ns.label)
        elif ns.action == 'inspect':
            result = m.inspect_local(ns.source, ns.kind)
        elif ns.action == 'suggest':
            from agentflow_console.ai import suggest
            result = suggest(m, ns.host, ns.question, ns.profile, ns.stage)
        elif ns.action == 'remove':
            result = m.remove_skill(ns.name, ns.approve)
        elif ns.action == 'git-inspect':
            result = m.inspect_git(ns.url, ns.commit, ns.subdir)
        elif ns.action == 'git-install':
            result = m.install_git(ns.url, ns.commit, ns.subdir, ns.approve)
        else:
            result = m.install_skill(ns.kind, ns.source, ns.approve)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ManagementError, OSError, ValueError) as exc:
        print('MANAGEMENT_BLOCKED: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
