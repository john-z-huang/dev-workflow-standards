#!/usr/bin/env python3
"""历史提交标题重写脚本测试。"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "rewrite_weather_commit_subjects.py"
PYTHON = sys.executable


def run_rewriter(message: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SCRIPT)],
        input=message,
        capture_output=True,
        text=True,
        check=False,
    )


class RewriteWeatherCommitSubjectsTests(unittest.TestCase):
    def test_rewrites_legacy_subject_and_preserves_body(self) -> None:
        result = run_rewriter("添加十类气象数据 Python 处理脚本\n\n保留正文。\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout,
            "feat: 添加十类气象数据 Python 处理脚本\n\n保留正文。\n",
        )

    def test_leaves_prefixed_subject_unchanged(self) -> None:
        message = "docs: 更新工作流说明\n\n正文。\n"
        result = run_rewriter(message)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, message)

    def test_rejects_unknown_subject(self) -> None:
        result = run_rewriter("未配置标题\n")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("未配置提交标题映射", result.stderr)


if __name__ == "__main__":
    unittest.main()
