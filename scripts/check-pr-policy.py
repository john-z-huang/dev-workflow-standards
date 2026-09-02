#!/usr/bin/env python3
"""只读审计 GitHub Issue/PR 的工作流约束。

脚本通过 GitHub CLI 的 REST API 检查 Issue 是否开放、PR 是否开放、PR 的
base/head 是否符合预期，以及 PR 描述是否关联指定 Issue。它不创建、修改或
关闭任何 GitHub 资源。

用法:
    python3 check-pr-policy.py --repo owner/repo --issue 7
    python3 check-pr-policy.py --repo owner/repo --pr 42 --issue 7 \
        --expected-base main --expected-head feat/add-validation

退出码:
    0  所有请求的 Issue/PR 检查通过
    1  GitHub 资源存在但违反工作流策略
    2  参数错误
    3  gh 命令、网络或 JSON 响应失败
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any


ISSUE_REFERENCE_TEMPLATE = (
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\s*{issue}\b"
)


def run_gh_json(endpoint: str, *, error_stream=sys.stderr) -> dict[str, Any] | None:
    """调用 gh REST API；错误信息不回显命令输出，避免意外泄露敏感信息。"""
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"错误: gh API 请求失败（退出码 {result.returncode}）", file=error_stream)
        return None

    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("错误: gh API 返回了无效 JSON", file=error_stream)
        return None
    if not isinstance(value, dict):
        print("错误: gh API 返回的数据结构不是对象", file=error_stream)
        return None
    return value


def resolve_repo(*, error_stream=sys.stderr) -> str | None:
    """从当前 Git 仓库上下文解析 owner/repo。"""
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print("错误: 无法从当前目录确定 GitHub 仓库，请显式传入 --repo", file=error_stream)
        return None
    return result.stdout.strip()


def has_issue_closing_reference(body: str, issue_number: int) -> bool:
    """判断 PR 描述是否包含可关闭指定 Issue 的关键词。"""
    pattern = re.compile(
        ISSUE_REFERENCE_TEMPLATE.format(issue=re.escape(str(issue_number))),
        re.IGNORECASE,
    )
    return bool(pattern.search(body))


def validate_issue(issue: dict[str, Any]) -> tuple[str, ...]:
    """返回 Issue 状态违反的策略项。"""
    if issue.get("state") != "open":
        return (f"Issue 当前不是开放状态: {issue.get('state', '未知')}",)
    return ()


def validate_pr(
    pr: dict[str, Any],
    *,
    issue_number: int | None = None,
    expected_base: str | None = None,
    expected_head: str | None = None,
) -> tuple[str, ...]:
    """返回 PR 状态、拓扑和关联关系违反的策略项。"""
    errors: list[str] = []
    if pr.get("state") != "open":
        errors.append(f"PR 当前不是开放状态: {pr.get('state', '未知')}")

    base = pr.get("base", {}).get("ref")
    head = pr.get("head", {}).get("ref")
    if expected_base and base != expected_base:
        errors.append(f"PR base 不符合预期: 实际为 {base!r}，预期为 {expected_base!r}")
    if expected_head and head != expected_head:
        errors.append(f"PR head 不符合预期: 实际为 {head!r}，预期为 {expected_head!r}")

    if issue_number is not None and not has_issue_closing_reference(
        pr.get("body") or "", issue_number
    ):
        errors.append(f"PR 描述未关联 Closes/Fixes/Resolves #{issue_number}")

    return tuple(errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读审计 GitHub Issue/PR 工作流约束")
    parser.add_argument("--repo", help="GitHub 仓库，格式为 owner/repo；默认从当前目录解析")
    parser.add_argument("--issue", type=int, help="需要检查是否开放的 Issue 编号")
    parser.add_argument("--pr", type=int, help="需要检查的 Pull Request 编号")
    parser.add_argument("--expected-base", help="PR 预期 base 分支")
    parser.add_argument("--expected-head", help="PR 预期 head 分支")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.issue is None and args.pr is None:
        print("错误: 至少提供 --issue 或 --pr", file=sys.stderr)
        return 2
    if args.expected_base and args.pr is None:
        print("错误: --expected-base 需要与 --pr 一起使用", file=sys.stderr)
        return 2
    if args.expected_head and args.pr is None:
        print("错误: --expected-head 需要与 --pr 一起使用", file=sys.stderr)
        return 2

    repo = args.repo or resolve_repo()
    if not repo:
        return 3

    errors: list[str] = []
    if args.issue is not None:
        issue = run_gh_json(f"repos/{repo}/issues/{args.issue}")
        if issue is None:
            return 3
        errors.extend(f"Issue #{args.issue}: {error}" for error in validate_issue(issue))

    if args.pr is not None:
        pr = run_gh_json(f"repos/{repo}/pulls/{args.pr}")
        if pr is None:
            return 3
        errors.extend(
            f"PR #{args.pr}: {error}"
            for error in validate_pr(
                pr,
                issue_number=args.issue,
                expected_base=args.expected_base,
                expected_head=args.expected_head,
            )
        )

    if errors:
        print("错误: GitHub 工作流检查失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("GitHub 工作流检查通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
