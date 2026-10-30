"""独立 Skill 管理入口；不导入或启动 MCP/OpenAI，不读取凭据。"""

import argparse
import json
import sys

from .services.skill_installation import SkillError, manage_skill


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线安装或显式更新开发规范 Skill；不注册 MCP 或安装 Hook")
    groups = parser.add_subparsers(dest="group", required=True)
    skills = groups.add_parser("skills", help="安装、查看及更新独立 Skill 快照")
    commands = skills.add_subparsers(dest="action", required=True)
    for action, help_text in (
        ("install", "安装到不存在的目录；拒绝覆盖任何已有目标"),
        ("update", "仅更新完整且未修改的受管安装"),
        ("show", "只读查看包版本、目标状态和已安装版本"),
    ):
        command = commands.add_parser(action, help=help_text)
        command.add_argument("--target", help="完整目标目录；默认 ~/.agents/skills/dev-workflow-standards")
        if action != "show":
            command.add_argument("--dry-run", action="store_true", help="完整预检但不创建目录、锁或文件")
    args = parser.parse_args(argv)
    try:
        result = manage_skill(args.action, args.target, dry_run=getattr(args, "dry_run", False))
    except SkillError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
