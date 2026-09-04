#!/usr/bin/env python3
"""为历史天气数据项目提交标题补充统一的类型前缀。

该脚本作为 ``git filter-branch --msg-filter`` 的消息过滤器使用。它只从标准输入
读取一条完整的 Git 提交信息，将第一行标题按精确映射替换后输出到标准输出；不
直接修改 Git 引用，也不改动提交正文或文件树。

用法示例:

    FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f \\
      --msg-filter 'python3 scripts/rewrite_weather_commit_subjects.py' \\
      -- main

历史重写会生成新的 commit SHA。只应在已经确认分支范围、远端协作影响和备份
策略后使用。标题已经符合格式时脚本会原样输出，便于重复执行或检查新旧历史。
"""

from __future__ import annotations

import re
import sys


SUBJECTS = {
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

PREFIXED_SUBJECT = re.compile(
    r"^(?:feat|fix|docs|refactor|test|chore|perf|build|ci):\s+\S.*$"
)


def rewrite(message: str) -> str:
    """替换提交标题，保留正文、注释和原始换行。"""
    lines = message.splitlines(keepends=True)
    for index, line in enumerate(lines):
        subject = line.rstrip("\r\n")
        if not subject.strip() or subject.lstrip().startswith("#"):
            continue

        normalized_subject = subject.strip()
        replacement = SUBJECTS.get(normalized_subject)
        if replacement is None:
            if PREFIXED_SUBJECT.fullmatch(normalized_subject):
                return message
            raise SystemExit(f"未配置提交标题映射: {subject!r}")

        ending = line[len(subject) :]
        lines[index] = replacement + ending
        return "".join(lines)

    raise SystemExit("提交信息没有可用标题")


if __name__ == "__main__":
    sys.stdout.write(rewrite(sys.stdin.read()))
