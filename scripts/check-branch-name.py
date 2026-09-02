#!/usr/bin/env python3
"""在 Git push 前检查分支名中的特定产品名称。

该脚本可直接作为 Git ``pre-push`` 检查器调用，也可以手动传入一个或多个
分支名称进行检查。脚本只依赖 Python 标准库和 Git 本身，不依赖任何特定
Code Agent 的运行时或配置格式。

用法:
    python3 check-branch-name.py feat/add-validation
    python3 check-branch-name.py --pre-push origin <远端 URL>

退出码:
    0  所有待推送分支名称均通过检查
    1  分支名称命中禁止名称
    2  参数、Git 状态或 pre-push 输入无效
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from typing import TextIO


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


def find_forbidden_names(branch_name: str) -> tuple[str, ...]:
    """返回分支名中命中的禁止名称，大小写不敏感且去重。"""
    matches = (match.group(0).lower() for match in FORBIDDEN_AGENT_NAME_PATTERN.finditer(branch_name))
    return tuple(dict.fromkeys(matches))


def branch_name_from_ref(ref: str) -> str | None:
    """从 Git ref 中提取 heads 分支名；其他 ref 不参与检查。"""
    prefix = "refs/heads/"
    if not ref.startswith(prefix):
        return None
    return ref[len(prefix) :]


def is_zero_sha(sha: str) -> bool:
    """判断 pre-push 输入中的 ref 是否表示删除远端分支。"""
    return bool(sha) and not sha.strip("0")


def read_pre_push_branches(lines: Iterable[str]) -> tuple[list[tuple[str, str]], str | None]:
    """解析 Git pre-push 标准输入。

    返回 ``(待检查分支, 错误信息)``。每个分支项为 ``(来源, 分支名)``，来源
    用于在错误信息中区分本地 ref 和远端 ref。
    """
    branches: list[tuple[str, str]] = []

    for line_number, line in enumerate(lines, start=1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 4:
            return [], f"pre-push 输入第 {line_number} 行应包含 4 个字段"

        local_ref, local_sha, remote_ref, _remote_sha = fields

        # 删除远端分支时 local_sha 为全零值，没有新的 patch 需要检查。
        if is_zero_sha(local_sha):
            continue

        local_branch = branch_name_from_ref(local_ref)
        if local_branch:
            branches.append(("本地", local_branch))

        # 检查目标远端分支，防止通过 refspec 将合规的本地分支推成违规的
        # GitHub 分支名。
        remote_branch = branch_name_from_ref(remote_ref)
        if remote_branch and ("远端", remote_branch) not in branches:
            branches.append(("远端", remote_branch))

    return branches, None


def report_violations(
    branches: Iterable[tuple[str, str]],
    *,
    error_stream: TextIO,
) -> int:
    """报告违规分支并返回适用于 pre-push 的退出码。"""
    violations: list[tuple[str, str, tuple[str, ...]]] = []
    seen: set[tuple[str, str]] = set()

    for source, branch_name in branches:
        item = (source, branch_name)
        if item in seen:
            continue
        seen.add(item)

        matches = find_forbidden_names(branch_name)
        if matches:
            violations.append((source, branch_name, matches))

    if not violations:
        return 0

    print("错误: 已阻止 Git push。分支名称包含禁止的产品名：", file=error_stream)
    for source, branch_name, matches in violations:
        print(
            f"  - {source}分支 {branch_name!r} 命中: {', '.join(matches)}",
            file=error_stream,
        )
    print("请重命名分支后再推送。", file=error_stream)
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
        description="检查 Git 分支名称是否包含禁止的产品名",
    )
    parser.add_argument(
        "branches",
        nargs="*",
        metavar="BRANCH",
        help="直接检查的一个或多个分支名称；未提供时检查当前分支",
    )
    parser.add_argument(
        "--pre-push",
        action="store_true",
        help="解析 Git pre-push 标准输入；Git 传入的 remote 参数会被忽略",
    )
    return parser


def main(argv: list[str] | None = None, stdin: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_stream = stdin or sys.stdin

    if args.pre_push:
        branches, error = read_pre_push_branches(input_stream)
        if error:
            print(f"错误: {error}", file=sys.stderr)
            return 2
        return report_violations(branches, error_stream=sys.stderr)

    branch_names = args.branches
    if not branch_names:
        branch = current_branch()
        if not branch:
            print("错误: 无法确定当前 Git 分支（可能处于 detached HEAD）", file=sys.stderr)
            return 2
        branch_names = [branch]

    return report_violations(
        (("", branch_name) for branch_name in branch_names),
        error_stream=sys.stderr,
    )


if __name__ == "__main__":
    sys.exit(main())
