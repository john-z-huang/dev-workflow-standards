from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from urllib.parse import unquote, urlsplit
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[1]


class SkillDistributionTests(unittest.TestCase):
    def test_sdist_rebuild_and_installed_cli_without_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            project = root / "checkout"
            package = project / "mcp-server"
            package.mkdir(parents=True)
            source = project / "skills" / "dev-workflow-standards"
            shutil.copytree(ROOT / "skills" / "dev-workflow-standards", source)
            shutil.copytree(ROOT / "mcp-server" / "dev_workflow_standards_tools",
                            package / "dev_workflow_standards_tools",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "skill_bundle"))
            for name in ("pyproject.toml", "hatch_build.py"):
                shutil.copy2(ROOT / "mcp-server" / name, package / name)
            environment = {**os.environ, "OPENAI_API_KEY": "", "OPENAI_BASE_URL": ""}
            environment.pop("PYTHONPATH", None)

            def run(argv, cwd=root, expected=0):
                result = subprocess.run(argv, cwd=cwd, env=environment, text=True,
                                        capture_output=True, timeout=90)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return result

            wheels = []
            for number in (1, 2):
                if number == 2:
                    with (source / "SKILL.md").open("a") as stream:
                        stream.write("\n测试第二个发布快照。\n")
                artifacts = root / f"artifacts-{number}"
                artifacts.mkdir()
                run([sys.executable, "-m", "hatchling", "build", "-t", "sdist", "-d", str(artifacts)], package)
                sdist = next(artifacts.glob("*.tar.gz"))
                extracted = root / f"extracted-{number}"
                with tarfile.open(sdist) as archive:
                    self.assertTrue(any("skill-source/SKILL.md" in name for name in archive.getnames()))
                    self.assertFalse(any(".git/" in name or ".venv/" in name or "archive/" in name
                                         for name in archive.getnames()))
                    archive.extractall(extracted, filter="data")
                rebuild_root = next(extracted.iterdir())
                # 重建位置旁边没有原仓库 skills 目录；仅使用 sdist 中的闭包。
                run([sys.executable, "-m", "hatchling", "build", "-t", "wheel", "-d", str(artifacts)], rebuild_root)
                wheel = next(artifacts.glob("*.whl"))
                wheels.append(wheel)
                with zipfile.ZipFile(wheel) as archive:
                    prefix = "dev_workflow_standards_tools/skill_bundle/"
                    manifest = json.loads(archive.read(prefix + "manifest.json"))
                    shipped = {name.removeprefix(prefix): archive.read(name)
                               for name in archive.namelist() if name.startswith(prefix)
                               and name != prefix + "manifest.json"}
                    expected_files = {p.relative_to(source).as_posix(): p.read_bytes()
                                      for p in source.rglob("*.md")}
                    self.assertEqual(shipped, expected_files)
                    metadata = yaml.safe_load(shipped["SKILL.md"].decode().split("---", 2)[1])
                    self.assertEqual(metadata["name"], "dev-workflow-standards")
                    self.assertTrue(metadata["description"].strip())
                    self.assertEqual(manifest["files"], {
                        name: hashlib.sha256(data).hexdigest() for name, data in shipped.items()
                    })
                    entrypoints = next(name for name in archive.namelist() if name.endswith("entry_points.txt"))
                    self.assertIn("dev-workflow-standards-tools = dev_workflow_standards_tools.server:main",
                                  archive.read(entrypoints).decode())
                    metadata_path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
                    self.assertNotIn("openai-codex", archive.read(metadata_path).decode().lower())
                    self.assertFalse(any("codex_sdk" in name or name.startswith("tests/")
                                         for name in archive.namelist()))
                    for name, data in shipped.items():
                        for link in re.findall(r"\]\(([^)]+)\)", data.decode()):
                            url = urlsplit(link)
                            if url.scheme or not url.path:
                                continue
                            linked = (source / name).parent / unquote(url.path)
                            self.assertTrue(linked.resolve().is_relative_to(source), (name, link))
                            self.assertTrue(linked.exists(), (name, link))
                shutil.rmtree(extracted)
            shutil.rmtree(project)
            self.assertFalse(project.exists())

            venv = root / "environment"
            run([sys.executable, "-m", "venv", "--without-pip", str(venv)])
            python = venv / "bin" / "python"
            cli = venv / "bin" / "dev-workflow-standards"
            run(["uv", "pip", "install", "--offline", "--python", str(python), "--no-deps", str(wheels[0])])
            # 该环境没有 OpenAI/MCP 依赖，管理命令仍应独立工作。
            target = root / "new-home" / ".agents" / "skills" / "dev-workflow-standards-skill"
            args = [str(cli), "skills"]
            run([*args, "install", "--target", str(target), "--dry-run"])
            self.assertFalse(target.parent.exists())
            run([*args, "install", "--target", str(target)])
            before = (target / "SKILL.md").read_bytes()
            show = json.loads(run([*args, "show", "--target", str(target)]).stdout)
            self.assertEqual(show["installed_version"], "0.2.0")
            run([*args, "install", "--target", str(target)], expected=1)
            run(["uv", "pip", "install", "--offline", "--reinstall", "--python", str(python),
                 "--no-deps", str(wheels[1])])
            self.assertEqual((target / "SKILL.md").read_bytes(), before)
            run([*args, "update", "--target", str(target), "--dry-run"])
            self.assertEqual((target / "SKILL.md").read_bytes(), before)
            run([*args, "update", "--target", str(target)])
            self.assertIn("测试第二个发布快照。", (target / "SKILL.md").read_text())
            self.assertEqual(json.loads(run([*args, "update", "--target", str(target)]).stdout)["status"], "unchanged")
            (target / "user-notes.md").write_text("keep this")
            run([*args, "update", "--target", str(target)], expected=1)
            self.assertEqual((target / "user-notes.md").read_text(), "keep this")


if __name__ == "__main__":
    unittest.main()
