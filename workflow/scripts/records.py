#!/usr/bin/env python3
"""Resolve workflow storage and maintain dependency-aware Markdown task records."""

from __future__ import annotations

import argparse
from datetime import datetime
from graphlib import CycleError, TopologicalSorter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

try:
    import yaml
except ImportError:
    sys.exit('PyYAML is required: python3 -m pip install pyyaml')

STATUSES = ('pending', 'in_progress', 'completed', 'blocked', 'cancelled')
INTEGRATION = {'main', 'master', 'develop', 'dev'}


def git(repo: Path, *args: str, optional: bool = False) -> str:
    proc = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if proc.returncode and not optional:
        raise ValueError(proc.stderr.strip() or 'Git command failed')
    return proc.stdout.strip() if proc.returncode == 0 else ''


def plugin_name() -> str:
    for parent in Path(__file__).resolve().parents:
        manifest = parent / '.codex-plugin/plugin.json'
        if manifest.is_file():
            name = json.loads(manifest.read_text())['name']
            if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', name):
                raise ValueError('Invalid plugin name in manifest')
            return name
    return 'workflow'


def roots() -> dict:
    storage = Path.home() / '.workflow'
    namespace = storage / plugin_name()
    config = namespace / 'config.yaml'
    data = yaml.safe_load(config.read_text()) if config.exists() else {}
    if data is None:
        data = {}
    if not isinstance(data, dict) or set(data) - {'spec_dir', 'task_dir'}:
        raise ValueError('Config accepts only spec_dir and task_dir')
    result = {'config': str(config)}
    for key, default in [('spec_dir', storage / 'spec'), ('task_dir', storage)]:
        value = data.get(key, str(default))
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'{key} must be a non-empty path')
        path = Path(value).expanduser()
        result[key] = str((path if path.is_absolute() else namespace / path).resolve())
    return result


def within(root: str, *parts: str) -> Path:
    base = Path(root).resolve()
    path = base.joinpath(*parts).resolve()
    if not path.is_relative_to(base):
        raise ValueError('Generated path escapes its storage root')
    return path


def paths(args: argparse.Namespace) -> dict:
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', args.topic):
        raise ValueError('Topic must be English kebab-case')
    document = getattr(args, 'name', None) or args.topic
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', document):
        raise ValueError('--name must be English kebab-case without a file extension')
    repo = Path(args.repo).expanduser().resolve()
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    primary = common.parent if common.name == '.git' else common
    name = primary.name
    origin = git(repo, 'remote', 'get-url', 'origin', optional=True)
    branch = args.branch or git(repo, 'symbolic-ref', '--short', 'HEAD', optional=True)
    if not args.branch and (branch in INTEGRATION or branch.startswith(('dev/', 'release/'))):
        branch = ''
    line = args.line
    for label, value in [('branch', branch), ('line', line)]:
        if value:
            git(repo, 'check-ref-format', f'refs/heads/{value}')
            if any(part in ('', '.', '..') for part in value.split('/')):
                raise ValueError(f'Invalid {label} path')
    if getattr(args, 'kind', None) == 'task' and not (line and branch):
        raise ValueError('Specify the target line with --line and the planned task branch with --branch')
    result = {**roots(), 'repo': name, 'repo_path': str(primary), 'origin': origin,
              'branch': branch or None, 'line': line}
    spec_root = within(result['spec_dir'], name)
    spec_candidates = sorted(p for p in spec_root.glob(f'????????-{args.topic}/*.md')
                             if p.is_file() and valid_date(p.parent.name[:8]))
    result['spec_candidates'] = [str(p) for p in spec_candidates]
    result['task'] = None
    result['candidates'] = []
    directory = None
    candidates = []
    if branch and line:
        directory = within(result['task_dir'], name, line, branch)
        candidates = sorted(p for p in directory.glob(f'????????-{args.topic}.md')
                            if p.is_file() and valid_date(p.name[:8]))
        result['candidates'] = [str(p) for p in candidates]
    if args.date and not valid_date(args.date):
        raise ValueError('--date must be a valid YYYYMMDD date')
    dates = {p.parent.name[:8] for p in spec_candidates} | {p.name[:8] for p in candidates}
    if not args.date and len(dates) > 1:
        raise ValueError('Multiple planning dates match; select --date or resume by explicit path: '
                         + ', '.join(sorted(dates)))
    date = args.date or next(iter(dates), f'{datetime.now():%Y%m%d}')
    result['date'] = date
    result['spec_directory'] = str(within(result['spec_dir'], name, f'{date}-{args.topic}'))
    result['spec'] = str(within(result['spec_directory'], document + '.md'))
    if directory is not None:
        result['task'] = str(within(str(directory), f'{date}-{args.topic}.md'))
    return result


def valid_date(value: str) -> bool:
    if not re.fullmatch(r'[0-9]{8}', value):
        return False
    try:
        datetime.strptime(value, '%Y%m%d')
    except ValueError:
        return False
    return True


def read_task(text: str) -> tuple[dict, str]:
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.S)
    if not match:
        raise ValueError('Task file requires YAML frontmatter with tasks')
    data = yaml.safe_load(match[1])
    validate(data)
    return data, text[match.end():]


def validate(data: dict) -> dict[str, dict]:
    if not isinstance(data, dict) or not isinstance(data.get('tasks'), list) or not data['tasks']:
        raise ValueError('tasks must be a non-empty list')
    tasks = {}
    for task in data['tasks']:
        if not isinstance(task, dict):
            raise ValueError('Each task must be a mapping')
        ident = task.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'T[0-9]+', ident) or ident in tasks:
            raise ValueError(f'Invalid or duplicate task ID: {ident}')
        for key in ('subject', 'acceptance'):
            if not isinstance(task.get(key), str) or not task[key].strip():
                raise ValueError(f'{ident} requires {key}')
        task.setdefault('status', 'pending')
        task.setdefault('depends_on', [])
        if task['status'] not in STATUSES:
            raise ValueError(f'Invalid status for {ident}')
        deps = task['depends_on']
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
            raise ValueError(f'{ident} depends_on must be a list of task IDs')
        if len(set(deps)) != len(deps):
            raise ValueError(f'{ident} has duplicate dependencies')
        if task['status'] in ('completed', 'blocked') and (
                not isinstance(task.get('result'), str) or not task['result'].strip()):
            raise ValueError(f'{ident} requires result for {task["status"]}')
        tasks[ident] = task
    for ident, task in tasks.items():
        if set(task['depends_on']) - tasks.keys():
            raise ValueError(f'{ident} has unknown dependencies')
    try:
        tuple(TopologicalSorter({i: t['depends_on'] for i, t in tasks.items()}).static_order())
    except CycleError as exc:
        raise ValueError('Task dependencies contain a cycle') from exc
    for ident, task in tasks.items():
        if task['status'] in ('in_progress', 'completed'):
            if any(tasks[dep]['status'] != 'completed' for dep in task['depends_on']):
                raise ValueError(f'{ident} has unfinished dependencies')
    return tasks


def render(data: dict, body: str) -> str:
    return '---\n' + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + '---\n' + body


def write(path: Path, text: str, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        with path.open('x') as stream:
            stream.write(text)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def save(args: argparse.Namespace) -> dict:
    resolved = paths(args)
    target = resolved[args.kind]
    if target is None:
        raise ValueError('Specify the target line with --line and the planned task branch with --branch')
    path = Path(target)
    if path.exists() and not args.replace:
        raise ValueError(f'File exists; resume it or use --replace: {path}')
    text = Path(args.input).expanduser().read_text()
    if not text.strip():
        raise ValueError('Input document is empty')
    if args.kind == 'task':
        data, body = read_task(text)
        identity = {k: resolved[k] for k in ('repo', 'repo_path', 'origin', 'line', 'branch')}
        if path.exists():
            previous, _ = read_task(path.read_text())
            if any(previous.get(k) != value for k, value in identity.items()
                   if k != 'line' or k in previous):
                raise ValueError('Existing task record belongs to a different repository, line or branch')
            data['created'] = previous.get('created', path.name[:8])
        else:
            data['created'] = path.name[:8]
        data.update(identity)
        text = render(data, body)
    write(path, text, args.replace)
    return {'path': str(path), 'kind': args.kind}


def ready(args: argparse.Namespace) -> dict:
    data, _ = read_task(Path(args.file).expanduser().read_text())
    tasks = validate(data)
    selected = set(args.only or tasks)
    if selected - tasks.keys():
        raise ValueError('Unknown selected task IDs')
    result = {'ready': [], 'running': [], 'blocked': {}, 'completed': [], 'cancelled': []}
    for ident, task in tasks.items():
        if ident not in selected:
            continue
        deps = [dep for dep in task['depends_on'] if tasks[dep]['status'] != 'completed']
        status = task['status']
        if status == 'pending' and not deps:
            result['ready'].append(ident)
        elif status == 'blocked' or (status == 'pending' and deps):
            result['blocked'][ident] = {'dependencies': deps, 'reason': task.get('result', '')}
        else:
            result['running' if status == 'in_progress' else status].append(ident)
    return result


def status(args: argparse.Namespace) -> dict:
    path = Path(args.file).expanduser()
    original = path.read_text()
    data, body = read_task(original)
    task = validate(data).get(args.task_id)
    if task is None:
        raise ValueError(f'Unknown task: {args.task_id}')
    if args.status in ('completed', 'blocked') and not (args.result and args.result.strip()):
        raise ValueError(f'{args.status} requires --result from this execution')
    task['status'] = args.status
    if args.result is not None:
        task['result'] = args.result
    if args.commit is not None:
        if not re.fullmatch(r'[0-9a-fA-F]{7,64}', args.commit):
            raise ValueError('commit must be a Git SHA')
        task['commit'] = args.commit
    task['updated'] = datetime.now().astimezone().isoformat(timespec='seconds')
    validate(data)
    if path.read_text() != original:
        raise ValueError('Task file changed during update; reload before retrying')
    write(path, render(data, body), replace=True)
    return {'path': str(path), 'task': task}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('paths', 'save'):
        sub = commands.add_parser(command)
        if command == 'save':
            sub.add_argument('kind', choices=('spec', 'task'))
            sub.add_argument('--input', required=True, help='UTF-8 Markdown source file')
            sub.add_argument('--replace', action='store_true')
        sub.add_argument('--repo', default='.')
        sub.add_argument('--topic', required=True)
        sub.add_argument('--name', help='Spec document name without .md; defaults to the topic')
        sub.add_argument('--branch')
        sub.add_argument('--line', help='Target integration branch, preserving its full path')
        sub.add_argument('--date', help='Planning date YYYYMMDD; defaults to a unique existing date or today')
    sub = commands.add_parser('ready')
    sub.add_argument('file')
    sub.add_argument('--only', nargs='+')
    sub = commands.add_parser('status')
    sub.add_argument('file')
    sub.add_argument('task_id')
    sub.add_argument('status', choices=STATUSES)
    sub.add_argument('--result')
    sub.add_argument('--commit')
    args = parser.parse_args()
    try:
        result = {'paths': paths, 'save': save, 'ready': ready, 'status': status}[args.command](args)
    except (ValueError, OSError, KeyError, yaml.YAMLError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
