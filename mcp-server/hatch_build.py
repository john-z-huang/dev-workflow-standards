"""从唯一指令源构建独立资源；sdist 自带同一份源，不回溯开发仓库。"""

import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import unquote, urlsplit

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        # sdist 中优先使用封装的源；仅开发构建从仓库的唯一源取得资源。
        source = root / "skill-source"
        if not source.exists():
            source = root.parent / "skills" / "dev-workflow-standards"
        if source.is_symlink() or not (source / "SKILL.md").is_file():
            raise ValueError("缺少完整 Skill 指令源")
        payload = {}
        for path in sorted(source.rglob("*")):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise ValueError("Skill 源包含链接或特殊文件")
            if path.is_dir():
                continue
            name = path.relative_to(source).as_posix()
            if path.suffix != ".md" or any(part.startswith(".") for part in path.relative_to(source).parts):
                raise ValueError("Skill 源只允许显式维护的 Markdown 资料")
            payload[name] = path.read_bytes()
        for name, data in payload.items():
            for link in re.findall(r"\]\(([^)]+)\)", data.decode("utf-8")):
                url = urlsplit(link)
                if url.scheme or not url.path:
                    continue
                target = (source / name).parent / unquote(url.path)
                if not target.resolve().is_relative_to(source.resolve()) or not target.exists():
                    raise ValueError(f"Skill 内部链接缺失或越界: {name}: {link}")
        self._stage = tempfile.TemporaryDirectory(prefix="dev-workflow-skill-build-")
        stage = Path(self._stage.name)
        for name, data in payload.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        destination = "skill-source"
        if self.target_name == "wheel":
            manifest = {
                "schema": 1,
                "owner": "dev-workflow-standards-tools",
                "skill": "dev-workflow-standards",
                "version": self.metadata.version,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()},
            }
            (stage / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
            )
            destination = "dev_workflow_standards_tools/skill_bundle"
        build_data.setdefault("force_include", {})[str(stage)] = destination

    def finalize(self, version, build_data, artifact_path):
        self._stage.cleanup()
