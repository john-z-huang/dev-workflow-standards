#!/usr/bin/env python3
"""暂存区检查器测试。"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-staged-changes.py"
PYTHON = sys.executable


def run_checker(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckStagedChangesTests(unittest.TestCase):
    def test_accepts_clean_staged_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            result = run_checker(repo)
        self.assertEqual(result.returncode, 0)

    def test_rejects_staged_whitespace_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            (repo / "example.txt").write_text("bad trailing space \n", encoding="utf-8")
            subprocess.run(["git", "add", "example.txt"], cwd=repo, check=True)
            result = run_checker(repo)
        self.assertEqual(result.returncode, 1)
        self.assertIn("空白检查", result.stderr)

    def test_runs_optional_test_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            result = run_checker(repo, "--test-command", f"{PYTHON} -c pass")
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
