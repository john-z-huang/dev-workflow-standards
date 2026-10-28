"""原子创建本地分支并将当前 worktree 的 HEAD 指向该分支。"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

from ..infrastructure.paths import _validated_repo_path
from ..policy import branch_errors

_HEX_OID = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_REDIRECTING_GIT_ENV = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
)
_TRANSACTION = "start\ncreate refs/heads/{branch} {oid}\noption no-deref\nsymref-update HEAD refs/heads/{branch} oid {oid}\n{ending}\n"
_OPERATION_MARKERS = (
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "REBASE_HEAD",
    "BISECT_LOG",
    "rebase-apply",
    "rebase-merge",
    "sequencer",
)


class _GitFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _git(root: str, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "--no-lazy-fetch", *args], cwd=root, input=input_text, capture_output=True,
            text=True, encoding="utf-8", errors="strict", check=False,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
        )
    except UnicodeError as exc:
        raise _GitFailure("git_output_invalid", "Git 输出无法按 UTF-8 安全解码") from exc
    except OSError as exc:
        raise _GitFailure("git_unavailable", "无法启动 Git 或访问其工作目录") from exc


def _require_no_lazy_fetch_support(root: str) -> None:
    result = _git(root, "--version")
    if result.returncode != 0 or not result.stdout.startswith("git version "):
        raise _GitFailure("git_capability_unavailable", "Git 不支持禁用 lazy fetch 的必要选项")


def _path_from_git(root: str, path: str) -> Path:
    result = _git(root, "rev-parse", "--git-path", path)
    if result.returncode != 0 or not result.stdout.strip():
        raise _GitFailure("git_path_unavailable", "Git 无法解析仓库元数据路径")
    candidate = Path(result.stdout.rstrip("\r\n"))
    return candidate if candidate.is_absolute() else Path(root) / candidate


def _present(path: Path, *, unreadable_is_error: bool = False) -> bool:
    try:
        path.lstat()
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        if unreadable_is_error:
            raise _GitFailure("metadata_unreadable", "无法检查仓库元数据") from exc
        raise


def _check_worktree_state(root: str, branch_name: str) -> None:
    worktrees = _git(root, "worktree", "list", "--porcelain", "-z")
    if worktrees.returncode != 0:
        raise _GitFailure("worktree_state_unavailable", "无法核实 Git worktree 状态")
    expected_path = str(Path(root).resolve())
    records: list[list[str]] = [[]]
    for raw in worktrees.stdout.split("\0"):
        if not raw:
            if records[-1]:
                records.append([])
            continue
        records[-1].append(raw)
    current_found = False
    wanted_ref = f"refs/heads/{branch_name}"
    for record in records:
        path_item = next((item for item in record if item.startswith("worktree ")), None)
        if path_item is None:
            continue
        if path_item == f"worktree {expected_path}":
            current_found = True
            if any(item == "locked" or item.startswith("locked ") for item in record):
                raise _GitFailure("worktree_locked", "目标 worktree 已锁定")
        elif f"branch {wanted_ref}" in record:
            raise _GitFailure("branch_checked_out", "请求的分支已在其他 worktree 检出")
    if not current_found:
        raise _GitFailure("worktree_state_unavailable", "Git worktree 列表中找不到目标目录")

    unmerged = _git(root, "ls-files", "--unmerged", "-z")
    if unmerged.returncode != 0:
        raise _GitFailure("index_state_unavailable", "无法检查 index 中的未解决合并项")
    if unmerged.stdout:
        raise _GitFailure("unmerged_index", "index 含有未解决的合并项")

    for marker in _OPERATION_MARKERS:
        path = _path_from_git(root, marker)
        if _present(path, unreadable_is_error=True):
            raise _GitFailure("operation_in_progress", "merge、rebase、revert、cherry-pick、bisect 或 sequencer 操作仍在进行")

    for lock_name in ("HEAD.lock", "index.lock", f"refs/heads/{branch_name}.lock"):
        if _present(_path_from_git(root, lock_name), unreadable_is_error=True):
            raise _GitFailure("repository_locked", "相关 Git 锁文件已存在")


def _reference_transaction_hook(root: str) -> Path:
    configured = _git(root, "config", "--path", "--get", "core.hooksPath")
    if configured.returncode == 0:
        configured_path = configured.stdout.rstrip("\r\n")
        if not configured_path:
            raise _GitFailure("hook_path_invalid", "core.hooksPath 配置为空")
        hook_dir = Path(configured_path).expanduser()
        if not hook_dir.is_absolute():
            hook_dir = Path(root) / hook_dir
    elif configured.returncode == 1:
        hook_dir = _path_from_git(root, "hooks")
    else:
        raise _GitFailure("hook_path_unavailable", "无法读取 core.hooksPath 配置")

    hook = hook_dir / "reference-transaction"
    try:
        metadata = hook.lstat()
    except FileNotFoundError:
        return hook
    except OSError as exc:
        raise _GitFailure("hook_unreadable", "无法检查 reference-transaction hook 路径") from exc
    try:
        resolved = hook.resolve(strict=True)
        target = resolved.stat()
    except OSError as exc:
        raise _GitFailure("hook_unreadable", "无法检查 reference-transaction hook 目标") from exc
    if not stat.S_ISREG(target.st_mode):
        raise _GitFailure("hook_unreadable", "reference-transaction hook 不是普通文件")
    if os.access(resolved, os.X_OK):
        raise _GitFailure("reference_transaction_hook", "存在可执行的 reference-transaction hook")
    if stat.S_ISLNK(metadata.st_mode) and not resolved.exists():
        raise _GitFailure("hook_unreadable", "reference-transaction hook 符号链接无法解析")
    return hook


def _head_oid(root: str) -> str:
    result = _git(root, "rev-parse", "--verify", "--end-of-options", "HEAD")
    if result.returncode != 0:
        raise _GitFailure("head_unavailable", "HEAD 尚未创建或无效")
    oid = result.stdout.strip()
    if not _HEX_OID.fullmatch(oid):
        raise _GitFailure("head_oid_invalid", "Git 返回了无效的 HEAD 对象 ID")
    object_type = _git(root, "cat-file", "-t", oid)
    if object_type.returncode != 0 or object_type.stdout.strip() != "commit":
        raise _GitFailure("head_not_commit", "HEAD 必须直接指向 commit 对象")
    return oid.lower()


def _ensure_new_ref(root: str, branch_name: str) -> None:
    refs = _git(root, "for-each-ref", "--format=%(refname)", "refs/heads")
    if refs.returncode != 0:
        raise _GitFailure("branch_state_unavailable", "无法枚举本地分支引用")
    target = f"refs/heads/{branch_name}"
    for existing in refs.stdout.splitlines():
        if existing == target or existing.startswith(target + "/") or target.startswith(existing + "/"):
            raise _GitFailure("branch_exists", "请求的分支名与已有本地引用冲突")
    existence = _git(root, "show-ref", "--exists", target)
    if existence.returncode == 0:
        raise _GitFailure("branch_exists", "请求的本地引用已存在")
    if existence.returncode != 2:
        raise _GitFailure("branch_state_unavailable", "无法核实请求的分支引用")
    symbolic = _git(root, "symbolic-ref", "-q", target)
    if symbolic.returncode == 0:
        raise _GitFailure("branch_exists", "请求的分支名已是符号引用")
    if symbolic.returncode != 1:
        raise _GitFailure("branch_state_unavailable", "无法核实请求的分支引用")


def _result(
    *,
    ok: bool,
    created: bool | None,
    repo_path: str | None,
    branch_name: str,
    start_head_oid: str | None,
    error_code: str | None = None,
    error: str | None = None,
    needs_review: bool = False,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "created": created,
        "repo_path": repo_path,
        "branch_name": branch_name,
        "start_head_oid": start_head_oid,
        "error_code": error_code,
        "error": error,
        "needs_review": needs_review,
    }


def create_repository_branch(repo_path: str, branch_name: str, expected_head_oid: str | None = None) -> dict[str, Any]:
    """在捕获的 HEAD commit 上原子创建本地分支，并将当前 worktree 的 HEAD 指向新分支。

    使用单个 ``git update-ref --stdin`` 事务创建引用并更新 HEAD，保留脏工作区、暂存项和未跟踪文件。
    不 checkout 文件、不写 index、不运行 hook、不联网，也不选择其他基点。expected_head_oid 是唯一并发条件；
    若 HEAD 符号目标改变但 OID 相同，事务仍会接受。
    """
    root: str | None = None
    start_oid: str | None = None
    transaction_started = False
    transaction_completed = False
    redirecting = [name for name in _REDIRECTING_GIT_ENV if name in os.environ]
    redirecting.extend(name for name in os.environ if re.fullmatch(r"GIT_CONFIG_(?:KEY|VALUE)_\d+", name))
    if redirecting:
        return _result(ok=False, created=False, repo_path=None, branch_name=str(branch_name), start_head_oid=None,
                       error_code="git_environment_redirected", error="检测到可能重定向仓库、对象库或 index 的 Git 环境变量")
    try:
        root, path_error = _validated_repo_path(repo_path)
    except (OSError, UnicodeError, TypeError, ValueError):
        return _result(ok=False, created=False, repo_path=None, branch_name=str(branch_name), start_head_oid=None,
                       error_code="invalid_repo_path", error="无法安全解析 repo_path")
    if path_error:
        return _result(ok=False, created=False, repo_path=None, branch_name=branch_name, start_head_oid=None,
                       error_code="invalid_repo_path", error=path_error)
    assert root is not None
    if not isinstance(branch_name, str) or not branch_name:
        return _result(ok=False, created=False, repo_path=root, branch_name=str(branch_name), start_head_oid=None,
                       error_code="invalid_branch_name", error="branch_name 必须是非空字符串")
    if branch_name in {"main", "master"} or branch_errors(branch_name):
        return _result(ok=False, created=False, repo_path=root, branch_name=branch_name, start_head_oid=None,
                       error_code="branch_policy_rejected", error="branch_name 未通过本地分支策略")
    try:
        _require_no_lazy_fetch_support(root)
        name_check = _git(root, "check-ref-format", "--branch", branch_name)
        if name_check.returncode != 0:
            raise _GitFailure("invalid_branch_name", "branch_name 不是有效的本地分支名")
        _ensure_new_ref(root, branch_name)
        _check_worktree_state(root, branch_name)
        current_oid = _head_oid(root)
        start_oid = current_oid
        if expected_head_oid is not None:
            if not isinstance(expected_head_oid, str) or not expected_head_oid or not _HEX_OID.fullmatch(expected_head_oid):
                raise _GitFailure("invalid_expected_head_oid", "expected_head_oid 必须为 40 或 64 位十六进制对象 ID，或 null")
            if expected_head_oid.lower() != current_oid:
                raise _GitFailure("head_oid_mismatch", "当前 HEAD 与 expected_head_oid 不匹配")
        oid = current_oid

        # 某些 Git 版本在能力探测事务时可能调用 reference-transaction hook。
        _reference_transaction_hook(root)
        # 通过排队后 abort 的空事务探测命令语法，不 prepare 或提交引用。
        probe = _git(root, "update-ref", "--stdin", input_text=_TRANSACTION.format(branch=branch_name, oid=oid, ending="abort"))
        if probe.returncode != 0:
            raise _GitFailure("git_capability_unavailable", "当前 Git 不支持所需的原子引用事务")

        # 在唯一可能写入引用的事务前再次检查 hook。
        _reference_transaction_hook(root)
        transaction_started = True
        transaction = _git(root, "update-ref", "--stdin", input_text=_TRANSACTION.format(branch=branch_name, oid=oid, ending="prepare\ncommit"))
        if transaction.returncode != 0:
            return _result(ok=False, created=None, repo_path=root, branch_name=branch_name, start_head_oid=oid,
                           error_code="transaction_failed", error="引用事务失败；重试前请先核对仓库引用", needs_review=True)
        transaction_completed = True
        try:
            actual_head = _git(root, "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}")
            actual_branch = _git(root, "rev-parse", "--verify", "--end-of-options", f"refs/heads/{branch_name}^{{commit}}")
            actual_symref = _git(root, "symbolic-ref", "-q", "HEAD")
        except _GitFailure as exc:
            return _result(ok=False, created=True, repo_path=root, branch_name=branch_name, start_head_oid=oid,
                           error_code="post_commit_verification_failed", error=exc.message, needs_review=True)
        if (actual_head.returncode != 0 or actual_branch.returncode != 0 or actual_symref.returncode != 0
                or actual_head.stdout.strip().lower() != oid
                or actual_branch.stdout.strip().lower() != oid
                or actual_symref.stdout.strip() != f"refs/heads/{branch_name}"):
            return _result(ok=False, created=True, repo_path=root, branch_name=branch_name, start_head_oid=oid,
                           error_code="post_commit_verification_failed", error="事务已完成，但无法确认最终 HEAD 与分支引用", needs_review=True)
        return _result(ok=True, created=True, repo_path=root, branch_name=branch_name, start_head_oid=oid)
    except _GitFailure as exc:
        return _result(ok=False, created=True if transaction_completed else (None if transaction_started else False),
                       repo_path=root, branch_name=branch_name, start_head_oid=start_oid,
                       error_code="post_commit_verification_failed" if transaction_completed else ("transaction_failed" if transaction_started else exc.code),
                       error="引用事务已完成，但结果核验失败" if transaction_completed else ("引用事务可能已开始；重试前请先核对仓库引用" if transaction_started else exc.message),
                       needs_review=transaction_started or transaction_completed)
    except (OSError, UnicodeError, TypeError, ValueError):
        return _result(ok=False, created=True if transaction_completed else (None if transaction_started else False),
                       repo_path=root, branch_name=branch_name, start_head_oid=start_oid,
                       error_code="post_commit_verification_failed" if transaction_completed else ("transaction_failed" if transaction_started else "repository_state_unavailable"),
                       error="无法安全读取或更新仓库状态", needs_review=transaction_started or transaction_completed)
