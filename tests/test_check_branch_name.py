#!/usr/bin/env python3
"""分支名称 push 前检查器测试。"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-branch-name.py"
PYTHON = sys.executable


def run_checker(*args: str, input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckBranchNameTests(unittest.TestCase):
    def test_allows_normal_branch(self) -> None:
        result = run_checker("feat/add-validation")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")


    def test_blocks_forbidden_name_case_insensitively(self) -> None:
        result = run_checker("Fix/CURSOR-timeout")
        self.assertEqual(result.returncode, 1)
        self.assertIn("已阻止 Git push", result.stderr)
        self.assertIn("cursor", result.stderr)

    def test_blocks_each_requested_product_name(self) -> None:
        for product_name in ("codex", "claude", "antigravity", "opencode", "cursor"):
            with self.subTest(product_name=product_name):
                result = run_checker(f"feat/{product_name}-integration")
                self.assertEqual(result.returncode, 1)


    def test_pre_push_checks_local_and_remote_branch_refs(self) -> None:
        result = run_checker(
            "--pre-push",
            "origin",
            "https://github.com/example/repo.git",
            input_text=(
                "refs/heads/feat/normal 1111111111111111111111111111111111111111 "
                "refs/heads/antigravity-fix 0000000000000000000000000000000000000000\n"
            ),
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("antigravity-fix", result.stderr)


    def test_pre_push_allows_remote_branch_deletion(self) -> None:
        result = run_checker(
            "--pre-push",
            "origin",
            "https://github.com/example/repo.git",
            input_text=(
                "(delete) 0000000000000000000000000000000000000000 "
                "refs/heads/codex-old 1111111111111111111111111111111111111111\n"
            ),
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")


    def test_rejects_malformed_pre_push_input(self) -> None:
        result = run_checker(
            "--pre-push",
            "origin",
            "https://github.com/example/repo.git",
            input_text="refs/heads/feat/normal 1111\n",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("4 个字段", result.stderr)


if __name__ == "__main__":
    unittest.main()
