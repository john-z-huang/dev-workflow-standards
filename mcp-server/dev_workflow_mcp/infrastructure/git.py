"""Private Git ref, status, path and content helpers."""

import hashlib
from pathlib import Path, PurePosixPath

from ..policy import REMOTE_BRANCH_PATTERN
from .process import _run_fixed


def _current_branch(root: str) -> str | None:
    result = _run_fixed(["git", "branch", "--show-current"], cwd=root)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _valid_local_branch(root: str, name: str) -> str | None:
    result = _run_fixed(["git", "check-ref-format", "--branch", name], cwd=root)
    return None if result.returncode == 0 else "branch_name 不是有效的本地分支名"


def _valid_remote_branch(name: str) -> bool:
    return bool(name and REMOTE_BRANCH_PATTERN.fullmatch(name) and ".." not in name and "//" not in name)


def _absolute_new_path(path: str) -> tuple[str | None, str | None]:
    requested = Path(path).expanduser()
    if not requested.is_absolute() or ".." in requested.parts:
        return None, "路径必须是绝对路径且不能包含 '..' 路径段"
    try:
        parent = requested.parent.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "目标父目录不存在或无法解析"
    return str(parent / requested.name), None


def _same_git_common_dir(source: str, target: str) -> bool:
    args = ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
    left = _run_fixed(args, cwd=source)
    right = _run_fixed(args, cwd=target)
    return left.returncode == 0 and right.returncode == 0 and left.stdout.strip() == right.stdout.strip()


def _safe_relative_path(value: str) -> PurePosixPath | None:
    if not value or "\\" in value or value.startswith("/"):
        return None
    path = PurePosixPath(value)
    if path.as_posix() != value or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if ".git" in path.parts:
        return None
    return path


def _sha256(path: Path) -> tuple[str | None, int | None, str | None]:
    try:
        with path.open("rb") as stream:
            digest = hashlib.sha256()
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size, None
    except OSError:
        return None, None, "文件无法读取"


def _require_clean_worktree(cwd: str) -> str | None:
    result = _run_fixed(["git", "status", "--porcelain"], cwd=cwd)
    if result.returncode != 0:
        return "无法读取 Git 工作区状态"
    if result.stdout.strip():
        return "工作区存在已暂存、未暂存或未跟踪内容"
    return None


def _requested_repo_paths(paths: list[str]) -> tuple[list[PurePosixPath] | None, str | None]:
    if not paths:
        return None, "paths 不能为空"
    parsed: list[PurePosixPath] = []
    seen: set[str] = set()
    for value in paths:
        rel = _safe_relative_path(value)
        if rel is None:
            return None, f"路径必须是安全、规范的仓库相对 POSIX 路径: {value!r}"
        if rel.as_posix() in seen:
            return None, f"路径重复: {value!r}"
        seen.add(rel.as_posix())
        parsed.append(rel)
    return parsed, None


def _validate_stage_path(root: str, rel: PurePosixPath) -> str | None:
    candidate = Path(root)
    for part in rel.parts[:-1]:
        candidate = candidate / part
        if candidate.is_symlink():
            return f"路径父目录不能是 symlink: {rel.as_posix()}"
        if candidate.exists() and not candidate.is_dir():
            return f"路径父组件不是目录: {rel.as_posix()}"
    candidate = candidate / rel.parts[-1]
    if candidate.is_symlink():
        return f"不能暂存 symlink: {rel.as_posix()}"
    if candidate.exists() and not candidate.is_file():
        return f"只能暂存普通文件或 tracked deletion: {rel.as_posix()}"
    if not candidate.exists():
        tracked = _run_fixed(["git", "ls-files", "--error-unmatch", "--", f":(literal){rel.as_posix()}"], cwd=root)
        if tracked.returncode != 0:
            return f"不存在的路径不是 tracked deletion: {rel.as_posix()}"
    return None


def _staged_path_names(root: str) -> tuple[list[str] | None, str | None]:
    result = _run_fixed(["git", "diff", "--cached", "--name-only", "--no-renames", "-z"], cwd=root)
    if result.returncode != 0:
        return None, "无法读取 staged paths"
    return [name for name in result.stdout.split("\0") if name], None
