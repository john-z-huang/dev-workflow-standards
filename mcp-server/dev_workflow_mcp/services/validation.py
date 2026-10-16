"""Validation and local cleanup workflow use cases.

This module contains application logic only; MCP registration lives in tools/.
"""

from __future__ import annotations

import re
from typing import Any

from ..infrastructure.github_cli import _gh_api_json, _gh_pr_for_cleanup, _resolve_repo
from ..infrastructure.git import _require_clean_worktree
from ..infrastructure.paths import _run_repo, _validated_repo_path
from ..infrastructure.process import _run_fixed
from ..policy import ATTRIBUTION_PATTERN, CHINESE_PATTERN, LEGACY_SUBJECTS, OID_PATTERN, PREFIXED_SUBJECT, SUBJECT_PATTERN, branch_errors as _branch_errors



def check_branch_names(branch_names: list[str] | None = None, repo_path: str | None = None) -> dict[str, Any]:
    """检查一个或多个分支名；省略 branch_names 时检查当前仓库分支。

    只读取 git branch --show-current，不创建、切换、删除分支或安装 Hook。
    """
    if branch_names is None:
        if repo_path is None:
            return {"passed": False, "checks": [], "error": "repo_path 绝对路径为必填项，除非提供 branch_names"}
        result, _, path_error = _run_repo(repo_path, ["git", "branch", "--show-current"])
        if path_error:
            return {"passed": False, "checks": [], "error": path_error}
        if result.returncode != 0 or not result.stdout.strip():
            return {"passed": False, "checks": [], "error": "无法确定当前分支或当前处于 detached HEAD"}
        branch_names = [result.stdout.strip()]
    if not branch_names:
        return {"passed": False, "checks": [], "error": "至少提供一个分支名，或省略以检查当前分支"}
    checks = [
        {"branch_name": name, "passed": not (errors := _branch_errors(name)), "errors": errors}
        for name in branch_names
    ]
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def check_commit_message(message: str) -> dict[str, Any]:
    """检查提交信息标题、中文说明和禁止的工具署名；不读取或修改 Git 状态。"""
    lines = [line for line in message.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    subject = lines[0].strip() if lines else ""
    errors: list[str] = []
    if not subject:
        errors.append("提交主题不能为空")
    else:
        if not SUBJECT_PATTERN.fullmatch(subject):
            errors.append("提交主题必须使用允许的类型前缀和格式：<type>: 中文说明")
        if not CHINESE_PATTERN.search(subject):
            errors.append("提交主题必须包含中文说明")
    match = ATTRIBUTION_PATTERN.search("\n".join(lines))
    if match:
        errors.append(f"禁止包含工具署名或生成声明: {match.group(0)}")
    return {"passed": not errors, "subject": subject, "errors": errors}


def check_staged_changes(repo_path: str) -> dict[str, Any]:
    """运行固定的 `git diff --cached --check` 检查暂存区空白错误。

    只读 Git 暂存区；不运行测试、用户提供的命令或任何 shell 命令。
    """
    result, _, path_error = _run_repo(repo_path, ["git", "diff", "--cached", "--check"])
    if path_error:
        return {"passed": False, "diagnostics": [], "error": path_error}
    if result.returncode == 0:
        return {"passed": True, "diagnostics": []}
    return {
        "passed": False,
        "diagnostics": [line for line in result.stdout.splitlines() if line],
        "error": "git diff --cached --check 执行失败",
        "exit_code": result.returncode,
    }


def audit_issue_pr_policy(
    repo_path: str,
    repo: str | None = None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    expected_base: str | None = None,
    expected_head: str | None = None,
) -> dict[str, Any]:
    """只读审计 GitHub Issue/PR 开放状态、PR base/head 和关闭 Issue 的正文关联。

    通过固定的 gh repo view / gh api 只读请求；不创建、修改、关闭或合并 GitHub 资源。
    """
    root, path_error = _validated_repo_path(repo_path)
    if path_error:
        return {"passed": False, "errors": [path_error]}
    if issue_number is not None and issue_number <= 0:
        return {"passed": False, "errors": ["issue_number 必须为正数"]}
    if pr_number is not None and pr_number <= 0:
        return {"passed": False, "errors": ["pr_number 必须为正数"]}
    if issue_number is None and pr_number is None:
        return {"passed": False, "errors": ["至少提供正数 issue_number 或 pr_number"]}
    if expected_base is not None and pr_number is None:
        return {"passed": False, "errors": ["expected_base 需要与 pr_number 一起使用"]}
    if expected_head is not None and pr_number is None:
        return {"passed": False, "errors": ["expected_head 需要与 pr_number 一起使用"]}
    resolved_repo, error = _resolve_repo(repo, cwd=root)
    if error:
        return {"passed": False, "errors": [error]}

    errors: list[str] = []
    if issue_number is not None:
        issue, error = _gh_api_json(f"repos/{resolved_repo}/issues/{issue_number}", cwd=root)
        if error:
            return {"passed": False, "repo": resolved_repo, "errors": [error]}
        if issue.get("state") != "open":
            errors.append(f"Issue #{issue_number}: Issue 当前不是开放状态: {issue.get('state', '未知')}")
    if pr_number is not None:
        pr, error = _gh_api_json(f"repos/{resolved_repo}/pulls/{pr_number}", cwd=root)
        if error:
            return {"passed": False, "repo": resolved_repo, "errors": [error]}
        if pr.get("state") != "open":
            errors.append(f"PR #{pr_number}: PR 当前不是开放状态: {pr.get('state', '未知')}")
        base = (pr.get("base") or {}).get("ref")
        head = (pr.get("head") or {}).get("ref")
        if expected_base is not None and base != expected_base:
            errors.append(f"PR #{pr_number}: base 实际为 {base!r}，预期为 {expected_base!r}")
        if expected_head is not None and head != expected_head:
            errors.append(f"PR #{pr_number}: head 实际为 {head!r}，预期为 {expected_head!r}")
        if issue_number is not None:
            body = pr.get("body") or ""
            pattern = re.compile(
                rf"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\s*{issue_number}\b",
                re.IGNORECASE,
            )
            if not pattern.search(body):
                errors.append(f"PR #{pr_number}: 描述未关联 Closes/Fixes/Resolves #{issue_number}")
    return {"passed": not errors, "repo": resolved_repo, "errors": errors}


def cleanup_merged_pr_local_branch(
    repo_path: str,
    pr_number: int,
    repo: str | None = None,
    branch_name: str | None = None,
    merged_head_oid: str | None = None,
) -> dict[str, Any]:
    """在明确的人类授权后同步已合并 PR 的 base 并删除本地 head 分支。

    Invoke only after explicit user authorization; Codex write-approval must be enabled. The tool
    verifies a clean worktree and a MERGED PR, switches to the actual base,
    runs `git pull --ff-only origin <base>`, then uses `git branch -d`. It uses `git branch -D`
    only if the supplied pre-merge head OID exactly matches the local branch OID. It never deletes
    a remote branch or merges a PR. Side effects: local branch switch, fast-forward pull, local
    head branch deletion. The supplied OID must have been recorded before merge.
    """
    if pr_number <= 0:
        return {"completed": False, "actions": [], "error": "pr_number 必须为正数"}
    if merged_head_oid is not None and not OID_PATTERN.fullmatch(merged_head_oid):
        return {"completed": False, "actions": [], "error": "merged_head_oid 格式无效"}
    root, path_error = _validated_repo_path(repo_path)
    if path_error:
        return {"completed": False, "actions": [], "error": path_error}
    clean_error = _require_clean_worktree(root)
    if clean_error:
        return {"completed": False, "actions": [], "error": clean_error}
    info, error = _gh_pr_for_cleanup(pr_number, repo, cwd=root)
    if error:
        return {"completed": False, "actions": [], "error": error}
    if info.get("state") != "MERGED":
        return {"completed": False, "actions": [], "error": f"PR 尚未合并（状态: {info.get('state', '未知')}）"}
    base = info.get("baseRefName")
    head = info.get("headRefName")
    target_branch = branch_name or head
    if not base or not head:
        return {"completed": False, "actions": [], "error": "PR 缺少 base/head 分支信息"}
    if branch_name is not None and branch_name != head:
        return {"completed": False, "actions": [], "error": "指定 branch_name 与 PR head 不一致"}
    if target_branch == base:
        return {"completed": False, "actions": [], "error": "PR head 不能与 base 分支相同"}
    ref_check = _run_fixed(["git", "check-ref-format", "--branch", target_branch], cwd=root)
    if ref_check.returncode != 0:
        return {"completed": False, "actions": [], "error": "PR head 不是有效的本地分支名"}

    actions: list[str] = []
    switched = _run_fixed(["git", "switch", "--", base], cwd=root)
    if switched.returncode != 0:
        switched = _run_fixed(["git", "switch", "--track", f"origin/{base}"], cwd=root)
    if switched.returncode != 0:
        return {"completed": False, "actions": actions, "error": "无法切换到 PR base 分支"}
    actions.append(f"switched to {base}")
    pull = _run_fixed(["git", "pull", "--ff-only", "origin", base], cwd=root)
    if pull.returncode != 0:
        return {"completed": False, "actions": actions, "error": "git pull --ff-only 同步 base 失败"}
    actions.append(f"fast-forwarded origin/{base}")
    clean_error = _require_clean_worktree(root)
    if clean_error:
        return {"completed": False, "actions": actions, "error": clean_error}

    current = _run_fixed(["git", "branch", "--show-current"], cwd=root)
    if current.returncode != 0 or current.stdout.strip() == target_branch:
        return {"completed": False, "actions": actions, "error": "当前仍处于待删除分支，或无法确定当前分支"}
    deleted = _run_fixed(["git", "branch", "-d", "--", target_branch], cwd=root)
    if deleted.returncode == 0:
        actions.append(f"deleted local branch {target_branch} with -d")
        return {"completed": True, "repo": repo, "pr_number": pr_number, "actions": actions}
    if merged_head_oid is None:
        return {
            "completed": False,
            "actions": actions,
            "error": "普通删除失败；若为 squash merge，需提供合并前记录的 PR head SHA 后重试",
        }
    local_head = _run_fixed(["git", "rev-parse", "--verify", f"refs/heads/{target_branch}"], cwd=root)
    if local_head.returncode != 0 or local_head.stdout.strip().lower() != merged_head_oid.lower():
        return {"completed": False, "actions": actions, "error": "本地 head SHA 与合并前记录值不一致，拒绝强制删除"}
    forced = _run_fixed(["git", "branch", "-D", "--", target_branch], cwd=root)
    if forced.returncode != 0:
        return {"completed": False, "actions": actions, "error": "核验后强制删除本地分支失败"}
    actions.append(f"deleted local branch {target_branch} with -D after exact OID verification")
    return {"completed": True, "repo": repo, "pr_number": pr_number, "actions": actions}


def rewrite_legacy_commit_message(message: str) -> dict[str, str]:
    """将已配置的旧天气项目提交标题映射为规范标题，供独立授权的 Git 历史过滤使用。

    只转换输入文本，不调用 Git、不改写提交历史。未知标题返回错误；GitHub 自动合并
    标题和已有规范标题保持原样，正文与换行保留。
    """
    lines = message.splitlines(keepends=True)
    for index, line in enumerate(lines):
        subject = line.rstrip("\r\n")
        if not subject.strip() or subject.lstrip().startswith("#"):
            continue
        normalized = subject.strip()
        if normalized.startswith("Merge pull request") or PREFIXED_SUBJECT.fullmatch(normalized):
            return {"rewritten_message": message, "changed": "false"}
        replacement = LEGACY_SUBJECTS.get(normalized)
        if replacement is None:
            return {"rewritten_message": "", "changed": "false", "error": f"未配置提交标题映射: {subject!r}"}
        lines[index] = replacement + line[len(subject):]
        return {"rewritten_message": "".join(lines), "changed": "true"}
    return {"rewritten_message": "", "changed": "false", "error": "提交信息没有可用标题"}\n