from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dev_workflow_standards_tools.services import skill_installation as service


def bundle(version="1", text=b"# Test Skill\n"):
    payload = {"SKILL.md": text, "references/guide.md": b"guide\n"}
    manifest = {"schema": 1, "owner": service.OWNER, "skill": service.SKILL, "version": version,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}}
    return manifest, payload


class SkillInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.target = self.root / "skills" / service.SKILL
        self.bundle_patch = patch.object(service, "_bundle", return_value=bundle())
        self.bundle_patch.start()
        self.addCleanup(self.bundle_patch.stop)

    def manage(self, action, **kwargs):
        return service.manage_skill(action, str(self.target), **kwargs)

    def test_lifecycle_explicit_update_and_idempotency(self):
        self.assertEqual(self.manage("show")["status"], "not_installed")
        self.assertEqual(self.manage("install")["status"], "installed")
        old = (self.target / "SKILL.md").read_bytes()
        with self.assertRaises(service.SkillError):
            self.manage("install")
        self.assertEqual(self.manage("update")["status"], "unchanged")
        with patch.object(service, "_bundle", return_value=bundle("2", b"new")):
            self.assertEqual(self.manage("show")["installed_version"], "1")
            self.assertEqual((self.target / "SKILL.md").read_bytes(), old)
            self.manage("update", dry_run=True)
            self.assertEqual((self.target / "SKILL.md").read_bytes(), old)
            self.assertEqual(self.manage("update")["status"], "updated")
            self.assertEqual(self.manage("show")["installed_version"], "2")

    def test_preview_has_no_side_effects(self):
        self.manage("install", dry_run=True)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_unknown_empty_and_nonempty_directories_are_preserved(self):
        self.target.mkdir(parents=True)
        with self.assertRaises(service.SkillError):
            self.manage("install")
        (self.target / "SKILL.md").write_text("old development version")
        for action in ("install", "update", "show"):
            with self.subTest(action=action):
                with self.assertRaises(service.SkillError):
                    self.manage(action)
                self.assertEqual((self.target / "SKILL.md").read_text(), "old development version")

    def test_default_install_and_update_use_new_directory_and_preserve_old_project(self):
        legacy = self.root / ".agents" / "skills" / service.SKILL
        legacy.mkdir(parents=True)
        (legacy / "SKILL.md").write_text("old project")
        (legacy / ".git").mkdir()
        with patch.object(Path, "home", return_value=self.root):
            expected = self.root / ".agents" / "skills" / "dev-workflow-standards-skill"
            result = service.manage_skill("install", dry_run=True)
            self.assertEqual(result["target"], str(expected))
            self.assertFalse(expected.exists())
            service.manage_skill("install")
            self.assertEqual(service.manage_skill("show")["target"], str(expected))
            with patch.object(service, "_bundle", return_value=bundle("2", b"new snapshot")):
                service.manage_skill("update")
            self.assertEqual((expected / "SKILL.md").read_bytes(), b"new snapshot")
        self.assertEqual((legacy / "SKILL.md").read_text(), "old project")
        self.assertEqual(sorted(path.name for path in legacy.iterdir()), [".git", "SKILL.md"])

    def test_explicit_legacy_targets_are_blocked_even_with_valid_managed_manifest(self):
        legacy = self.root / ".agents" / "skills" / service.SKILL
        manifest, payload = bundle()
        for name, data in payload.items():
            path = legacy / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (legacy / service.MARKER).write_bytes(service._manifest_bytes(manifest))
        before = service._snapshot(legacy)
        with patch.object(Path, "home", return_value=self.root):
            for target in (legacy, legacy / "nested", legacy.parent):
                for action in ("install", "update"):
                    with self.subTest(target=target, action=action), self.assertRaisesRegex(service.SkillError, "旧项目目录受保护"):
                        service.manage_skill(action, str(target))
        self.assertEqual(service._snapshot(legacy), before)

    def test_resolved_legacy_directory_cannot_be_used_as_explicit_target(self):
        actual = self.root / "old-checkout"
        actual.mkdir()
        (actual / "SKILL.md").write_text("old project")
        legacy = self.root / ".agents" / "skills" / service.SKILL
        legacy.parent.mkdir(parents=True)
        legacy.symlink_to(actual, target_is_directory=True)
        with patch.object(Path, "home", return_value=self.root):
            for target in (actual, legacy):
                with self.subTest(target=target), self.assertRaisesRegex(service.SkillError, "旧项目目录受保护"):
                    service.manage_skill("install", str(target))
        self.assertEqual((actual / "SKILL.md").read_text(), "old project")

    def test_git_checkout_target_and_ancestor_are_refused(self):
        self.target.mkdir(parents=True)
        (self.target / ".git").mkdir()
        with self.assertRaises(service.SkillError):
            self.manage("update")
        (self.root / ".git").write_text("gitdir: elsewhere")
        with self.assertRaises(service.SkillError):
            service.manage_skill("install", str(self.root / "new"))

    def test_traversal_and_symlink_target_and_ancestor_are_refused(self):
        self.target.parent.mkdir()
        self.target.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(service.SkillError):
            self.manage("install")
        link = self.root / "link"
        link.symlink_to(self.target.parent, target_is_directory=True)
        with self.assertRaises(service.SkillError):
            service.manage_skill("install", str(link / "new"))
        with self.assertRaises(service.SkillError):
            service.manage_skill("install", str(self.root / "missing" / ".." / "new"))

    def test_modified_extra_missing_and_special_contents_block_update(self):
        changes = ("modified", "missing", "extra", "empty_dir", "symlink", "hardlink", "fifo")
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                target = self.root / str(index)
                service.manage_skill("install", str(target))
                guide = target / "references" / "guide.md"
                if change == "modified":
                    guide.write_text("user edit")
                elif change == "missing":
                    guide.unlink()
                elif change == "extra":
                    (target / "extra").write_text("user file")
                elif change == "empty_dir":
                    (target / "empty").mkdir()
                elif change == "symlink":
                    guide.unlink()
                    guide.symlink_to(self.root / "external")
                elif change == "hardlink":
                    os.link(guide, self.root / "external")
                elif change == "fifo":
                    os.mkfifo(target / "pipe")
                with self.assertRaises(service.SkillError):
                    service.manage_skill("update", str(target))
                self.assertTrue(target.exists())

    def test_failure_before_atomic_publish_keeps_old_installation(self):
        self.manage("install")
        before = service._snapshot(self.target)
        with patch.object(service, "_bundle", return_value=bundle("2", b"new")), patch.object(
            service, "_publish", side_effect=service.SkillError("simulated failure")
        ), self.assertRaises(service.SkillError):
            self.manage("update")
        self.assertEqual(service._snapshot(self.target), before)

    def test_racing_first_install_does_not_replace_newly_created_target(self):
        publish = service._publish
        def competing_install(source, target, *, exchange):
            target.mkdir()
            (target / "user-file").write_text("preserve concurrent content")
            publish(source, target, exchange=exchange)
        with patch.object(service, "_publish", side_effect=competing_install), self.assertRaises(service.SkillError):
            self.manage("install")
        self.assertEqual((self.target / "user-file").read_text(), "preserve concurrent content")
        self.assertFalse((self.target / "SKILL.md").exists())

    def test_interrupt_after_swap_leaves_complete_new_target(self):
        self.manage("install")
        publish = service._publish

        def interrupted(*args, **kwargs):
            publish(*args, **kwargs)
            raise KeyboardInterrupt

        with patch.object(service, "_bundle", return_value=bundle("2", b"new")), patch.object(
            service, "_publish", side_effect=interrupted
        ), self.assertRaises(KeyboardInterrupt):
            self.manage("update")
        self.assertEqual(self.manage("show")["installed_version"], "2")
        self.assertEqual((self.target / "SKILL.md").read_bytes(), b"new")

    def test_external_edit_before_swap_is_rejected_and_preserved(self):
        self.manage("install")
        installed = service._installed
        def edit_when_staged(path):
            result = installed(path)
            if path != self.target:
                (self.target / "SKILL.md").write_text("external edit")
            return result
        with patch.object(service, "_bundle", return_value=bundle("2", b"new")), patch.object(
            service, "_installed", side_effect=edit_when_staged
        ), self.assertRaises(service.SkillError):
            self.manage("update")
        self.assertEqual((self.target / "SKILL.md").read_text(), "external edit")

    def test_external_special_file_during_swap_is_preserved_and_rolled_back(self):
        self.manage("install")
        publish = service._publish
        def edit_before_swap(source, target, *, exchange):
            if not (target / "pipe").exists():
                os.mkfifo(target / "pipe")
            publish(source, target, exchange=exchange)
        with patch.object(service, "_bundle", return_value=bundle("2", b"new")), patch.object(
            service, "_publish", side_effect=edit_before_swap
        ), self.assertRaises(service.SkillError):
            self.manage("update")
        self.assertTrue((self.target / "pipe").exists())
        self.assertEqual((self.target / "SKILL.md").read_bytes(), bundle()[1]["SKILL.md"])

    def test_cooperating_process_lock_blocks_a_second_writer(self):
        self.target.parent.mkdir()
        with service._lock(self.target), self.assertRaisesRegex(service.SkillError, "另一个"):
            self.manage("install")
        self.assertFalse(self.target.exists())

    def test_unknown_platform_has_no_writes(self):
        with patch.object(service.sys, "platform", "win32"), self.assertRaises(service.SkillError):
            self.manage("install")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_untrusted_manifest_paths_and_schema_are_refused(self):
        original, _ = bundle()
        for name in ("../escape.md", "/absolute.md", "a/../../escape.md", "a\\b.md", "./test.md", ".git/config.md", "a\x00.md"):
            data = {**original, "files": {**original["files"], name: "a" * 64}}
            with self.subTest(name=name), self.assertRaises(service.SkillError):
                service._manifest(json.dumps(data).encode())
        with self.assertRaises(service.SkillError):
            service._manifest(b"not json")
        with self.assertRaises(service.SkillError):
            service._manifest(b"\xff")
        with self.assertRaises(service.SkillError):
            service.manage_skill("install", "bad\x00path")


if __name__ == "__main__":
    unittest.main()
