#!/usr/bin/env python3
"""Create or locate local Git worktrees for workflow tasks; emit JSON."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def git(repo, *args, optional=False):
    result = subprocess.run(['git', '-C', str(repo), *args], text=True, capture_output=True)
    if result.returncode and not optional:
        raise ValueError(result.stderr.strip() or 'Git command failed')
    return result.stdout.strip() if not result.returncode else ''


def exists(repo, ref):
    return bool(git(repo, 'rev-parse', '--verify', ref, optional=True))


def prepare(args):
    repo = Path(args.repo).expanduser().resolve()
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir'))
    primary = common.parent if common.name == '.git' else common
    git(repo, 'check-ref-format', f'refs/heads/{args.branch}')
    base = git(repo, 'rev-parse', '--symbolic-full-name', '--verify', args.base)
    if not base.startswith(('refs/heads/', 'refs/remotes/')):
        raise ValueError('--base must identify a local or fetched remote branch')
    if base == f'refs/heads/{args.branch}' or base == f'refs/remotes/{args.remote}/{args.branch}':
        raise ValueError('Task branch must differ from the target base')
    git(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')
    local = f'refs/heads/{args.branch}'
    remote = f'refs/remotes/{args.remote}/{args.branch}'
    local_exists = exists(repo, local)
    remote_exists = exists(repo, remote)
    if args.action == 'start' and (local_exists or remote_exists):
        raise ValueError('Branch already exists; use attach')
    if args.action == 'attach' and not (local_exists or remote_exists):
        raise ValueError('Branch not found locally; fetch the selected remote first')
    registered = git(repo, 'worktree', 'list', '--porcelain', '-z')
    records = registered.split('\0\0')
    path = None
    for record in records:
        fields = record.split('\0')
        if f'branch {local}' in fields:
            path = Path(next(field[9:] for field in fields if field.startswith('worktree ')))
            break
    if path is None:
        root = primary.parent / f'{primary.name}-worktrees'
        occupied = {field[9:] for field in registered.split('\0') if field.startswith('worktree ')}
        for number in range(1, 10000):
            candidate = root / f'task-{number:02d}'
            if not candidate.exists() and str(candidate) not in occupied:
                path = candidate
                break
        if path is None:
            raise ValueError('No available worktree slot')
        root.mkdir(parents=True, exist_ok=True)
        if args.action == 'start':
            git(repo, 'worktree', 'add', '-b', args.branch, str(path), base)
        elif local_exists:
            git(repo, 'worktree', 'add', str(path), args.branch)
        else:
            git(repo, 'worktree', 'add', '--track', '-b', args.branch, str(path), remote)
    return {'action': args.action, 'repo': str(primary), 'path': str(path),
            'branch': args.branch, 'base': base,
            'base_sha': git(repo, 'merge-base', base, local),
            'dirty': bool(git(path, 'status', '--porcelain', '--untracked-files=all'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'attach'))
    parser.add_argument('branch')
    parser.add_argument('--repo', default='.')
    parser.add_argument('--base', required=True)
    parser.add_argument('--remote', default='origin')
    args = parser.parse_args()
    try:
        result = prepare(args)
    except (ValueError, OSError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
