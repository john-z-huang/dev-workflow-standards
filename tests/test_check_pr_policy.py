#!/usr/bin/env python3
"""Issue/PR 策略审计测试。"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check-pr-policy.py"
SPEC = importlib.util.spec_from_file_location("check_pr_policy", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CheckPrPolicyTests(unittest.TestCase):
    def test_recognizes_issue_closing_keywords(self) -> None:
        self.assertTrue(MODULE.has_issue_closing_reference("Closes #7", 7))
        self.assertTrue(MODULE.has_issue_closing_reference("fixes #7", 7))
        self.assertFalse(MODULE.has_issue_closing_reference("Closes #8", 7))

    def test_validates_open_issue(self) -> None:
        self.assertEqual(MODULE.validate_issue({"state": "open"}), ())
        self.assertTrue(MODULE.validate_issue({"state": "closed"}))

    def test_validates_pr_topology_and_issue_reference(self) -> None:
        pr = {
            "state": "open",
            "body": "Closes #7",
            "base": {"ref": "main"},
            "head": {"ref": "feat/workflow-policy-checks"},
        }
        self.assertEqual(
            MODULE.validate_pr(
                pr,
                issue_number=7,
                expected_base="main",
                expected_head="feat/workflow-policy-checks",
            ),
            (),
        )
        self.assertTrue(
            MODULE.validate_pr(pr, issue_number=7, expected_base="release")
        )


if __name__ == "__main__":
    unittest.main()
