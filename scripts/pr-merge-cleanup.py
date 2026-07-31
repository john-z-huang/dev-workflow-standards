#!/usr/bin/env python3
"""PR 合并后清理脚本

在 Pull Request 合并后，自动执行以下清理流程：
1. 确认指定 PR 已在 GitHub 上合并
2. 切换到本地 main 分支
3. 拉取远端 main 分支最新更新
4. 删除本地特性分支

用法:
    python3 pr-merge-cleanup.py <PR编号> [<特性分支名称>]

参数:
    PR编号        GitHub Pull Request 编号（必填）
    特性分支名称   需要删除的本地分支名称（可选，默认自动从 PR 信息获取）

示例:
    python3 pr-merge-cleanup.py 42
    python3 pr-merge-cleanup.py 42 feat/add-validation

退出码:
    0  清理成功
    1  参数错误或前置条件不满足
    2  PR 尚未合并
    3  Git 操作失败

依赖:
    - git（已安装并配置）
    - gh CLI（已安装并完成认证）
"""

import argparse
import json
import subprocess
import sys


def run_command(cmd, check=True):
    """执行 shell 命令并返回结果"""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip() or "命令执行失败"
        print(f"错误: {' '.join(cmd)} 执行失败 (退出码 {result.returncode})", file=sys.stderr)
        if error_msg:
            print(f"  详情: {error_msg}", file=sys.stderr)
        sys.exit(3)
    return result


def check_pr_merged(pr_number):
    """检查指定 PR 是否已合并，返回 PR 信息字典"""
    result = run_command([
        "gh", "pr", "view", str(pr_number),
        "--json", "state,mergedAt,headRefName,title",
    ])
    pr_info = json.loads(result.stdout)

    if pr_info.get("state") != "MERGED":
        print(f"PR #{pr_number} 尚未合并（当前状态: {pr_info.get('state', '未知')}）", file=sys.stderr)
        sys.exit(2)

    print(f"✓ PR #{pr_number} 已合并: {pr_info.get('title', '无标题')}")
    return pr_info


def ensure_clean_working_tree():
    """确认工作区干净，无未提交变更"""
    result = run_command(["git", "status", "--porcelain"])
    if result.stdout.strip():
        print("错误: 工作区存在未提交的变更，请先提交或暂存后再执行清理", file=sys.stderr)
        sys.exit(1)


def switch_to_main():
    """切换到 main 分支"""
    run_command(["git", "checkout", "main"])
    print("✓ 已切换到 main 分支")


def pull_latest():
    """拉取远端 main 分支最新更新"""
    run_command(["git", "pull", "origin", "main"])
    print("✓ 已拉取远端 main 分支最新更新")


def delete_branch(branch_name):
    """删除本地特性分支"""
    current = run_command(["git", "branch", "--show-current"])
    if current.stdout.strip() == branch_name:
        print(f"警告: 当前处于 {branch_name} 分支，跳过删除", file=sys.stderr)
        return

    result = run_command(["git", "branch", "-d", branch_name], check=False)
    if result.returncode != 0:
        print(f"警告: 无法删除分支 {branch_name}（可能已删除或包含未合并提交）", file=sys.stderr)
        if result.stderr:
            print(f"  详情: {result.stderr.strip()}", file=sys.stderr)
        return

    print(f"✓ 已删除本地分支 {branch_name}")


def main():
    parser = argparse.ArgumentParser(
        description="PR 合并后清理：确认合并状态、同步 main、删除本地特性分支",
    )
    parser.add_argument(
        "pr_number",
        type=int,
        help="GitHub Pull Request 编号",
    )
    parser.add_argument(
        "branch",
        nargs="?",
        default=None,
        help="需要删除的本地分支名称（可选，默认从 PR 信息自动获取）",
    )
    args = parser.parse_args()

    ensure_clean_working_tree()

    pr_info = check_pr_merged(args.pr_number)

    branch_name = args.branch or pr_info.get("headRefName")
    if not branch_name:
        print("错误: 无法确定特性分支名称，请手动指定", file=sys.stderr)
        sys.exit(1)

    switch_to_main()
    pull_latest()
    delete_branch(branch_name)

    print("\n清理完成！")


if __name__ == "__main__":
    main()
