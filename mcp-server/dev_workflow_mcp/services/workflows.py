"""Workflow use cases, scoped to explicit repository paths."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field

from ..infrastructure.github_cli import (
    _gh_current_login,
    _gh_object,
    _resolve_repo,
    _temporary_body_file,
)
from ..infrastructure.git import (
    _absolute_new_path,
    _current_branch,
    _require_clean_worktree,
    _safe_relative_path,
    _same_git_common_dir,
    _sha256,
    _staged_path_names,
    _valid_local_branch,
    _valid_remote_branch,
    _validate_stage_path,
    _requested_repo_paths,
)
from ..infrastructure.paths import _run_repo, _validated_repo_path
from ..infrastructure.process import _run_fixed
from ..policy import OID_PATTERN, REPO_PATTERN, WORK_BRANCH_PATTERN, branch_errors as _branch_errors
from .validation import check_commit_message


class ManifestEntry(BaseModel):
    path: str = Field(description="仓库根目录相对 POSIX 路径")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size: int = Field(ge=0)


def audit_repository_state(repo_path: str) -> dict[str, Any]:
    """只读审计指定仓库的根路径、当前分支、工作区状态、remote 名称及 GitHub Fork/default branch 信息。

    固定读取：git rev-parse、git status --short --branch、git remote、git branch --show-current、
    gh repo view --json parent,defaultBranchRef,nameWithOwner。Remote URL 不输出，避免意外泄露嵌入凭据。
    """
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    status = _run_fixed(["git", "status", "--short", "--branch", "--untracked-files=all"], cwd=root)
    remotes = _run_fixed(["git", "remote"], cwd=root)
    branch = _current_branch(root)
    gh = _run_fixed(
        ["gh", "repo", "view", "--json", "nameWithOwner,parent,defaultBranchRef"], cwd=root
    )
    gh_info: dict[str, Any] | None = None
    gh_error = None
    if gh.returncode == 0:
        try:
            candidate = json.loads(gh.stdout)
            gh_info = candidate if isinstance(candidate, dict) else None
        except json.JSONDecodeError:
            gh_error = "gh repo view returned invalid JSON"
    else:
        gh_error = f"gh repo view unavailable or failed (exit {gh.returncode})"
    return {
        "ok": status.returncode == 0 and remotes.returncode == 0,
        "repo_path": root,
        "current_branch": branch,
        "status_lines": status.stdout.splitlines() if status.returncode == 0 else [],
        "remotes": remotes.stdout.splitlines() if remotes.returncode == 0 else [],
        "github": gh_info,
        "github_error": gh_error,
        "errors": [message for message in (
            None if status.returncode == 0 else "git status failed",
            None if remotes.returncode == 0 else "git remote failed",
        ) if message],
    }


def list_repository_worktrees(repo_path: str) -> dict[str, Any]:
    """只读列出指定仓库的 worktree 路径、HEAD 和分支；不创建或移除 worktree。"""
    result, root, error = _run_repo(repo_path, ["git", "worktree", "list", "--porcelain"])
    if error:
        return {"ok": False, "worktrees": [], "error": error}
    entries: list[dict[str, str | bool]] = []
    current: dict[str, str | bool] = {}
    for line in result.stdout.splitlines() + [""]:
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current["path"] = value
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
        elif key == "detached":
            current["detached"] = True
        elif key == "locked":
            current["locked"] = True
    return {"ok": result.returncode == 0, "repo_path": root, "worktrees": entries, "error": None if result.returncode == 0 else "git worktree list failed"}


def switch_repository_branch(repo_path: str, branch_name: str) -> dict[str, Any]:
    """在授权后切换指定仓库的本地分支。副作用：改变该 worktree 当前检出的分支；拒绝不安全或不存在的目标。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    error = _valid_local_branch(root, branch_name)
    if error:
        return {"ok": False, "error": error}
    exists = _run_fixed(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"], cwd=root)
    if exists.returncode != 0:
        return {"ok": False, "error": "本地目标分支不存在；不自动创建或追踪 remote 分支"}
    status = _run_fixed(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)
    if status.returncode != 0 or any(not line.startswith("?? ") for line in status.stdout.splitlines()):
        return {"ok": False, "error": "存在已跟踪的暂存或未暂存更改，切换已拒绝"}
    result = _run_fixed(["git", "switch", "--", branch_name], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "branch_name": branch_name, "error": None if result.returncode == 0 else "git switch failed; existing user data was not intentionally discarded"}


def pull_origin_branch_fast_forward(repo_path: str, branch_name: str) -> dict[str, Any]:
    """在授权后将当前同名本地分支以 `git pull --ff-only origin <branch>` 快进同步。要求跟踪更改干净且当前分支匹配。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if not _valid_remote_branch(branch_name):
        return {"ok": False, "error": "branch_name 格式无效"}
    if _current_branch(root) != branch_name:
        return {"ok": False, "error": "当前分支必须与 branch_name 完全一致"}
    status = _run_fixed(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)
    if status.returncode != 0 or any(not line.startswith("?? ") for line in status.stdout.splitlines()):
        return {"ok": False, "error": "存在已跟踪的暂存或未暂存更改，pull 已拒绝"}
    result = _run_fixed(["git", "pull", "--ff-only", "origin", branch_name], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "branch_name": branch_name, "error": None if result.returncode == 0 else "git pull --ff-only 失败；未执行非快进替代操作"}


def fetch_upstream_branch(repo_path: str, branch_name: str) -> dict[str, Any]:
    """在授权后执行固定的 `git fetch upstream <branch>` 更新 remote-tracking 信息。需要 Codex writes approval；不合并、不推送。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if not _valid_remote_branch(branch_name):
        return {"ok": False, "error": "branch_name 格式无效"}
    remote = _run_fixed(["git", "remote"], cwd=root)
    if remote.returncode != 0 or "upstream" not in remote.stdout.splitlines():
        return {"ok": False, "error": "未配置 upstream remote；不自动添加 remote"}
    result = _run_fixed(["git", "fetch", "upstream", branch_name], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "remote": "upstream", "branch_name": branch_name, "error": None if result.returncode == 0 else "git fetch upstream 失败"}


def merge_upstream_branch_fast_forward(repo_path: str, branch_name: str) -> dict[str, Any]:
    """在授权后将 upstream/<branch> 以 `git merge --ff-only` 合入当前同名本地分支。副作用：更新本地分支和工作区；不创建 merge commit。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if not _valid_remote_branch(branch_name):
        return {"ok": False, "error": "branch_name 格式无效"}
    if _current_branch(root) != branch_name:
        return {"ok": False, "error": "当前分支必须与 branch_name 完全一致"}
    status = _run_fixed(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)
    if status.returncode != 0 or status.stdout.strip():
        return {"ok": False, "error": "工作区必须完全干净才能合并 upstream"}
    remote = _run_fixed(["git", "remote"], cwd=root)
    if remote.returncode != 0 or "upstream" not in remote.stdout.splitlines():
        return {"ok": False, "error": "未配置 upstream remote；不自动添加 remote"}
    fetched = _run_fixed(["git", "show-ref", "--verify", f"refs/remotes/upstream/{branch_name}"], cwd=root)
    if fetched.returncode != 0:
        return {"ok": False, "error": "upstream ref 不存在；请先单独 fetch"}
    result = _run_fixed(["git", "merge", "--ff-only", f"upstream/{branch_name}"], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "branch_name": branch_name, "error": None if result.returncode == 0 else "git merge --ff-only 失败；保留现场"}


def rebase_repository_branch(repo_path: str, branch_name: str, base_branch: str) -> dict[str, Any]:
    """在明确授权后将当前 branch_name rebase 到已存在的本地 base_branch。要求工作区完全干净且当前分支匹配；副作用：改写当前分支提交历史。若冲突或失败立即停止，不自动 continue/abort/reset。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if (error := _valid_local_branch(root, branch_name)) or (error := _valid_local_branch(root, base_branch)):
        return {"ok": False, "error": error}
    if branch_name == base_branch or _current_branch(root) != branch_name:
        return {"ok": False, "error": "当前分支必须等于 branch_name，且不能 rebase 到自身"}
    for name in (branch_name, base_branch):
        exists = _run_fixed(["git", "show-ref", "--verify", f"refs/heads/{name}"], cwd=root)
        if exists.returncode != 0:
            return {"ok": False, "error": f"本地分支不存在: {name}"}
    clean = _require_clean_worktree(root)
    if clean:
        return {"ok": False, "error": clean}
    result = _run_fixed(["git", "rebase", base_branch], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "branch_name": branch_name, "base_branch": base_branch,
            "error": None if result.returncode == 0 else "git rebase 失败或产生冲突；未执行后续恢复命令"}


def remove_repository_worktree(repo_path: str, target_worktree_path: str, branch_name: str) -> dict[str, Any]:
    """仅在用户明确要求移除指定本地 worktree 并授权后执行 `git worktree remove <path>`。要求路径属于同仓库、检出 branch_name、工作区干净；副作用：删除该 worktree 目录。不会删除本地分支或远端分支，也不使用 --force。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    requested = Path(target_worktree_path).expanduser()
    if not requested.is_absolute() or ".." in requested.parts:
        return {"ok": False, "error": "target_worktree_path 必须是绝对路径且不含 '..'"}
    try:
        target = requested.resolve(strict=True)
    except (OSError, RuntimeError):
        return {"ok": False, "error": "目标 worktree 不存在或无法解析"}
    if target == Path(root):
        return {"ok": False, "error": "拒绝移除 repo_path 本身"}
    target_root, error = _validated_repo_path(str(target))
    if error or not _same_git_common_dir(root, target_root):
        return {"ok": False, "error": error or "目标不是同一 Git 仓库的 worktree"}
    if _current_branch(target_root) != branch_name:
        return {"ok": False, "error": "目标当前分支与 branch_name 不符"}
    clean = _require_clean_worktree(target_root)
    if clean:
        return {"ok": False, "error": clean}
    result = _run_fixed(["git", "worktree", "remove", str(target)], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "target_worktree_path": str(target), "branch_name": branch_name,
            "error": None if result.returncode == 0 else "git worktree remove 失败；未使用 --force"}


def create_repository_worktree(repo_path: str, target_worktree_path: str, branch_name: str, base_branch: str) -> dict[str, Any]:
    """在授权后执行 `git worktree add <target> -b <branch> <base>`。会新增本地分支和目录；不执行同步、复制未跟踪文件或需求编辑。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if branch_name in {"main", "master"} or _branch_errors(branch_name):
        return {"ok": False, "error": "branch_name 未通过项目分支策略"}
    if (error := _valid_local_branch(root, branch_name)) is not None:
        return {"ok": False, "error": error}
    if (error := _valid_local_branch(root, base_branch)) is not None:
        return {"ok": False, "error": f"base_branch 无效: {error}"}
    base_exists = _run_fixed(["git", "show-ref", "--verify", f"refs/heads/{base_branch}"], cwd=root)
    branch_exists = _run_fixed(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"], cwd=root)
    if base_exists.returncode != 0:
        return {"ok": False, "error": "base_branch 必须是已核验的本地分支"}
    if branch_exists.returncode == 0:
        return {"ok": False, "error": "branch_name 已存在；不复用未核实的旧基点"}
    target, error = _absolute_new_path(target_worktree_path)
    if error:
        return {"ok": False, "error": error}
    if Path(target).exists():
        return {"ok": False, "error": "target_worktree_path 已存在，拒绝复用或覆盖"}
    if target == root or Path(target).is_relative_to(root):
        return {"ok": False, "error": "worktree 目标不能位于源仓库目录内"}
    worktrees = _run_fixed(["git", "worktree", "list", "--porcelain"], cwd=root)
    branch_ref = f"refs/heads/{branch_name}"
    if worktrees.returncode != 0:
        return {"ok": False, "error": "无法核验当前 worktree 拓扑"}
    if any(line == f"branch {branch_ref}" for line in worktrees.stdout.splitlines()):
        return {"ok": False, "error": "该分支已被其他 worktree 检出"}
    result = _run_fixed(["git", "worktree", "add", target, "-b", branch_name, base_branch], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "target_worktree_path": target, "branch_name": branch_name, "base_branch": base_branch, "error": None if result.returncode == 0 else "git worktree add 失败；不删除或回滚用户已有路径"}


def capture_untracked_file_manifest(repo_path: str) -> dict[str, Any]:
    """只读生成未被忽略的未跟踪普通文件清单，含相对 POSIX 路径、SHA-256 和字节数；不保存文件或搬动内容。拒绝符号链接和特殊文件。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "entries": [], "error": error}
    result = _run_fixed(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root)
    if result.returncode != 0:
        return {"ok": False, "entries": [], "error": "git status failed"}
    entries: list[dict[str, Any]] = []
    unsupported: list[str] = []
    for record in result.stdout.split("\0"):
        if not record.startswith("?? "):
            continue
        rel = _safe_relative_path(record[3:])
        if rel is None:
            unsupported.append(record[3:])
            continue
        path = Path(root).joinpath(*rel.parts)
        try:
            if not path.is_file() or path.is_symlink():
                unsupported.append(rel.as_posix())
                continue
        except OSError:
            unsupported.append(rel.as_posix())
            continue
        digest, size, hash_error = _sha256(path)
        if hash_error:
            unsupported.append(rel.as_posix())
        else:
            entries.append({"path": rel.as_posix(), "sha256": digest, "size": size})
    return {"ok": not unsupported, "repo_path": root, "entries": entries, "unsupported_paths": unsupported, "note": "Git status excludes ignored files; ignored files are not included."}


def copy_untracked_files_to_worktree(repo_path: str, target_worktree_path: str, manifest: list[ManifestEntry]) -> dict[str, Any]:
    """在授权后按先前清单复制未跟踪文件到同仓库 worktree。只复制 SHA-256/size 完全匹配的普通文件；拒绝覆盖、路径穿越、symlink 及目标不是同一仓库 worktree。需要 Codex writes approval。"""
    source, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "copied": [], "error": error}
    target_requested = Path(target_worktree_path).expanduser()
    if not target_requested.is_absolute() or ".." in target_requested.parts:
        return {"ok": False, "copied": [], "error": "target_worktree_path 必须为绝对路径且不能包含 '..'"}
    try:
        target = target_requested.resolve(strict=True)
    except (OSError, RuntimeError):
        return {"ok": False, "copied": [], "error": "目标 worktree 不存在或无法解析"}
    target_root, error = _validated_repo_path(str(target))
    if error or not _same_git_common_dir(source, target_root):
        return {"ok": False, "copied": [], "error": error or "目标不属于同一 Git 仓库的 worktree"}
    if not manifest:
        return {"ok": False, "copied": [], "error": "manifest 不能为空"}
    validated: list[tuple[PurePosixPath, Path, ManifestEntry]] = []
    seen: set[str] = set()
    for entry in manifest:
        rel = _safe_relative_path(entry.path)
        if rel is None or entry.path in seen:
            return {"ok": False, "copied": [], "error": f"manifest 路径无效或重复: {entry.path!r}"}
        seen.add(entry.path)
        source_file = Path(source).joinpath(*rel.parts)
        cursor = Path(source)
        if any((cursor := cursor / part).is_symlink() for part in rel.parts[:-1]):
            return {"ok": False, "copied": [], "error": f"源路径包含 symlink 目录: {entry.path}"}
        if source_file.is_symlink() or not source_file.is_file():
            return {"ok": False, "copied": [], "error": f"源文件已不存在、不是普通文件或为 symlink: {entry.path}"}
        digest, size, hash_error = _sha256(source_file)
        if hash_error or digest != entry.sha256 or size != entry.size:
            return {"ok": False, "copied": [], "error": f"源文件指纹与清单不一致: {entry.path}"}
        status = _run_fixed(["git", "check-ignore", "--no-index", "--quiet", "--", entry.path], cwd=source)
        if status.returncode == 0:
            return {"ok": False, "copied": [], "error": f"路径现在被忽略，拒绝复制: {entry.path}"}
        tracked = _run_fixed(["git", "ls-files", "--error-unmatch", "--", entry.path], cwd=source)
        if tracked.returncode == 0:
            return {"ok": False, "copied": [], "error": f"路径已跟踪，拒绝复制: {entry.path}"}
        current = _run_fixed(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", entry.path], cwd=source)
        if current.returncode != 0 or current.stdout.split("\0")[0] != f"?? {entry.path}":
            return {"ok": False, "copied": [], "error": f"路径当前不是 Git 未跟踪文件: {entry.path}"}
        validated.append((rel, source_file, entry))
    copied: list[str] = []
    try:
        for rel, source_file, entry in validated:
            destination = target.joinpath(*rel.parts)
            cursor = target
            for part in rel.parts[:-1]:
                cursor = cursor / part
                if cursor.exists() and (cursor.is_symlink() or not cursor.is_dir()):
                    raise ValueError(f"目标路径父组件冲突: {rel.as_posix()}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                raise ValueError(f"目标路径已存在，拒绝覆盖: {rel.as_posix()}")
            with source_file.open("rb") as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            digest, size, hash_error = _sha256(destination)
            if hash_error or digest != entry.sha256 or size != entry.size:
                raise ValueError(f"目标复制后指纹不匹配: {rel.as_posix()}")
            copied.append(rel.as_posix())
    except (OSError, ValueError) as exc:
        return {"ok": False, "copied": copied, "error": str(exc)}
    return {"ok": True, "copied": copied, "target_worktree_path": str(target), "staged": False}


def configure_project_hooks_path(repo_path: str) -> dict[str, Any]:
    """在授权后固定设置 `git config --local core.hooksPath .githooks`。要求 `.githooks/pre-commit` 和 `commit-msg` 已存在；不复制脚本、不安装远端 Hook。会修改仓库本地 Git 配置。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    hook_dir = Path(root) / ".githooks"
    required = [hook_dir / "pre-commit", hook_dir / "commit-msg"]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
    if missing:
        return {"ok": False, "error": f"缺少 Hook wrapper: {', '.join(missing)}"}
    current = _run_fixed(["git", "config", "--local", "--get", "core.hooksPath"], cwd=root)
    if current.returncode == 0 and current.stdout.strip() not in {".githooks", ""}:
        return {"ok": False, "error": f"当前 core.hooksPath={current.stdout.strip()!r}；拒绝覆盖既有设置"}
    result = _run_fixed(["git", "config", "--local", "core.hooksPath", ".githooks"], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "core.hooksPath": ".githooks", "error": None if result.returncode == 0 else "git config failed"}


def stage_repository_paths(repo_path: str, paths: list[str]) -> dict[str, Any]:
    """在明确用户授权且 Codex writes approval 后，只将显式列出的普通仓库相对文件路径加入 Git index。允许精确的 tracked deletion；拒绝绝对路径、穿越、symlink、目录、重复路径及已有 staged changes。写入后核验 staged path 集合与请求完全相同；不 stage 清单外内容。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "staged_paths": [], "error": error}
    parsed, error = _requested_repo_paths(paths)
    if error:
        return {"ok": False, "staged_paths": [], "error": error}
    before, error = _staged_path_names(root)
    if error:
        return {"ok": False, "staged_paths": [], "error": error}
    if before:
        return {"ok": False, "staged_paths": before, "error": "index 已有 staged changes；先由用户决定如何处理"}
    for rel in parsed:
        error = _validate_stage_path(root, rel)
        if error:
            return {"ok": False, "staged_paths": [], "error": error}
    args = ["git", "add", "--", *(f":(literal){rel.as_posix()}" for rel in parsed)]
    added = _run_fixed(args, cwd=root)
    staged, read_error = _staged_path_names(root)
    expected = {rel.as_posix() for rel in parsed}
    actual = set(staged or [])
    if added.returncode != 0 or read_error or actual != expected:
        return {"ok": False, "staged_paths": staged or [], "error": read_error or "git add 失败或 staged paths 与显式请求不一致"}
    return {"ok": True, "repo_path": root, "staged_paths": sorted(actual)}


def commit_repository_changes(repo_path: str, message: str, expected_paths: list[str]) -> dict[str, Any]:
    """在明确用户授权且 Codex writes approval 后提交已暂存内容。要求 staged paths 与 expected_paths 完全相等、提交信息通过既有策略、`git diff --cached --check` 通过。运行固定 `git commit -m <message>`，不使用绕过 Hook 的参数；返回提交 OID、实际消息、提交路径及提交后的工作区状态。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    expected, error = _requested_repo_paths(expected_paths)
    if error:
        return {"ok": False, "error": error}
    staged, error = _staged_path_names(root)
    if error:
        return {"ok": False, "error": error}
    wanted = {rel.as_posix() for rel in expected}
    actual = set(staged)
    if actual != wanted:
        return {"ok": False, "staged_paths": sorted(actual), "error": "staged paths 与 expected_paths 不完全一致；未提交"}
    message_check = check_commit_message(message)
    if not message_check["passed"]:
        return {"ok": False, "error": "提交信息未通过既有策略", "message_check": message_check}
    whitespace = _run_fixed(["git", "diff", "--cached", "--check"], cwd=root)
    if whitespace.returncode != 0:
        return {"ok": False, "error": "git diff --cached --check 未通过", "diagnostics": whitespace.stdout.splitlines()}
    committed = _run_fixed(["git", "commit", "-m", message], cwd=root)
    if committed.returncode != 0:
        return {"ok": False, "error": f"git commit failed (exit {committed.returncode}); no hook bypass was attempted"}
    oid = _run_fixed(["git", "rev-parse", "--verify", "HEAD"], cwd=root)
    actual_message = _run_fixed(["git", "log", "-1", "--format=%B"], cwd=root)
    commit_paths = _run_fixed(["git", "diff-tree", "--root", "--no-commit-id", "--name-only", "--no-renames", "-r", "-z", "HEAD"], cwd=root)
    status = _run_fixed(["git", "status", "--short", "--branch", "--untracked-files=all"], cwd=root)
    if any(result.returncode != 0 for result in (oid, actual_message, commit_paths, status)):
        return {"ok": False, "committed": True, "error": "提交已成功，但提交元数据或后续工作区状态无法完整回读"}
    return {
        "ok": True,
        "committed": True,
        "commit_oid": oid.stdout.strip(),
        "message": actual_message.stdout.rstrip("\n"),
        "paths": sorted(path for path in commit_paths.stdout.split("\0") if path),
        "status": status.stdout.splitlines(),
    }


def list_github_issue_labels(repo_path: str, repo: str | None = None) -> dict[str, Any]:
    """只读列出指定 GitHub 仓库现有 Issue labels，供 Issue 创建前复用仓库标签。最多读取 gh label list 的 100 个结果。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "labels": [], "error": error}
    resolved, error = _resolve_repo(repo, cwd=root)
    if error:
        return {"ok": False, "labels": [], "error": error}
    result = _run_fixed(["gh", "label", "list", "--repo", resolved, "--limit", "100", "--json", "name,description,color"], cwd=root)
    if result.returncode != 0:
        return {"ok": False, "repo": resolved, "labels": [], "error": f"gh label list failed (exit {result.returncode})"}
    try:
        labels = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "repo": resolved, "labels": [], "error": "gh label list returned invalid JSON"}
    if not isinstance(labels, list):
        return {"ok": False, "repo": resolved, "labels": [], "error": "gh label list returned a non-list"}
    return {"ok": True, "repo": resolved, "labels": labels, "limit": 100}


def create_github_issue(repo_path: str, repo: str, title: str, body: str, labels: list[str]) -> dict[str, Any]:
    """在明确授权后于指定仓库创建并核验 Issue。要求 body 完整、至少一个已存在的工作类型 label；默认指派 `@me`。使用安全临时 body-file，不将 Markdown 正文放入命令参数。副作用：创建 GitHub Issue。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "created": False, "error": error}
    if not REPO_PATTERN.fullmatch(repo):
        return {"ok": False, "created": False, "error": "repo 必须为 owner/repo"}
    if not title.strip() or not body.strip() or not labels or any(not label.strip() for label in labels):
        return {"ok": False, "created": False, "error": "title/body 和至少一个非空 label 均为必填"}
    label_result = _run_fixed(["gh", "label", "list", "--repo", repo, "--limit", "100", "--json", "name"], cwd=root)
    if label_result.returncode != 0:
        return {"ok": False, "created": False, "error": "无法读取仓库 labels；为避免猜标签而停止"}
    try:
        available = {item["name"] for item in json.loads(label_result.stdout) if isinstance(item, dict) and isinstance(item.get("name"), str)}
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "created": False, "error": "仓库 labels 响应无效"}
    missing = [label for label in labels if label not in available]
    if missing:
        return {"ok": False, "created": False, "error": f"指定 label 不存在或不在前 100 项中: {missing!r}"}
    login, error = _gh_current_login(root)
    if error:
        return {"ok": False, "created": False, "error": error}
    temporary, body_file = _temporary_body_file(body)
    try:
        args = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body-file", body_file, "--assignee", "@me"]
        for label in labels:
            args.extend(["--label", label])
        created = _run_fixed(args, cwd=root)
        if created.returncode != 0:
            return {"ok": False, "created": False, "error": f"gh issue create failed (exit {created.returncode})"}
    finally:
        temporary.cleanup()
    match = re.search(r"/issues/(\d+)\s*$", created.stdout.strip())
    if not match:
        return {"ok": False, "created": True, "error": "Issue 创建命令返回成功，但无法解析 Issue URL；请人工回读，不要重复创建"}
    number = int(match.group(1))
    details, error = _gh_object(["gh", "issue", "view", str(number), "--repo", repo, "--json", "number,title,state,labels,assignees"], root)
    if error:
        return {"ok": False, "created": True, "issue_number": number, "error": error}
    label_names = {item.get("name") for item in details.get("labels", []) if isinstance(item, dict)}
    assignees = {item.get("login") for item in details.get("assignees", []) if isinstance(item, dict)}
    verified = details.get("state") == "OPEN" and set(labels).issubset(label_names) and login in assignees
    return {"ok": verified, "created": True, "repo": repo, "issue": details, "error": None if verified else "Issue 已创建，但开放状态、labels 或 @me assignee 回读校验失败"}


def push_issue_branch_to_origin(repo_path: str, repo: str, branch_name: str, issue_number: int) -> dict[str, Any]:
    """在明确推送授权后执行固定的 `git push origin <branch_name>`。要求当前本地分支匹配、工作区干净，且指定 GitHub Issue 开放、带 label 并指派给当前 gh 用户。副作用：向 origin 更新该分支；不强推。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if not REPO_PATTERN.fullmatch(repo) or issue_number <= 0 or not _valid_remote_branch(branch_name):
        return {"ok": False, "error": "repo/issue_number/branch_name 参数无效"}
    if branch_name in {"main", "master"} or _current_branch(root) != branch_name:
        return {"ok": False, "error": "只允许推送当前检出的非主分支"}
    status = _run_fixed(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)
    if status.returncode != 0 or status.stdout.strip():
        return {"ok": False, "error": "工作区必须完全干净才能推送"}
    issue, error = _gh_object(["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "number,state,labels,assignees"], root)
    if error:
        return {"ok": False, "error": error}
    login, error = _gh_current_login(root)
    if error:
        return {"ok": False, "error": error}
    labels = issue.get("labels") or []
    assignees = issue.get("assignees") or []
    if issue.get("state") != "OPEN" or not labels or login not in {item.get("login") for item in assignees if isinstance(item, dict)}:
        return {"ok": False, "error": "Issue 必须开放、具备至少一个 label 并指派给当前 gh 用户"}
    result = _run_fixed(["git", "push", "origin", branch_name], cwd=root)
    return {"ok": result.returncode == 0, "repo_path": root, "repo": repo, "branch_name": branch_name, "issue_number": issue_number, "error": None if result.returncode == 0 else "git push origin failed; no force push was attempted"}


def create_github_pull_request(repo_path: str, repo: str, title: str, body: str, base_branch: str, head_branch: str, issue_number: int) -> dict[str, Any]:
    """在明确授权后创建并回读关联 PR。要求显式 repo/base/head/open Issue，body 含 Closes/Fixes/Resolves #N；PR 默认指派 `@me`。使用临时 body-file，不内联 Markdown。副作用：创建开放 PR。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "created": False, "error": error}
    if not REPO_PATTERN.fullmatch(repo) or issue_number <= 0 or not title.strip() or not body.strip():
        return {"ok": False, "created": False, "error": "repo/title/body/issue_number 参数无效"}
    if not _valid_remote_branch(base_branch) or not _valid_remote_branch(head_branch) or base_branch == head_branch:
        return {"ok": False, "created": False, "error": "base_branch/head_branch 无效或相同"}
    ref_pattern = re.compile(rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\s*{issue_number}\b", re.IGNORECASE)
    if not ref_pattern.search(body):
        return {"ok": False, "created": False, "error": f"PR body 必须包含 Closes/Fixes/Resolves #{issue_number}"}
    issue, error = _gh_object(["gh", "issue", "view", str(issue_number), "--repo", repo, "--json", "number,state"], root)
    if error or issue.get("state") != "OPEN":
        return {"ok": False, "created": False, "error": error or "Issue 必须处于 OPEN 状态"}
    exists = _run_fixed(["git", "show-ref", "--verify", f"refs/heads/{head_branch}"], cwd=root)
    if exists.returncode != 0:
        return {"ok": False, "created": False, "error": "本地 head_branch 不存在；先完成本地验证和推送"}
    login, error = _gh_current_login(root)
    if error:
        return {"ok": False, "created": False, "error": error}
    temporary, body_file = _temporary_body_file(body)
    try:
        created = _run_fixed(["gh", "pr", "create", "--repo", repo, "--title", title, "--body-file", body_file,
                              "--base", base_branch, "--head", head_branch, "--assignee", "@me"], cwd=root)
        if created.returncode != 0:
            return {"ok": False, "created": False, "error": f"gh pr create failed (exit {created.returncode})"}
    finally:
        temporary.cleanup()
    match = re.search(r"/pull/(\d+)\s*$", created.stdout.strip())
    if not match:
        return {"ok": False, "created": True, "error": "PR 创建命令返回成功，但无法解析 PR URL；请人工回读，不要重复创建"}
    number = int(match.group(1))
    details, error = _gh_object(["gh", "pr", "view", str(number), "--repo", repo,
        "--json", "number,title,state,baseRefName,headRefName,body,assignees"], root)
    if error:
        return {"ok": False, "created": True, "pr_number": number, "error": error}
    assignees = {item.get("login") for item in details.get("assignees", []) if isinstance(item, dict)}
    verified = (details.get("state") == "OPEN" and details.get("baseRefName") == base_branch and
                details.get("headRefName") == head_branch and login in assignees and
                ref_pattern.search(details.get("body") or "") is not None)
    return {"ok": verified, "created": True, "repo": repo, "pull_request": details,
            "error": None if verified else "PR 已创建，但 state/base/head/Issue 关联/assignee 回读校验失败"}


def merge_github_pull_request(repo_path: str, repo: str, pr_number: int, merge_method: Literal["squash", "merge", "rebase"]) -> dict[str, Any]:
    """在明确授权合并后运行固定 `gh pr merge <number> --<merge_method>`，先核验 PR OPEN/MERGEABLE 和 required checks 全部通过。base 为 main 时只允许 squash；不使用 --admin、--auto、--delete-branch。副作用：远端合并并关闭 PR。成功执行合并命令后返回合并前的 `pre_merge_head_oid`，供后续本地分支清理核验。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if not REPO_PATTERN.fullmatch(repo) or pr_number <= 0:
        return {"ok": False, "error": "repo/pr_number 参数无效"}
    pr, error = _gh_object(["gh", "pr", "view", str(pr_number), "--repo", repo,
        "--json", "number,state,baseRefName,headRefName,mergeable,reviewDecision,headRefOid"], root)
    if error:
        return {"ok": False, "error": error}
    if pr.get("state") != "OPEN" or pr.get("mergeable") != "MERGEABLE":
        return {"ok": False, "error": "PR 必须为 OPEN 且 mergeable=MERGEABLE"}
    if pr.get("baseRefName") == "main" and merge_method != "squash":
        return {"ok": False, "error": "目标 base 为 main，按策略只能 squash merge"}
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        return {"ok": False, "error": "PR 有 changes requested review"}
    checks, error = _gh_object(["gh", "pr", "checks", str(pr_number), "--repo", repo,
        "--required", "--json", "name,bucket"], root)
    if error:
        return {"ok": False, "error": error}
    if not isinstance(checks, list) or any(item.get("bucket") != "pass" for item in checks if isinstance(item, dict)):
        return {"ok": False, "error": "required checks 未全部通过或响应格式无效", "checks": checks}
    if any(not isinstance(item, dict) for item in checks):
        return {"ok": False, "error": "required checks 响应格式无效", "checks": checks}
    result = _run_fixed(["gh", "pr", "merge", str(pr_number), f"--{merge_method}", "--repo", repo], cwd=root)
    if result.returncode != 0:
        return {"ok": False, "error": f"gh pr merge failed (exit {result.returncode}); no admin/auto fallback was attempted"}
    final, error = _gh_object(["gh", "pr", "view", str(pr_number), "--repo", repo,
        "--json", "number,state,mergedAt,baseRefName,headRefName,mergeCommit"], root)
    verified = not error and final.get("state") == "MERGED" and final.get("baseRefName") == pr.get("baseRefName")
    return {"ok": verified, "merged": verified, "repo": repo, "pull_request": final,
            "pre_merge_head_oid": pr.get("headRefOid"),
            "error": error or (None if verified else "merge command succeeded but PR merged state/base could not be verified")}


def push_fork_main_fast_forward(repo_path: str, repo: str) -> dict[str, Any]:
    """在明确授权后仅将已确认 Fork 的本地 main 快进推送为 origin/main。要求 GitHub parent 非空、upstream/main 是本地 main 的祖先、当前检出 main 且工作区完全干净。副作用：更新个人 Fork 的 origin/main；不强推。需要 Codex writes approval。"""
    root, error = _validated_repo_path(repo_path)
    if error:
        return {"ok": False, "error": error}
    if not REPO_PATTERN.fullmatch(repo):
        return {"ok": False, "error": "repo 必须为 owner/repo"}
    fork, error = _gh_object(["gh", "repo", "view", repo, "--json", "parent,defaultBranchRef"], root)
    if error or not fork.get("parent"):
        return {"ok": False, "error": error or "目标不是 GitHub Fork"}
    default_branch = (fork.get("defaultBranchRef") or {}).get("name")
    if default_branch != "main" or _current_branch(root) != "main":
        return {"ok": False, "error": "只支持默认分支为 main 且当前检出 main 的 Fork 镜像同步"}
    status = _run_fixed(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root)
    if status.returncode != 0 or status.stdout.strip():
        return {"ok": False, "error": "main 工作区必须完全干净"}
    remotes = _run_fixed(["git", "remote"], cwd=root)
    if remotes.returncode != 0 or not {"upstream", "origin"}.issubset(remotes.stdout.splitlines()):
        return {"ok": False, "error": "必须预先配置 upstream 和 origin remotes"}
    ancestor = _run_fixed(["git", "merge-base", "--is-ancestor", "upstream/main", "main"], cwd=root)
    if ancestor.returncode != 0:
        return {"ok": False, "error": "upstream/main 尚未快进合入本地 main"}
    pushed = _run_fixed(["git", "push", "origin", "main"], cwd=root)
    return {"ok": pushed.returncode == 0, "repo_path": root, "repo": repo, "branch": "main", "error": None if pushed.returncode == 0 else "git push origin main 失败；未强推"}
