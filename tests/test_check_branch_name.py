#!/usr/bin/env python3
"""分支名称 commit 前检查器测试。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-branch-name.py"
PYTHON = sys.executable


def run_checker(
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=cwd,
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
        self.assertIn("已阻止 Git commit", result.stderr)
        self.assertIn("cursor", result.stderr)

    def test_blocks_each_requested_product_name(self) -> None:
        for product_name in ("codex", "claude", "antigravity", "opencode", "cursor"):
            with self.subTest(product_name=product_name):
                result = run_checker(f"feat/{product_name}-integration")
                self.assertEqual(result.returncode, 1)

    def test_pre_commit_checks_current_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "switch", "-c", "feature/add-validation"], cwd=repo, check=True)
            result = run_checker("--pre-commit", cwd=repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("不符合策略", result.stderr)

    def test_allows_protected_root_branch(self) -> None:
        result = run_checker("main")
        self.assertEqual(result.returncode, 0)

    def test_blocks_invalid_branch_format(self) -> None:
        for branch_name in (
            "feature/add-validation",
            "feat/Add-validation",
            "feat/add_validation",
            "update-docs",
            "feat/add--validation",
        ):
            with self.subTest(branch_name=branch_name):
                result = run_checker(branch_name)
                self.assertEqual(result.returncode, 1)
                self.assertIn("不符合策略", result.stderr)


if __name__ == "__main__":
    unittest.main()
