#!/usr/bin/env python3
"""One-time installer only. No runtime CLI, teamdev, global writes or workflow engine.

The installer fetches a pinned upstream Superpowers archive, validates the 7
required original SKILL.md files, copies their COMPLETE skill directories to
all three agents' project-local skill roots, and installs workflow instructions.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import urllib.request
import zipfile
import importlib.util
import architect_sources as architect
# Load the installer-only provisioning module from this release directory (not from PYTHONPATH/global).
_TOOL_MODULE = Path(__file__).resolve().with_name('tool_provision.py')
_TOOL_SPEC = importlib.util.spec_from_file_location('agentflow_tool_provision_local', _TOOL_MODULE)
tool_provision = importlib.util.module_from_spec(_TOOL_SPEC)
_TOOL_SPEC.loader.exec_module(tool_provision)

COMMIT = '22f0b463e7a5e579904dd6211a520321035526f7'
SOURCE = 'obra/superpowers'
ORIGINAL_LICENSE_REL = '.ai-dev/licenses/obra-superpowers-LICENSE'
ORIGINAL_LICENSE_BLOB_SHA1 = 'abf0390320aa14406af7a520b9b0739fdda9bf08'
ARCHIVE_URL = f'https://codeload.github.com/obra/superpowers/zip/{COMMIT}'
# GitHub Git-blob IDs verified against the pinned upstream repository.
EXPECTED_SKILLS = {
    'brainstorming': '9eb0edc7fedf26e1d3e2f3f223e5bcc5058aed6a',
    'writing-plans': '4cf0275d88d67aa4ef09f4bbca9970ed6ff74a00',
    'test-driven-development': '46838cc9e893c06259e3bdad0fc2425b36242f15',
    'verification-before-completion': '7d45333cc4a49c57a80df6c1fe2fa777a207afbc',
    'requesting-code-review': '68d338a58ecdd8b77bfbb519b781ef223dbbb842',
    'receiving-code-review': '950da7b74bf6dbed6b8726d12ddadd65a9f5fda7',
    'systematic-debugging': '62fc752aaef59a8bbed5d305f4cadc60f8ae07ed',
}
# All companion files from the same fixed commit; absent or modified helpers BLOCK install.
EXPECTED_HELPERS = {
    'brainstorming/builder-check-prompt.md': '136e9c1d516ee1852abc5e556e76ce1b085d3827',
    'brainstorming/visual-companion.md': '8dca065bd9adb9d4fa82a66acbb4176ea23259c6',
    'brainstorming/scripts/frame-template.html': 'f540bb8a4f88107e2b37b2871a4c1a55a3b6f720',
    'brainstorming/scripts/helper.js': 'e11d26489ce248f37af3e4dd01ddec6a4e88287f',
    'brainstorming/scripts/server.cjs': 'fdc796122583f5d6687d9582eb265c2fa0cb7781',
    'brainstorming/scripts/start-server.sh': 'f6d538a47b14aed925a856e34411ba8258ec54c9',
    'brainstorming/scripts/stop-server.sh': '7cacfe9440043f7a46eac555cd835fad0769c425',
    'test-driven-development/writing-good-tests.md': 'd3c4482fd30b4f9084bb61545fe73939a7502c28',
    'requesting-code-review/code-reviewer.md': '6d358b5d7d450c83cacbe450b7dbd4e673b694ad',
    'systematic-debugging/condition-based-waiting-example.ts': '703a06b653160d060bbf46ab5c6e0cd7446bd592',
    'systematic-debugging/condition-based-waiting.md': '70994f777c586f7d4c43033aac34c7cf0da6688b',
    'systematic-debugging/defense-in-depth.md': 'e2483354dc2b62478a2624e34ca18bc0efe887b2',
    'systematic-debugging/find-polluter.sh': '985f5d08ccf8a3f2d40739cfcaf4413bb24bf1cb',
    'systematic-debugging/root-cause-tracing.md': '0e72e8f9566b7ef85e814633d1feacad9d0c5868',
}
SKILL_ROOTS = ('.opencode/skills', '.claude/skills', '.agents/skills')
MAX_ZIP_BYTES = 50_000_000
MAX_SKILL_TOTAL_BYTES = 12_000_000
MAX_FILE_BYTES = 2_000_000


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest()


def _safe_archive_relative(path: str) -> tuple[str, ...] | None:
    # Reject weird zip paths; validate each element before even deciding inclusion.
    if '\\' in path or '\x00' in path or path.startswith('/'):
        raise ValueError(f'Unsafe archive entry: {path!r}')
    parts = PurePosixPath(path).parts
    if '..' in parts or '.' in parts:
        raise ValueError(f'Unsafe archive entry: {path!r}')
    if len(parts) < 4 or parts[1] != 'skills':
        return None
    if parts[2] not in EXPECTED_SKILLS:
        return None
    if not path.startswith('superpowers-'):
        raise ValueError('Unexpected upstream archive root')
    return tuple(parts[2:])


def extract_skills(blob: bytes) -> dict[str, bytes]:
    """Validate and materialize only required skill subtrees, with no writes."""
    if len(blob) > MAX_ZIP_BYTES:
        raise ValueError('Upstream archive too large')
    result: dict[str, bytes] = {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for item in z.infolist():
            relative = _safe_archive_relative(item.filename)
            if relative is None or item.is_dir():
                continue
            mode = item.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise ValueError(f'Symlink prohibited in upstream skill: {item.filename}')
            if item.file_size > MAX_FILE_BYTES:
                raise ValueError(f'Skill file too large: {item.filename}')
            total += item.file_size
            if total > MAX_SKILL_TOTAL_BYTES:
                raise ValueError('Upstream skill data too large')
            key = '/'.join(relative)
            if key in result:
                raise ValueError(f'Duplicate archive entry: {key}')
            result[key] = z.read(item)
    all_expected = {**{f'{name}/SKILL.md': sha for name,sha in EXPECTED_SKILLS.items()}, **EXPECTED_HELPERS}
    for key,want in all_expected.items():
        if key not in result:
            raise ValueError(f'Missing upstream original or companion: {key}')
        actual = git_blob_sha1(result[key])
        if actual != want:
            raise ValueError(f'UPSTREAM_HASH_MISMATCH {key}: {actual} != {want}')
    unexpected = set(result) - set(all_expected)
    if unexpected:
        raise ValueError(f'Unexpected upstream skill file(s): {sorted(unexpected)[:5]}')
    return result


def _scaffold_files(base: Path) -> dict[str, bytes]:
    out = {}
    for path in (base / 'scaffold').rglob('*'):
        if path.is_file() and not any(part in ('__pycache__','.pytest_cache') for part in path.parts) and path.suffix not in ('.pyc','.pyo'):
            rel = path.relative_to(base / 'scaffold').as_posix()
            # npm always excludes .gitignore from tarballs, even when files[] whitelists it.
            # Preserve the project-local ignore policy via a distributable template.
            if rel == '.ai-dev/gitignore-template.txt':
                rel = '.ai-dev/.gitignore'
            out[rel] = path.read_bytes()
    return out


def build_install_map(scaffold: Path, skill_files: dict[str, bytes], architect_package: dict) -> dict[str, bytes]:
    result = _scaffold_files(scaffold)
    # Retain the exact upstream MIT license notice in every installed project.
    license_bytes = result.get(ORIGINAL_LICENSE_REL)
    if license_bytes is None or git_blob_sha1(license_bytes) != ORIGINAL_LICENSE_BLOB_SHA1:
        raise ValueError('UPSTREAM_LICENSE_MISSING_OR_TAMPERED')
    manifest = {
        'provider': SOURCE,
        'license': {'path': ORIGINAL_LICENSE_REL, 'git_blob_sha1': ORIGINAL_LICENSE_BLOB_SHA1},
        'commit': COMMIT,
        'scope': 'PROJECT_ONLY',
        'verified_skill_sha1': EXPECTED_SKILLS,
        'verified_companion_sha1': EXPECTED_HELPERS,
        'installed_files_sha256': {key: hashlib.sha256(data).hexdigest() for key, data in sorted(skill_files.items())},
        'note': 'Files present/hashed, NOT proof of native agent skill loading',
    }
    manifest['managed_skills'] = architect.managed_entries(architect_package)
    manifest['project_architect_sources'] = architect_package['sources']
    result['.ai-dev/external-skills.lock.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode()
    for root in SKILL_ROOTS:
        for name, content in skill_files.items():
            result[root + '/' + name] = content
        for name, content in architect_package['files'].items():
            result[root + '/' + name] = content
    result.update(architect_package['licenses'])
    return result


def _check_destination(root: Path, rel: str, contents: bytes) -> str | None:
    # Refuse any existing symlink in the target path; do not traverse out of project.
    cursor = root
    for part in PurePosixPath(rel).parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return f'SYMLINK {cursor}'
    if cursor.exists() and (not cursor.is_file() or cursor.read_bytes() != contents):
        return f'CONFLICT {cursor}'
    return None


def install(root: Path, scaffold: Path, upstream_zip: bytes, *, architect_package: dict | None = None) -> dict:
    if architect_package is None:
        architect_package = architect.load_package()
    files = build_install_map(scaffold, extract_skills(upstream_zip), architect_package)
    root = root.expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    conflicts = [_check_destination(root, rel, data) for rel, data in files.items()]
    conflicts = [x for x in conflicts if x]
    if conflicts:
        raise ValueError('Refusing to overwrite existing project files:\n' + '\n'.join(conflicts[:15]))
    did_exist = root.exists()
    root.mkdir(parents=True, exist_ok=True)
    newly_written=[]
    wrote = 0
    try:
        for rel, content in sorted(files.items()):
            path = root / rel
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name('.' + path.name + '.install-tmp')
            try:
                with tmp.open('xb') as fh:
                    fh.write(content)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
                newly_written.append(path)
                # Source helper executable flags apply only to project-local script files.
                if rel.endswith('.sh') and '/skills/' in rel:
                    path.chmod(0o755)
                wrote += 1
            finally:
                tmp.unlink(missing_ok=True)
    except BaseException:
        # Preserve all preexisting content. Roll back only newly-created files.
        for path in reversed(newly_written):
            path.unlink(missing_ok=True)
        if not did_exist:
            for folder in sorted((x for x in root.rglob('*') if x.is_dir()),key=lambda x:len(x.parts),reverse=True):
                try:folder.rmdir()
                except OSError:pass
            try:root.rmdir()
            except OSError:pass
        raise
    return {'project': str(root), 'skills': len(EXPECTED_SKILLS) + len(architect.SKILLS), 'architect_skills': len(architect.SKILLS), 'runtimes': len(SKILL_ROOTS), 'written_files': wrote,
            'tool_scope': 'PROJECT_ONLY', 'workflow_cli': 'NONE', 'native_skill_load': 'NOT_VERIFIED',
            'startup': 'New session: read docs/tasks/active/*, completed/* and legacy progress.md then show task summary.'}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='One-time AgentFlow Native Skills + project tool installer (NO runtime CLI)')
    ap.add_argument('project', help='Destination project path. Existing conflicting files are never overwritten.')
    ap.add_argument('--upstream-zip', help='Local official Superpowers ZIP at the pinned commit; useful for offline installs')
    ap.add_argument('--architect-archive-dir', help='Offline directory with 3 pinned GitHub source ZIPs: MUSUBI-<commit>.zip, skills-<commit>.zip, ECC-<commit>.zip')
    ap.add_argument('--skip-tools', action='store_true', help='ONLY for offline tests. Skips required RTK/CRG provisioning; not production READY.')
    ap.add_argument('--no-browser', action='store_true', help='Skip optional browser provisioning when system Chrome is unavailable')
    ns = ap.parse_args(argv)
    try:
        # Fail before any project writes if one of the 8 architect sources is unavailable.
        architect_package = architect.load_package(Path(ns.architect_archive_dir) if ns.architect_archive_dir else None)
        if ns.upstream_zip:
            blob = Path(ns.upstream_zip).read_bytes()
        else:
            print(f'Fetching pinned {SOURCE}@{COMMIT} ...', flush=True)
            request = urllib.request.Request(ARCHIVE_URL, headers={'User-Agent':'AgentFlow-Native-Skills-Installer/0.2'})
            with urllib.request.urlopen(request, timeout=40) as response:
                blob = response.read(MAX_ZIP_BYTES + 1)
        output = install(Path(ns.project), Path(__file__).resolve().parent, blob, architect_package=architect_package)
        if ns.skip_tools:
            output['tool_provision'] = {'status':'SKIPPED','reason':'EXPLICIT_SKIP_TOOLS'}
        else:
            output['tool_provision'] = tool_provision.provision(Path(ns.project), browser=not ns.no_browser)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        if output['tool_provision']['status']=='BLOCKED':
            print('TOOL_INSTALL_BLOCKED: review project-local tool results and retry installation; no global fallback',file=sys.stderr)
            return 2
        return 0
    except Exception as exc:
        print(f'INSTALL_BLOCKED: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
