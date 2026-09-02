#!/usr/bin/env python3
"""PR 合并后清理脚本测试。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "pr-merge-cleanup.py"
SPEC = importlib.util.spec_from_file_location("pr_merge_cleanup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrMergeCleanupTests(unittest.TestCase):
    def test_reads_base_and_head_from_merged_pr(self) -> None:
        result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "state": "MERGED",
                    "mergedAt": "2026-09-02T06:00:39Z",
                    "baseRefName": "main",
                    "headRefName": "feat/example",
                    "title": "示例变更",
                }
            ),
            stderr="",
        )
        with patch.object(MODULE, "run_command", return_value=result) as run_command:
            info = MODULE.check_pr_merged(6, "owner/repo")

        self.assertEqual(info["baseRefName"], "main")
        self.assertEqual(info["headRefName"], "feat/example")
        run_command.assert_called_once_with(
            [
                "gh",
                "pr",
                "view",
                "6",
                "--repo",
                "owner/repo",
                "--json",
                "state,mergedAt,baseRefName,headRefName,title",
            ]
        )

    def test_pull_uses_fast_forward_only(self) -> None:
        with patch.object(MODULE, "run_command") as run_command:
            MODULE.pull_latest("release")
        run_command.assert_called_once_with(
            ["git", "pull", "--ff-only", "origin", "release"]
        )

    def test_switch_tracks_remote_base_when_local_base_is_missing(self) -> None:
        failed_switch = subprocess.CompletedProcess([], 1, "", "missing")
        successful_switch = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(
            MODULE,
            "run_command",
            side_effect=[failed_switch, successful_switch],
        ) as run_command:
            MODULE.switch_to_base("release")

        self.assertEqual(run_command.call_args_list[0].args[0], ["git", "switch", "release"])
        self.assertEqual(
            run_command.call_args_list[1].args[0],
            ["git", "switch", "--track", "origin/release"],
        )


if __name__ == "__main__":
    unittest.main()
