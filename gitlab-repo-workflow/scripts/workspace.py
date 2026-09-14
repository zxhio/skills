#!/usr/bin/env python3
"""Prepare and release reusable Git worktree slots for gitlab-repo-workflow."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PROTECTED_PREFIXES = ("dev/", "release/")
PROTECTED_NAMES = {"main", "master", "dev"}


class WorkspaceError(RuntimeError):
    pass


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise WorkspaceError(f"{' '.join(args)} failed: {detail}")
    return result.stdout.strip()


def ref_exists(repo: Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref],
        cwd=repo,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def repo_root() -> Path:
    return Path(run("git", "rev-parse", "--show-toplevel")).resolve()


def worktree_root(repo: Path, explicit: str | None) -> Path:
    value = explicit or os.environ.get("WORKFLOW_WORKTREE_ROOT")
    return Path(value).expanduser().resolve() if value else repo.parent / f"{repo.name}-worktrees"


def worktrees(repo: Path) -> dict[Path, str | None]:
    output = run("git", "worktree", "list", "--porcelain", cwd=repo)
    result: dict[Path, str | None] = {}
    current: Path | None = None
    branch: str | None = None
    for line in output.splitlines() + [""]:
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree ")).resolve()
            branch = None
        elif line.startswith("branch "):
            branch = line.removeprefix("branch ").removeprefix("refs/heads/")
        elif not line and current is not None:
            result[current] = branch
            current = None
    return result


def clean(path: Path) -> bool:
    return not run("git", "status", "--porcelain", "--untracked-files=all", cwd=path)


def default_base(repo: Path, remote: str) -> str:
    if not ref_exists(repo, f"refs/remotes/{remote}/dev"):
        raise WorkspaceError(f"no {remote}/dev branch found")
    return f"{remote}/dev"


def validate_topic(branch: str) -> None:
    if not branch or branch.startswith(PROTECTED_PREFIXES) or branch in PROTECTED_NAMES:
        raise WorkspaceError(f"refusing to use protected branch as a task branch: {branch}")
    if ".." in branch or branch.startswith("/") or branch.endswith("/"):
        raise WorkspaceError(f"invalid task branch: {branch}")


def next_slot(root: Path, registered: dict[Path, str | None]) -> str:
    for number in range(1, 1000):
        name = f"task-{number:02d}"
        path = (root / name).resolve()
        if path not in registered and not path.exists():
            return name
        if registered.get(path) is None:
            return name
    raise WorkspaceError(f"no reusable task slot under {root}")


def emit(value: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    else:
        for key, item in value.items():
            print(f"{key}: {item}")


def allocate_slot(args: argparse.Namespace, repo: Path) -> tuple[str, Path, str | None]:
    root = worktree_root(repo, args.root)
    root.mkdir(parents=True, exist_ok=True)
    registered = worktrees(repo)
    slot = args.slot or next_slot(root, registered)
    path = (root / slot).resolve()

    current = registered.get(path, "__missing__")
    if current == "__missing__" and path.exists() and any(path.iterdir()):
        raise WorkspaceError(f"slot directory is not empty and is not a worktree: {path}")
    if current not in ("__missing__", None):
        raise WorkspaceError(f"slot is occupied by {current}: {path}")
    if path.exists() and not clean(path):
        raise WorkspaceError(f"slot has uncommitted or untracked files: {path}")
    return slot, path, current


def start(args: argparse.Namespace) -> None:
    repo = repo_root()
    validate_topic(args.branch)
    remote = args.remote
    run("git", "fetch", remote, "--prune", cwd=repo)
    base = args.base or default_base(repo, remote)
    current_branch = run("git", "branch", "--show-current", cwd=repo)
    if args.base and args.base.removeprefix(f"{remote}/") == current_branch:
        raise WorkspaceError("base cannot be the current task branch; choose the dev integration branch")
    base_sha = run("git", "rev-parse", base, cwd=repo)

    if ref_exists(repo, f"refs/heads/{args.branch}"):
        raise WorkspaceError(f"local branch already exists: {args.branch}; use attach for existing branches")
    if ref_exists(repo, f"refs/remotes/{remote}/{args.branch}"):
        raise WorkspaceError(f"remote branch already exists: {remote}/{args.branch}; use attach for existing branches")

    slot, path, current = allocate_slot(args, repo)

    if current is None:
        run("git", "switch", "--detach", base, cwd=path)
        run("git", "switch", "-c", args.branch, cwd=path)
    else:
        run("git", "worktree", "add", "-b", args.branch, str(path), base, cwd=repo)

    emit(
        {
            "action": "start",
            "branch": args.branch,
            "base": base,
            "base_sha": base_sha,
            "path": str(path),
            "slot": slot,
        },
        args.json,
    )


def attach(args: argparse.Namespace) -> None:
    repo = repo_root()
    validate_topic(args.branch)
    remote = args.remote
    run("git", "fetch", remote, "--prune", cwd=repo)

    local_exists = ref_exists(repo, f"refs/heads/{args.branch}")
    remote_exists = ref_exists(repo, f"refs/remotes/{remote}/{args.branch}")
    if not local_exists and not remote_exists:
        raise WorkspaceError(
            f"branch does not exist locally or on {remote}: {args.branch}; use start for new tasks"
        )

    registered = worktrees(repo)
    if local_exists and args.branch in registered.values():
        raise WorkspaceError(f"branch is already checked out in a worktree: {args.branch}")

    sync = "local-only"
    if local_exists and remote_exists:
        counts = run(
            "git", "rev-list", "--left-right", "--count",
            f"{args.branch}...{remote}/{args.branch}", cwd=repo,
        ).split()
        ahead, behind = int(counts[0]), int(counts[1])
        if ahead and behind:
            sync = f"diverged (ahead {ahead}, behind {behind})"
        elif ahead:
            sync = f"ahead {ahead}"
        elif behind:
            sync = f"behind {behind}"
        else:
            sync = "up-to-date"
    elif remote_exists:
        sync = "remote-only"

    base = args.base or default_base(repo, remote)
    branch_ref = args.branch if local_exists else f"{remote}/{args.branch}"
    base_sha = run("git", "merge-base", base, branch_ref, cwd=repo)

    slot, path, current = allocate_slot(args, repo)

    if current is None:
        if local_exists:
            run("git", "switch", args.branch, cwd=path)
        else:
            run("git", "switch", "--track", "-c", args.branch, f"{remote}/{args.branch}", cwd=path)
    else:
        if local_exists:
            run("git", "worktree", "add", str(path), args.branch, cwd=repo)
        else:
            run("git", "worktree", "add", "--track", "-b", args.branch, str(path),
                f"{remote}/{args.branch}", cwd=repo)

    emit(
        {
            "action": "attach",
            "branch": args.branch,
            "base": base,
            "base_sha": base_sha,
            "path": str(path),
            "slot": slot,
            "sync": sync,
        },
        args.json,
    )


def close(args: argparse.Namespace) -> None:
    if not args.confirm_merged:
        raise WorkspaceError("close requires --confirm-merged after GitLab confirmed the MR is merged")
    repo = repo_root()
    root = worktree_root(repo, args.root)
    path = (root / args.slot).resolve()
    registered = worktrees(repo)
    current = registered.get(path, "__missing__")
    if current == "__missing__":
        raise WorkspaceError(f"slot is not a registered worktree: {path}")
    if current is not None and args.branch and current != args.branch:
        raise WorkspaceError(f"slot branch is {current}, expected {args.branch}")
    if not clean(path):
        raise WorkspaceError(f"cannot close dirty worktree: {path}")

    branch = current
    if branch is not None:
        validate_topic(branch)
        run("git", "switch", "--detach", cwd=path)
        run("git", "branch", "-D", branch, cwd=repo)

    emit(
        {"action": "close", "branch": branch, "path": str(path), "slot": args.slot, "state": "free"},
        args.json,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="action", required=True)

    start_parser = sub.add_parser("start", help="create a new task branch and worktree")
    start_parser.add_argument("branch")
    start_parser.add_argument("--base", help="explicit base branch; defaults to remote dev")
    start_parser.add_argument("--remote", default="origin")
    start_parser.add_argument("--root", help="worktree root directory")
    start_parser.add_argument("--slot", help="reusable slot name, such as task-01")
    start_parser.add_argument("--json", action="store_true")
    start_parser.set_defaults(handler=start)

    attach_parser = sub.add_parser("attach", help="attach an existing local or remote branch to a worktree")
    attach_parser.add_argument("branch")
    attach_parser.add_argument("--base", help="explicit base branch; defaults to remote dev")
    attach_parser.add_argument("--remote", default="origin")
    attach_parser.add_argument("--root", help="worktree root directory")
    attach_parser.add_argument("--slot", help="reusable slot name, such as task-01")
    attach_parser.add_argument("--json", action="store_true")
    attach_parser.set_defaults(handler=attach)

    close_parser = sub.add_parser("close", help="close a merged task and release its worktree slot")
    close_parser.add_argument("--slot", required=True)
    close_parser.add_argument("--branch")
    close_parser.add_argument("--root", help="worktree root directory")
    close_parser.add_argument("--confirm-merged", action="store_true")
    close_parser.add_argument("--json", action="store_true")
    close_parser.set_defaults(handler=close)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.handler(args)
        return 0
    except WorkspaceError as error:
        print(f"workspace: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
