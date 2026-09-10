#!/usr/bin/env python3
"""Prepare and release reusable Git worktree slots for gitlab-repo-workflow."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


DEV_BRANCH = re.compile(r"^dev/v(\d+)\.(\d+)\.(\d+)$")
PROTECTED_PREFIXES = ("dev/", "release/")
PROTECTED_NAMES = {"main", "master"}


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


def latest_dev(repo: Path, remote: str) -> str:
    refs = run(
        "git",
        "for-each-ref",
        "--format=%(refname:short)",
        f"refs/remotes/{remote}/dev/v*",
        cwd=repo,
    ).splitlines()
    versions = []
    for ref in refs:
        match = DEV_BRANCH.fullmatch(ref.removeprefix(f"{remote}/"))
        if match:
            versions.append((tuple(int(value) for value in match.groups()), ref))
    if not versions:
        raise WorkspaceError(f"no valid {remote}/dev/vX.Y.Z branch found")
    return max(versions)[1]


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


def start(args: argparse.Namespace) -> None:
    repo = repo_root()
    validate_topic(args.branch)
    remote = args.remote
    run("git", "fetch", remote, "--prune", cwd=repo)
    base = args.base or latest_dev(repo, remote)
    current_branch = run("git", "branch", "--show-current", cwd=repo)
    if args.base and args.base.removeprefix(f"{remote}/") == current_branch:
        raise WorkspaceError("base cannot be the current task branch; choose a dev/vX.Y.Z branch")
    base_sha = run("git", "rev-parse", base, cwd=repo)
    root = worktree_root(repo, args.root)
    root.mkdir(parents=True, exist_ok=True)
    registered = worktrees(repo)
    slot = args.slot or next_slot(root, registered)
    path = (root / slot).resolve()

    if ref_exists(repo, f"refs/heads/{args.branch}"):
        raise WorkspaceError(f"local branch already exists: {args.branch}")

    current = registered.get(path, "__missing__")
    if current == "__missing__" and path.exists() and any(path.iterdir()):
        raise WorkspaceError(f"slot directory is not empty and is not a worktree: {path}")
    if current not in ("__missing__", None):
        raise WorkspaceError(f"slot is occupied by {current}: {path}")
    if path.exists() and not clean(path):
        raise WorkspaceError(f"slot has uncommitted or untracked files: {path}")

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

    start_parser = sub.add_parser("start", help="create or reuse a task worktree")
    start_parser.add_argument("branch")
    start_parser.add_argument("--base", help="explicit base branch; defaults to newest remote dev/vX.Y.Z")
    start_parser.add_argument("--remote", default="origin")
    start_parser.add_argument("--root", help="worktree root directory")
    start_parser.add_argument("--slot", help="reusable slot name, such as task-01")
    start_parser.add_argument("--json", action="store_true")
    start_parser.set_defaults(handler=start)

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
