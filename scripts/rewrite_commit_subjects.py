#!/usr/bin/env python3
"""Rewrite selected generic commit subjects while preserving message bodies.

The script reads one complete commit message from standard input and writes the
rewritten message to standard output. Already-prefixed and merge subjects pass
through unchanged; unknown unprefixed subjects fail.
"""

from __future__ import annotations

import re
import sys


SUBJECTS = {
    "添加基础校验脚本": "feat: 添加基础校验脚本",
    "修复文件路径解析": "fix: 修复文件路径解析",
    "更新开发说明文档": "docs: 更新开发说明文档",
    "整理模块结构": "refactor: 整理模块结构",
}

PREFIXED_SUBJECT = re.compile(
    r"^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$"
)
GITHUB_MERGE_SUBJECT_PREFIX = "Merge pull request"


def rewrite(message: str) -> str:
    """Replace the first unprefixed subject and preserve the rest of the message."""
    lines = message.splitlines(keepends=True)
    for index, line in enumerate(lines):
        subject = line.rstrip("\r\n")
        if not subject.strip() or subject.lstrip().startswith("#"):
            continue

        normalized_subject = subject.strip()
        if normalized_subject.startswith(GITHUB_MERGE_SUBJECT_PREFIX):
            return message

        replacement = SUBJECTS.get(normalized_subject)
        if replacement is None:
            if PREFIXED_SUBJECT.fullmatch(normalized_subject):
                return message
            raise SystemExit(f"未配置提交标题映射: {subject!r}")

        ending = line[len(subject) :]
        lines[index] = replacement + ending
        return "".join(lines)

    raise SystemExit("提交信息没有可用标题")


if __name__ == "__main__":
    sys.stdout.write(rewrite(sys.stdin.read()))
