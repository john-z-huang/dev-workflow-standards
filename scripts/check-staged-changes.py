#!/usr/bin/env python3
"""检查暂存区内容，并可选运行项目测试命令。

默认执行 ``git diff --cached --check``，阻止带有空白错误的提交。项目若要
在提交前运行测试，可通过 ``--test-command`` 传入一个以空格分隔的命令；命令
会使用参数列表执行，不经过 shell。

用法:
    python3 check-staged-changes.py
    python3 check-staged-changes.py --test-command "python3 -m unittest discover"

退出码:
    0  暂存区检查和可选测试通过
    1  检查或测试失败
    2  参数错误或 Git 命令执行失败
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def report_command_failure(
    label: str,
    result: subprocess.CompletedProcess[str],
    *,
    error_stream=sys.stderr,
) -> None:
    print(f"错误: {label}失败（退出码 {result.returncode}）", file=error_stream)
    details = result.stderr.strip() or result.stdout.strip()
    if details:
        print(details, file=error_stream)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="检查 Git 暂存区内容和可选测试")
    parser.add_argument(
        "--test-command",
        help="提交前运行的测试命令，使用 shlex 解析，不经过 shell",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    diff_check = run_command(["git", "diff", "--cached", "--check"])
    if diff_check.returncode != 0:
        report_command_failure("暂存区空白检查", diff_check)
        return 1

    if args.test_command:
        try:
            test_command = shlex.split(args.test_command)
        except ValueError as error:
            print(f"错误: 测试命令格式无效: {error}", file=sys.stderr)
            return 2
        if not test_command:
            print("错误: 测试命令不能为空", file=sys.stderr)
            return 2

        test_result = run_command(test_command)
        if test_result.returncode != 0:
            report_command_failure("测试命令", test_result)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
