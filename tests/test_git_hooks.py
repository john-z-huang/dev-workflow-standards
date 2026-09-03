#!/usr/bin/env python3
"""验证标准 Git hooks 在 git commit 阶段执行检查。"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PYTHON_SCRIPTS = (
    "check-branch-name.py",
    "check-commit-message.py",
    "check-staged-changes.py",
)


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def prepare_repo(repo: Path, branch_name: str = "feat/hook-validation") -> None:
    run_git(repo, "init", "-q").check_returncode()
    run_git(repo, "config", "user.name", "Test User").check_returncode()
    run_git(repo, "config", "user.email", "test@example.com").check_returncode()
    run_git(repo, "switch", "-c", branch_name).check_returncode()

    shutil.copytree(ROOT / ".githooks", repo / ".githooks")
    scripts = repo / "scripts"
    scripts.mkdir()
    for script_name in PYTHON_SCRIPTS:
        shutil.copy2(ROOT / "scripts" / script_name, scripts / script_name)
    run_git(repo, "config", "core.hooksPath", ".githooks").check_returncode()


def create_staged_file(repo: Path, content: str) -> None:
    (repo / "example.txt").write_text(content, encoding="utf-8")
    run_git(repo, "add", "example.txt").check_returncode()


class GitHookIntegrationTests(unittest.TestCase):
    def test_valid_commit_passes_all_commit_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            prepare_repo(repo)
            create_staged_file(repo, "valid\n")
            result = run_git(repo, "commit", "-m", "feat: 添加 hook 校验")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(run_git(repo, "rev-parse", "--verify", "HEAD").returncode, 0)

    def test_invalid_branch_is_rejected_before_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            prepare_repo(repo, "feature/invalid-format")
            create_staged_file(repo, "valid\n")
            result = run_git(repo, "commit", "-m", "feat: 添加 hook 校验")

            self.assertEqual(result.returncode, 1)
            self.assertIn("已阻止 Git commit", result.stderr)
            self.assertNotEqual(run_git(repo, "rev-parse", "--verify", "HEAD").returncode, 0)

    def test_staged_whitespace_error_is_rejected_before_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            prepare_repo(repo)
            create_staged_file(repo, "trailing space \n")
            result = run_git(repo, "commit", "-m", "feat: 添加 hook 校验")

            self.assertEqual(result.returncode, 1)
            self.assertIn("空白检查", result.stderr)
            self.assertNotEqual(run_git(repo, "rev-parse", "--verify", "HEAD").returncode, 0)

    def test_commit_message_is_rejected_during_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            prepare_repo(repo)
            create_staged_file(repo, "valid\n")
            result = run_git(repo, "commit", "-m", "feat: add hook validation")

            self.assertEqual(result.returncode, 1)
            self.assertIn("提交信息不符合规范", result.stderr)
            self.assertNotEqual(run_git(repo, "rev-parse", "--verify", "HEAD").returncode, 0)


if __name__ == "__main__":
    unittest.main()
