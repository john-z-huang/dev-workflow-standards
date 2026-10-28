from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import queue
import unittest
from unittest.mock import patch

from dev_workflow_standards_tools.services import create_branch


class CreateRepositoryBranchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="branch tool 仓库 ")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)

    def git(self, repo: pathlib.Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", check=False,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        if check and result.returncode:
            self.fail(f"git {' '.join(args)} failed: {result.stderr}")
        return result

    def init_repo(self, *, detached: bool = False) -> pathlib.Path:
        repo = self.root / f"repo {len(list(self.root.iterdir()))} 日本語"
        repo.mkdir()
        self.git(repo, "init", "-q")
        self.git(repo, "config", "user.name", "Synthetic Fixture")
        self.git(repo, "config", "user.email", "fixture@example.invalid")
        for name, content in (
            ("staged-only", b"baseline staged\n"),
            ("unstaged-only", b"baseline unstaged\n"),
            ("mixed", b"baseline mixed\n"),
        ):
            (repo / name).write_bytes(content)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-qm", "baseline")
        if detached:
            head = self.git(repo, "rev-parse", "HEAD").stdout.strip()
            self.git(repo, "checkout", "--detach", "-q", head)
        return repo

    def add_dirty_files(self, repo: pathlib.Path) -> dict[str, bytes]:
        (repo / "staged-only").write_bytes(b"staged\x00only\n")
        self.git(repo, "add", "staged-only")
        (repo / "unstaged-only").write_bytes(b"unstaged\xffonly\n")
        (repo / "mixed").write_bytes(b"index version\n")
        self.git(repo, "add", "mixed")
        (repo / "mixed").write_bytes(b"worktree version\x00\n")
        (repo / "untracked").write_bytes(b"untracked\n")
        return {name: (repo / name).read_bytes() for name in ("staged-only", "unstaged-only", "mixed", "untracked")}

    def snapshot(self, repo: pathlib.Path) -> tuple[dict[str, bytes], bytes, bytes, bytes]:
        files = {name: (repo / name).read_bytes() for name in ("staged-only", "unstaged-only", "mixed", "untracked")}
        status = self.git(repo, "--no-optional-locks", "status", "--porcelain=v1", "-z").stdout.encode()
        stages = self.git(repo, "--no-optional-locks", "ls-files", "--stage", "-z").stdout.encode()
        index = pathlib.Path(self.git(repo, "rev-parse", "--git-path", "index").stdout.strip())
        if not index.is_absolute():
            index = repo / index
        return files, status, stages, index.read_bytes()

    def result(self, repo: pathlib.Path, branch: str = "feat/synthetic", expected: str | None = None) -> dict:
        return create_branch.create_repository_branch(str(repo), branch, expected)

    def test_detached_and_ordinary_branch_preserve_dirty_worktree_and_index(self) -> None:
        for detached in (False, True):
            with self.subTest(detached=detached):
                repo = self.init_repo(detached=detached)
                file_bytes = self.add_dirty_files(repo)
                before = self.snapshot(repo)
                head_oid = self.git(repo, "rev-parse", "HEAD").stdout.strip()
                old_branch = self.git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
                old_branch_name = old_branch.stdout.strip() if old_branch.returncode == 0 else None
                created = self.result(repo, "feat/synthetic", head_oid.upper())
                self.assertTrue(created["ok"], created)
                self.assertTrue(created["created"])
                self.assertEqual(created["start_head_oid"], head_oid)
                self.assertEqual(self.snapshot(repo), before)
                self.assertEqual({name: (repo / name).read_bytes() for name in file_bytes}, file_bytes)
                self.assertEqual(self.git(repo, "symbolic-ref", "HEAD").stdout.strip(), "refs/heads/feat/synthetic")
                self.assertEqual(self.git(repo, "rev-parse", "HEAD").stdout.strip(), head_oid)
                self.assertEqual(self.git(repo, "rev-parse", "refs/heads/feat/synthetic").stdout.strip(), head_oid)
                if old_branch_name:
                    self.assertEqual(self.git(repo, "rev-parse", f"refs/heads/{old_branch_name}").stdout.strip(), head_oid)
                    self.assertNotEqual(self.git(repo, "symbolic-ref", "-q", "--no-recurse", f"refs/heads/{old_branch_name}", check=False).returncode, 0)
                    old_ref = pathlib.Path(self.git(repo, "rev-parse", "--git-path", f"refs/heads/{old_branch_name}").stdout.strip())
                    if not old_ref.is_absolute():
                        old_ref = repo / old_ref
                    self.assertEqual(old_ref.read_bytes(), f"{head_oid}\n".encode())

    def test_linked_worktree_with_non_ascii_space_path(self) -> None:
        main = self.init_repo()
        target = self.root / "linked worktree 日本語 with spaces"
        self.git(main, "worktree", "add", "-q", "-b", "feat/linked-source", str(target), "HEAD")
        dirty = self.add_dirty_files(target)
        before = self.snapshot(target)
        result = self.result(target, "fix/linked-target")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["repo_path"], str(target.resolve()))
        self.assertEqual(self.snapshot(target), before)
        self.assertEqual((target / "untracked").read_bytes(), dirty["untracked"])
        self.assertEqual(self.git(target, "symbolic-ref", "HEAD").stdout.strip(), "refs/heads/fix/linked-target")
        old_ref = pathlib.Path(self.git(target, "rev-parse", "--git-path", "refs/heads/feat/linked-source").stdout.strip())
        if not old_ref.is_absolute():
            old_ref = target / old_ref
        self.assertEqual(old_ref.read_bytes(), f"{self.git(target, 'rev-parse', 'HEAD').stdout.strip()}\n".encode())

    def test_ref_conflicts_invalid_branch_oid_and_wrong_repo_are_rejected(self) -> None:
        repo = self.init_repo()
        head = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        self.assertFalse(self.result(repo, "main")["created"])
        self.assertFalse(self.result(repo, "master")["created"])
        self.assertFalse(self.result(repo, "not valid")["created"])
        self.assertFalse(self.result(repo, "feat/synthetic", "")["created"])
        self.assertFalse(self.result(repo, "feat/synthetic", "g" * 40)["created"])
        self.assertFalse(self.result(repo, "feat/synthetic", 123)["created"])
        self.assertTrue(self.result(repo, "feat/null-expected", None)["ok"])

        duplicate_repo = self.init_repo()
        self.git(duplicate_repo, "branch", "feat/existing")
        self.assertEqual(self.result(duplicate_repo, "feat/existing")["error_code"], "branch_exists")
        symbolic_repo = self.init_repo()
        self.git(symbolic_repo, "symbolic-ref", "refs/heads/feat/symbolic", "refs/heads/main")
        self.assertEqual(self.result(symbolic_repo, "feat/symbolic")["error_code"], "branch_exists")
        dangling_repo = self.init_repo()
        self.git(dangling_repo, "symbolic-ref", "refs/heads/feat/dangling", "refs/heads/missing-target")
        self.assertEqual(self.result(dangling_repo, "feat/dangling")["error_code"], "branch_exists")
        self.assertEqual(self.result(repo / "staged-only", "feat/child")["error_code"], "invalid_repo_path")
        self.assertEqual(self.result(self.root / "missing", "feat/missing")["error_code"], "invalid_repo_path")
        self.assertEqual(self.git(repo, "rev-parse", "HEAD").stdout.strip(), head)

    def test_unborn_head_and_conflict_operation_markers_are_rejected(self) -> None:
        unborn = self.root / "unborn"
        unborn.mkdir()
        self.git(unborn, "init", "-q")
        self.assertEqual(self.result(unborn)["error_code"], "head_unavailable")
        for marker in ("MERGE_HEAD", "rebase-merge", "rebase-apply", "sequencer"):
            repo = self.init_repo()
            marker_path = self.git(repo, "rev-parse", "--git-path", marker).stdout.strip()
            path = pathlib.Path(marker_path)
            if not path.is_absolute():
                path = repo / path
            if marker in {"rebase-merge", "rebase-apply", "sequencer"}:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.write_text("synthetic", encoding="utf-8")
            result = self.result(repo, "feat/blocked")
            self.assertEqual(result["error_code"], "operation_in_progress", result)

    def test_unmerged_index_locked_worktree_and_ref_lock_fail_closed(self) -> None:
        repo = self.init_repo()
        path = repo / "conflict"
        path.write_text("base\n", encoding="utf-8")
        self.git(repo, "add", "conflict")
        self.git(repo, "commit", "-qm", "add conflict")
        self.git(repo, "checkout", "-qb", "side")
        path.write_text("side\n", encoding="utf-8")
        self.git(repo, "commit", "-qam", "side")
        self.git(repo, "checkout", "-q", "main")
        path.write_text("main\n", encoding="utf-8")
        self.git(repo, "commit", "-qam", "main")
        self.git(repo, "merge", "side", check=False)
        self.assertEqual(self.result(repo, "feat/conflict")["error_code"], "unmerged_index")

        lock_repo = self.init_repo()
        ref_lock = pathlib.Path(self.git(lock_repo, "rev-parse", "--git-path", "refs/heads/feat/locked.lock").stdout.strip())
        if not ref_lock.is_absolute():
            ref_lock = lock_repo / ref_lock
        ref_lock.parent.mkdir(parents=True, exist_ok=True)
        ref_lock.write_text("synthetic lock", encoding="utf-8")
        self.assertEqual(self.result(lock_repo, "feat/locked")["error_code"], "repository_locked")

        linked_source = self.init_repo()
        locked = self.root / "locked linked worktree"
        self.git(linked_source, "worktree", "add", "-q", "-b", "feat/locked-source", str(locked), "HEAD")
        self.git(linked_source, "worktree", "lock", str(locked))
        self.assertEqual(self.result(locked, "fix/locked-worktree")["error_code"], "worktree_locked")

    def test_reference_transaction_hook_and_custom_hooks_path_are_rejected_without_running(self) -> None:
        for custom in (False, True):
            repo = self.init_repo()
            hook_dir = self.root / ("custom hooks 日本語" if custom else ".git-hooks")
            if not custom:
                hook_dir = pathlib.Path(self.git(repo, "rev-parse", "--git-path", "hooks").stdout.strip())
                if not hook_dir.is_absolute():
                    hook_dir = repo / hook_dir
            hook_dir.mkdir(parents=True, exist_ok=True)
            marker = self.root / "hook-ran"
            marker.unlink(missing_ok=True)
            hook = hook_dir / "reference-transaction"
            hook.write_text(f"#!{os.sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n", encoding="utf-8")
            hook.chmod(0o755)
            if custom:
                self.git(repo, "config", "core.hooksPath", str(hook_dir))
            result = self.result(repo, "feat/hook")
            self.assertEqual(result["error_code"], "reference_transaction_hook", result)
            self.assertFalse(marker.exists())
            self.assertFalse(self.git(repo, "show-ref", "--verify", "refs/heads/feat/hook", check=False).returncode == 0)

    def test_stale_oid_before_transaction_and_concurrent_advance_between_capture_and_prepare(self) -> None:
        repo = self.init_repo()
        old = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.result(repo, "feat/stale", "f" * 40)["error_code"], "head_oid_mismatch")

        race_repo = self.init_repo()
        old_race = self.git(race_repo, "rev-parse", "HEAD").stdout.strip()
        real_git = create_branch._git
        advanced = False

        def race_git(root: str, *args: str, **kwargs):
            nonlocal advanced
            input_text = kwargs.get("input_text")
            if args[:2] == ("update-ref", "--stdin") and input_text and "prepare\ncommit" in input_text and not advanced:
                advanced = True
                (race_repo / "advanced").write_text("new commit", encoding="utf-8")
                subprocess.run(["git", "add", "advanced"], cwd=race_repo, check=True)
                subprocess.run(["git", "commit", "-qm", "advance"], cwd=race_repo, check=True)
            return real_git(root, *args, **kwargs)

        with patch.object(create_branch, "_git", side_effect=race_git):
            result = self.result(race_repo, "feat/race", old_race)
        self.assertTrue(advanced)
        self.assertFalse(result["ok"])
        self.assertIsNone(result["created"])
        self.assertTrue(result["needs_review"])
        self.assertFalse(self.git(race_repo, "show-ref", "--verify", "refs/heads/feat/race", check=False).returncode == 0)

    def test_git_environment_redirect_and_reference_read_failure_are_rejected_before_transaction(self) -> None:
        repo = self.init_repo()
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "redirected.git")}):
            with patch.object(create_branch, "_validated_repo_path") as validate:
                result = self.result(repo, "feat/env-redirect")
        self.assertEqual(result["error_code"], "git_environment_redirected")
        validate.assert_not_called()

        real_git = create_branch._git
        calls: list[tuple[str, ...]] = []

        def fail_ref_read(root: str, *args: str, **kwargs):
            calls.append(args)
            if args[:2] == ("show-ref", "--exists"):
                return subprocess.CompletedProcess(["git", *args], 1, "", "")
            return real_git(root, *args, **kwargs)

        with patch.object(create_branch, "_git", side_effect=fail_ref_read):
            result = self.result(repo, "feat/read-failure")
        self.assertEqual(result["error_code"], "branch_state_unavailable")
        self.assertFalse(any(args[:2] == ("update-ref", "--stdin") for args in calls))

        with patch.object(create_branch, "_validated_repo_path", side_effect=UnicodeError("private path text")):
            result = self.result(repo, "feat/path-decode")
        self.assertEqual(result["error_code"], "invalid_repo_path")
        self.assertNotIn("private path text", result["error"] or "")

    def test_permission_and_uncertain_transaction_failures_are_sanitized(self) -> None:
        repo = self.init_repo()
        with patch.object(create_branch, "_validated_repo_path", side_effect=PermissionError("private filesystem detail")):
            result = self.result(repo, "feat/path-permission")
        self.assertEqual(result["error_code"], "invalid_repo_path")
        self.assertNotIn("private filesystem detail", result["error"] or "")

        real_run = subprocess.run
        calls: list[list[str]] = []

        def deny_ref_read(command, *args, **kwargs):
            calls.append(command)
            if command[:4] == ["git", "--no-lazy-fetch", "show-ref", "--exists"]:
                raise PermissionError("private ref path")
            return real_run(command, *args, **kwargs)

        with patch.object(create_branch.subprocess, "run", side_effect=deny_ref_read):
            result = self.result(repo, "feat/ref-permission")
        self.assertEqual(result["error_code"], "git_unavailable")
        self.assertFalse(result["created"])
        self.assertFalse(any(args[:3] == ["git", "--no-lazy-fetch", "update-ref"] for args in calls))
        self.assertNotIn("private ref path", result["error"] or "")

        real_run = subprocess.run

        def deny_transaction(command, *args, **kwargs):
            if command[:3] == ["git", "--no-lazy-fetch", "update-ref"] and "prepare\ncommit" in kwargs.get("input", ""):
                raise PermissionError("private transaction spawn detail")
            return real_run(command, *args, **kwargs)

        transaction_repo = self.init_repo()
        with patch.object(create_branch.subprocess, "run", side_effect=deny_transaction):
            result = self.result(transaction_repo, "feat/transaction-permission")
        self.assertEqual(result["error_code"], "transaction_failed")
        self.assertIsNone(result["created"])
        self.assertTrue(result["needs_review"])
        self.assertNotIn("private transaction spawn detail", result["error"] or "")

        real_run = subprocess.run

        def report_transaction_failure(command, *args, **kwargs):
            if command[:3] == ["git", "--no-lazy-fetch", "update-ref"] and "prepare\ncommit" in kwargs.get("input", ""):
                return subprocess.CompletedProcess(command, 1, "", "private Git stderr")
            return real_run(command, *args, **kwargs)

        nonzero_repo = self.init_repo()
        with patch.object(create_branch.subprocess, "run", side_effect=report_transaction_failure):
            result = self.result(nonzero_repo, "feat/transaction-nonzero")
        self.assertEqual(result["error_code"], "transaction_failed")
        self.assertIsNone(result["created"])
        self.assertNotIn("private Git stderr", result["error"] or "")

        def complete_then_decode_error(command, *args, **kwargs):
            completed = real_run(command, *args, **kwargs)
            if command[:3] == ["git", "--no-lazy-fetch", "update-ref"] and "prepare\ncommit" in kwargs.get("input", ""):
                raise UnicodeError("private invalid byte sequence")
            return completed

        decode_repo = self.init_repo()
        with patch.object(create_branch.subprocess, "run", side_effect=complete_then_decode_error):
            result = self.result(decode_repo, "feat/transaction-decode")
        self.assertEqual(result["error_code"], "transaction_failed")
        self.assertIsNone(result["created"])
        self.assertTrue(result["needs_review"])
        self.assertNotIn("private invalid byte sequence", result["error"] or "")

    def test_prepared_transaction_locks_source_branch_and_worktree_data_stays_intact(self) -> None:
        repo = self.init_repo()
        self.add_dirty_files(repo)
        before = self.snapshot(repo)
        branch = self.git(repo, "symbolic-ref", "--short", "HEAD").stdout.strip()
        old = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        proc = subprocess.Popen(
            ["git", "--no-lazy-fetch", "update-ref", "--stdin"], cwd=repo, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
        )
        assert proc.stdin is not None and proc.stdout is not None
        response_queue: queue.Queue[str | None] = queue.Queue()

        def read_responses() -> None:
            assert proc.stdout is not None
            for response in proc.stdout:
                response_queue.put(response.strip())
            response_queue.put(None)

        reader = threading.Thread(target=read_responses, daemon=True)
        reader.start()
        try:
            proc.stdin.write(f"start\ncreate refs/heads/feat/prepared {old}\noption no-deref\nsymref-update HEAD refs/heads/feat/prepared oid {old}\nprepare\n")
            proc.stdin.flush()
            responses: list[str] = []
            while not any(line == "prepare: ok" for line in responses):
                line = response_queue.get(timeout=10)
                if line is None:
                    self.fail(f"update-ref exited before prepare confirmation: {responses}")
                responses.append(line)
                if len(responses) > 8:
                    self.fail(f"unexpected update-ref prepare responses: {responses}")
            tree = self.git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
            env = {
                **os.environ,
                "GIT_AUTHOR_NAME": "Synthetic Fixture",
                "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
                "GIT_COMMITTER_NAME": "Synthetic Fixture",
                "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            }
            commit = subprocess.run(
                ["git", "commit-tree", tree, "-p", old, "-m", "concurrent advance"], cwd=repo,
                capture_output=True, text=True, encoding="utf-8", env=env, check=True,
            ).stdout.strip()
            advanced = self.git(repo, "update-ref", f"refs/heads/{branch}", commit, old, check=False)
            self.assertNotEqual(advanced.returncode, 0)
            self.assertIn("HEAD.lock", advanced.stderr)
            proc.stdin.write("commit\n")
            proc.stdin.flush()
            proc.stdin.close()
            proc.wait(timeout=10)
            self.assertEqual(proc.returncode, 0, proc.stderr.read() if proc.stderr else "")
        finally:
            if proc.poll() is None:
                try:
                    proc.stdin.write("abort\n")
                    proc.stdin.flush()
                except (BrokenPipeError, OSError, ValueError):
                    proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            if proc.stdin is not None:
                proc.stdin.close()
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
        self.assertEqual(self.snapshot(repo), before)
        self.assertEqual(self.git(repo, "rev-parse", f"refs/heads/{branch}").stdout.strip(), old)
        self.assertEqual(self.git(repo, "symbolic-ref", "HEAD").stdout.strip(), "refs/heads/feat/prepared")

    def test_probe_and_post_success_readback_failure_results_are_distinct(self) -> None:
        repo = self.init_repo()
        calls: list[tuple[str, ...]] = []
        real_git = create_branch._git

        def record(root: str, *args: str, **kwargs):
            calls.append(args)
            return real_git(root, *args, **kwargs)

        with patch.object(create_branch, "_git", side_effect=record):
            result = self.result(repo, "feat/probe")
        self.assertTrue(result["ok"])
        self.assertTrue(any(args[:2] == ("update-ref", "--stdin") for args in calls))
        self.assertFalse(any(args[0] in {"checkout", "switch", "add", "commit", "push"} for args in calls))

        probe_repo = self.init_repo()
        probe_oid = self.git(probe_repo, "rev-parse", "HEAD").stdout.strip()
        self.add_dirty_files(probe_repo)
        probe_before = self.snapshot(probe_repo)
        probe = create_branch._git(
            str(probe_repo), "update-ref", "--stdin",
            input_text=create_branch._TRANSACTION.format(branch="feat/probe-only", oid=probe_oid, ending="abort"),
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(self.snapshot(probe_repo), probe_before)
        self.assertFalse((probe_repo / ".git" / "hook-log").exists())
        self.assertFalse(self.git(probe_repo, "show-ref", "--verify", "refs/heads/feat/probe-only", check=False).returncode == 0)
        self.assertFalse((probe_repo / ".git" / "logs" / "refs" / "heads" / "feat" / "probe-only").exists())

        repo2 = self.init_repo()
        real_git = create_branch._git

        transaction_done = False

        def fail_readback(root: str, *args: str, **kwargs):
            nonlocal transaction_done
            if args[:2] == ("update-ref", "--stdin"):
                completed = real_git(root, *args, **kwargs)
                transaction_done = completed.returncode == 0
                return completed
            if transaction_done and args[:3] == ("rev-parse", "--verify", "--end-of-options"):
                return subprocess.CompletedProcess(["git", *args], 2, "", "")
            return real_git(root, *args, **kwargs)

        with patch.object(create_branch, "_git", side_effect=fail_readback):
            result = self.result(repo2, "feat/readback")
        self.assertFalse(result["ok"])
        self.assertTrue(result["created"])
        self.assertEqual(result["error_code"], "post_commit_verification_failed")
        self.assertTrue(result["needs_review"])

    def test_every_service_git_call_disables_lazy_fetch_and_old_git_fails_closed(self) -> None:
        repo = self.init_repo()
        real_run = subprocess.run
        git_calls: list[tuple[list[str], dict]] = []

        def inspect_run(command, *args, **kwargs):
            if command and command[0] == "git" and len(command) > 1 and command[1] != "rev-parse":
                git_calls.append((command, kwargs))
            return real_run(command, *args, **kwargs)

        with patch.dict(os.environ, {"GIT_NO_LAZY_FETCH": "0"}):
            with patch.object(create_branch.subprocess, "run", side_effect=inspect_run):
                result = self.result(repo, "feat/no-lazy")
        self.assertTrue(result["ok"], result)
        self.assertTrue(git_calls)
        for command, kwargs in git_calls:
            self.assertEqual(command[1], "--no-lazy-fetch", command)
            self.assertEqual(kwargs["env"]["GIT_NO_LAZY_FETCH"], "1")

        unsupported_repo = self.init_repo()
        commands: list[tuple[str, ...]] = []

        def unsupported(root: str, *args: str, **kwargs):
            commands.append(args)
            return subprocess.CompletedProcess(["git", *args], 129, "", "unknown option")

        with patch.object(create_branch, "_git", side_effect=unsupported):
            result = self.result(unsupported_repo, "feat/unsupported")
        self.assertEqual(result["error_code"], "git_capability_unavailable")
        self.assertEqual(commands, [("--version",)])

    def test_missing_promisor_object_does_not_launch_remote_helper(self) -> None:
        repo = self.init_repo()
        head_oid = self.git(repo, "rev-parse", "HEAD").stdout.strip()
        object_path = repo / ".git" / "objects" / head_oid[:2] / head_oid[2:]
        self.assertTrue(object_path.exists())
        object_path.unlink()
        self.git(repo, "config", "extensions.partialClone", "origin")
        self.git(repo, "config", "remote.origin.promisor", "true")
        self.git(repo, "config", "remote.origin.url", "marker::fixture")
        self.git(repo, "config", "protocol.marker.allow", "always")
        helper_dir = self.root / "helper bin"
        helper_dir.mkdir()
        marker = self.root / "remote-helper-ran"
        helper = helper_dir / "git-remote-marker"
        helper.write_text(
            f"#!{sys.executable}\nfrom pathlib import Path\nimport os\nPath(os.environ['FETCH_MARKER']).write_text('ran')\n",
            encoding="utf-8",
        )
        helper.chmod(0o755)
        path = str(helper_dir) + os.pathsep + os.environ.get("PATH", "")
        helper_env = {**os.environ, "PATH": path, "GIT_NO_LAZY_FETCH": "0", "FETCH_MARKER": str(marker)}
        positive = subprocess.run(
            ["git", "cat-file", "-t", head_oid], cwd=repo, capture_output=True, text=True,
            encoding="utf-8", env=helper_env, check=False,
        )
        self.assertNotEqual(positive.returncode, 0, positive.stdout)
        self.assertTrue(marker.exists(), positive.stderr)
        marker.unlink()
        with patch.dict(os.environ, helper_env):
            result = self.result(repo, "feat/missing-promisor")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "head_not_commit")
        self.assertFalse(marker.exists())
        self.assertFalse(self.git(repo, "show-ref", "--verify", "refs/heads/feat/missing-promisor", check=False).returncode == 0)


if __name__ == "__main__":
    unittest.main()
