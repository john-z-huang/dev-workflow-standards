"""Repository-root path validation and scoped command helpers."""

from pathlib import Path

from .process import _run_fixed


def _validated_repo_path(repo_path: str) -> tuple[str | None, str | None]:
    requested = Path(repo_path).expanduser()
    if not requested.is_absolute() or ".." in requested.parts:
        return None, "repo_path 必须是绝对路径且不能包含 '..' 路径段"
    try:
        root = requested.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "repo_path 不存在或无法解析"
    if not root.is_dir():
        return None, "repo_path 必须指向 Git 仓库目录"
    result = _run_fixed(["git", "rev-parse", "--show-toplevel"], cwd=str(root))
    if result.returncode != 0:
        return None, "repo_path 不是可访问的 Git 仓库或 worktree"
    try:
        git_root = Path(result.stdout.strip()).resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "无法解析 Git 仓库根目录"
    if git_root != root:
        return None, f"repo_path 必须是 Git 仓库根目录：{git_root}"
    return str(root), None


def _run_repo(repo_path: str, args: list[str]):
    root, error = _validated_repo_path(repo_path)
    if error:
        return None, None, error
    return _run_fixed(args, cwd=root), root, None
