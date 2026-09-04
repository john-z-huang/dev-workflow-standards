#!/usr/bin/env python3
"""提交信息检查器测试。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-commit-message.py"
PYTHON = sys.executable


def run_checker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


class CheckCommitMessageTests(unittest.TestCase):
    def test_accepts_chinese_commit_message(self) -> None:
        result = run_checker("--message", "feat: 增加输入校验")
        self.assertEqual(result.returncode, 0)

    def test_rejects_commit_message_without_chinese_subject(self) -> None:
        result = run_checker("--message", "feat: add validation")
        self.assertEqual(result.returncode, 1)
        self.assertIn("必须包含中文", result.stderr)

    def test_rejects_commit_message_without_type_prefix(self) -> None:
        result = run_checker("--message", "增加输入校验")
        self.assertEqual(result.returncode, 1)
        self.assertIn("类型前缀", result.stderr)

    def test_rejects_attribution_statement(self) -> None:
        result = run_checker(
            "--message",
            "feat: 增加输入校验\n\nCo-Authored-By: Example <example@example.com>",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("署名或生成声明", result.stderr)

    def test_ignores_comment_lines_from_commit_template(self) -> None:
        result = run_checker(
            "--message",
            "feat: 增加输入校验\n# Generated with Example\n",
        )
        self.assertEqual(result.returncode, 0)

    def test_accepts_commit_message_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            message_file = Path(directory) / "COMMIT_EDITMSG"
            message_file.write_text("docs: 更新工作流说明\n", encoding="utf-8")
            result = run_checker(str(message_file))
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
