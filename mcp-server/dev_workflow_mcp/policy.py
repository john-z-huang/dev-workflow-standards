"""Stable repository, branch, commit and GitHub input policy."""

import re

ROOT_BRANCH_NAMES = frozenset({"main", "master"})
WORK_BRANCH_PATTERN = re.compile(
    r"^(?:(?:agent|feat|fix|docs|refactor|personal)/"
    r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*"
    r"|personal-[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
FORBIDDEN_AGENT_NAMES = (
    "codex", "claude", "antigravity", "opencode", "cursor", "copilot", "cline",
    "roo-code", "roo_code", "aider", "continue", "windsurf", "devin", "gemini",
    "cody", "junie", "kiro", "goose", "augment", "amazon-q", "amazon_q",
)
CHINESE_PATTERN = re.compile(r"[\u3400-\u9fff]")
SUBJECT_PATTERN = re.compile(r"^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$")
ATTRIBUTION_PATTERN = re.compile(
    r"(?:generated\s+(?:with|by)|created\s+with|assisted\s+by|authored\s+by|co-?authored-?by)",
    re.IGNORECASE,
)
REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
OID_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
REMOTE_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
PREFIXED_SUBJECT = re.compile(r"^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$")

LEGACY_SUBJECTS = {
    "添加数据文件检查临时脚本": "feat: 添加数据文件检查临时脚本",
    "更新 Python 数据入库规划文档": "docs: 更新 Python 数据入库规划文档",
    "更新 Z 文件 MR 字段处理": "fix: 更新 Z 文件 MR 字段处理",
    "精简 S 文件解析输出字段": "refactor: 精简 S 文件解析输出字段",
    "完成09自动站Z文件处理逻辑": "feat: 完成 09 自动站 Z 文件处理逻辑",
    "修正08自动站能见度数据CSV输出逻辑": "fix: 修正 08 自动站能见度数据 CSV 输出逻辑",
    "修复分区预警信号多预警解析": "fix: 修复分区预警信号多预警解析",
    "修改06酸雨数据处理脚本输出逻辑": "fix: 修改 06 酸雨数据处理脚本输出逻辑",
    "修复城市预报文件头兼容解析": "fix: 修复城市预报文件头兼容解析",
    "修复04全国预警CSV字段导出逻辑": "fix: 修复 04 全国预警 CSV 字段导出逻辑",
    "修复03云量观测数据处理与CSV输出": "fix: 修复 03 云量观测数据处理与 CSV 输出",
    "调整02台风最佳路径数据处理逻辑": "refactor: 调整 02 台风最佳路径数据处理逻辑",
    "添加十类气象数据 Python 处理脚本": "feat: 添加十类气象数据 Python 处理脚本",
    "完善气象数据格式盘点与处理规划": "docs: 完善气象数据格式盘点与处理规划",
    "重构开发容器配置目录": "refactor: 重构开发容器配置目录",
    "新增 Python 气象数据准备项目": "feat: 新增 Python 气象数据准备项目",
    "重命名天气数据平台核心库及命名空间": "refactor: 重命名天气数据平台核心库及命名空间",
    "将案例支持源码直接并入可执行目标": "refactor: 将案例支持源码直接并入可执行目标",
    "重构教学项目以脱离 WeatherCore 依赖": "refactor: 重构教学项目以脱离 WeatherCore 依赖",
    "整理项目目标与待办文档": "docs: 整理项目目标与待办文档",
    "更新使用的C++开发镜像的版本号": "chore: 更新 C++ 开发镜像版本号",
    "整理 CMake 迁移文档与辅助脚本": "docs: 整理 CMake 迁移文档与辅助脚本",
    "完善容器化 CMake 构建流程": "build: 完善容器化 CMake 构建流程",
    "迁移数据库教学案例并完善开发运行配置": "feat: 迁移数据库教学案例并完善开发运行配置",
    "完成天气数据平台项目拆分与迁移": "feat: 完成天气数据平台项目拆分与迁移",
    "chore: 接入 Git 提交校验脚本": "chore: 接入 Git 提交校验脚本",
}


def branch_errors(branch_name: str) -> list[str]:
    errors: list[str] = []
    if branch_name not in ROOT_BRANCH_NAMES and not WORK_BRANCH_PATTERN.fullmatch(branch_name):
        errors.append("必须是 main/master，或使用允许的类别前缀和小写连字符格式")
    hits = [name for name in FORBIDDEN_AGENT_NAMES if name in branch_name.lower()]
    if hits:
        errors.append(f"包含禁止的产品名: {', '.join(hits)}")
    return errors
