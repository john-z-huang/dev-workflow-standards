#!/usr/bin/env python3
"""检查 Git 提交信息的格式、语言和署名约束。

该脚本可作为 ``commit-msg`` hook 使用，也可以通过 ``--message`` 直接检查
文本。提交主题必须使用 ``<type>: 中文说明`` 格式，并且禁止明确违反规范的
署名/生成声明；是否真正属于一个独立功能模块仍由人工审查。

用法:
    python3 check-commit-message.py .git/COMMIT_EDITMSG
    python3 check-commit-message.py --message "feat: 增加输入校验"

退出码:
    0  提交信息通过检查
    1  提交信息违反规范
    2  参数错误或无法读取提交信息
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TextIO


CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
SUBJECT_PATTERN = re.compile(
    r"^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$"
)
ATTRIBUTION_PATTERN = re.compile(
    r"(?:generated\s+(?:with|by)|created\s+with|assisted\s+by|"
    r"authored\s+by|co-?authored-?by)",
    re.IGNORECASE,
)


def visible_lines(message: str) -> list[str]:
    """移除 Git 提交模板中的注释行。"""
    return [line for line in message.splitlines() if not line.lstrip().startswith("#")]


def validate_message(message: str) -> tuple[str, ...]:
    """返回提交信息违反的策略项。"""
    lines = visible_lines(message)
    subject = next((line.strip() for line in lines if line.strip()), "")
    errors: list[str] = []

    if not subject:
        errors.append("提交主题不能为空")
    else:
        if not SUBJECT_PATTERN.fullmatch(subject):
            errors.append(
                "提交主题必须使用允许的类型前缀和格式："
                "<type>: 中文说明（type 可为 feat/fix/docs/refactor/test/chore/perf/build/ci）"
            )
        if not CHINESE_PATTERN.search(subject):
            errors.append("提交主题必须包含中文说明")

    attribution_match = ATTRIBUTION_PATTERN.search("\n".join(lines))
    if attribution_match:
        errors.append(f"禁止包含工具署名或生成声明: {attribution_match.group(0)}")

    return tuple(errors)


def report_errors(errors: tuple[str, ...], *, error_stream: TextIO) -> int:
    if not errors:
        return 0
    print("错误: 已阻止提交，提交信息不符合规范：", file=error_stream)
    for error in errors:
        print(f"  - {error}", file=error_stream)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 Git 提交信息的格式、语言和署名约束")
    parser.add_argument(
        "message_file",
        nargs="?",
        help="commit-msg hook 传入的提交信息文件",
    )
    parser.add_argument("--message", help="直接检查的提交信息文本")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.message is not None and args.message_file is not None:
        print("错误: --message 不能与提交信息文件同时使用", file=sys.stderr)
        return 2
    if args.message is None and args.message_file is None:
        print("错误: 请提供提交信息文件或 --message", file=sys.stderr)
        return 2

    if args.message is not None:
        message = args.message
    else:
        try:
            message = Path(args.message_file).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            print(f"错误: 无法读取提交信息文件: {error}", file=sys.stderr)
            return 2

    return report_errors(validate_message(message), error_stream=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
