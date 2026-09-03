#!/usr/bin/env python3
"""在 Git commit 前检查分支名称策略。

该脚本可直接作为 Git ``pre-commit`` 检查器调用，也可以手动传入一个或多个
分支名称进行检查。脚本检查根分支、类别前缀、ASCII/小写命名规则，以及禁止
的产品名称。脚本只依赖 Python 标准库和 Git 本身，不依赖任何特定 Code Agent
的运行时或配置格式。

用法:
    python3 check-branch-name.py feat/add-validation
    python3 check-branch-name.py --pre-commit

退出码:
    0  所有待提交分支名称均通过检查
    1  分支名称不符合策略
    2  参数或 Git 状态无效
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys


# 该列表是有意集中维护的；新增产品名时只需补充此处，正则会自动更新。
FORBIDDEN_AGENT_NAMES = (
    "codex",
    "claude",
    "antigravity",
    "opencode",
    "cursor",
    "copilot",
    "cline",
    "roo-code",
    "roo_code",
    "aider",
    "continue",
    "windsurf",
    "devin",
    "gemini",
    "cody",
    "junie",
    "kiro",
    "goose",
    "augment",
    "amazon-q",
    "amazon_q",
)

FORBIDDEN_AGENT_NAME_PATTERN = re.compile(
    "(?:" + "|".join(re.escape(name) for name in FORBIDDEN_AGENT_NAMES) + ")",
    re.IGNORECASE,
)

# main/master 是受保护的根分支，不要求带类别前缀；其他工作分支必须使用
# 文档中规定的类别前缀，并且每一级只允许小写字母、数字和连字符。
ROOT_BRANCH_NAMES = frozenset({"main", "master"})
WORK_BRANCH_PATTERN = re.compile(
    r"^(?:agent|feat|fix|docs|refactor)/"
    r"[a-z0-9]+(?:-[a-z0-9]+)*"
    r"(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*$"
)


def find_forbidden_names(branch_name: str) -> tuple[str, ...]:
    """返回分支名中命中的禁止名称，大小写不敏感且去重。"""
    matches = (match.group(0).lower() for match in FORBIDDEN_AGENT_NAME_PATTERN.finditer(branch_name))
    return tuple(dict.fromkeys(matches))


def find_branch_policy_errors(branch_name: str) -> tuple[str, ...]:
    """返回分支名称违反的策略项。"""
    errors: list[str] = []

    if branch_name not in ROOT_BRANCH_NAMES and not WORK_BRANCH_PATTERN.fullmatch(branch_name):
        errors.append("必须是 main/master，或使用允许的类别前缀和小写连字符格式")

    matches = find_forbidden_names(branch_name)
    if matches:
        errors.append(f"包含禁止的产品名: {', '.join(matches)}")

    return tuple(errors)


def report_violations(branch_names: list[str]) -> int:
    """报告违规分支并返回适用于 pre-commit 的退出码。"""
    violations: list[tuple[str, tuple[str, ...]]] = []

    for branch_name in dict.fromkeys(branch_names):
        errors = find_branch_policy_errors(branch_name)
        if errors:
            violations.append((branch_name, errors))

    if not violations:
        return 0

    print("错误: 已阻止 Git commit。分支名称不符合策略：", file=sys.stderr)
    for branch_name, errors in violations:
        print(f"  - 分支 {branch_name!r}: {'；'.join(errors)}", file=sys.stderr)
    print("请重命名分支后再提交。", file=sys.stderr)
    return 1


def current_branch() -> str | None:
    """获取当前分支名；detached HEAD 时返回 None。"""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    branch_name = result.stdout.strip()
    return branch_name or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查 Git commit 使用的分支名称是否符合策略",
    )
    parser.add_argument(
        "branches",
        nargs="*",
        metavar="BRANCH",
        help="直接检查的一个或多个分支名称；未提供时检查当前分支",
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="作为 Git pre-commit hook 检查当前分支",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.pre_commit and args.branches:
        print("错误: --pre-commit 不能与显式分支名称同时使用", file=sys.stderr)
        return 2

    branch_names = args.branches
    if not branch_names:
        branch = current_branch()
        if not branch:
            print("错误: 无法确定当前 Git 分支（可能处于 detached HEAD）", file=sys.stderr)
            return 2
        branch_names = [branch]

    return report_violations(branch_names)


if __name__ == "__main__":
    sys.exit(main())
