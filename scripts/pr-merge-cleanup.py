#!/usr/bin/env python3
"""PR 合并后清理脚本。

在 Pull Request 合并后，自动执行以下清理流程：
1. 确认指定 PR 已在 GitHub 上合并
2. 从 PR 信息读取并切换到实际 base 分支
3. 以 fast-forward-only 模式拉取 base 分支最新更新
4. 删除本地已合并 head 分支

用法:
    python3 pr-merge-cleanup.py <PR编号> [<特性分支名称>] [--repo owner/repo]

参数:
    PR编号        GitHub Pull Request 编号（必填）
    特性分支名称  需要删除的本地分支名称（可选，必须与 PR head 一致）
    --repo        GitHub 仓库，格式为 owner/repo（可选，默认使用当前目录）

示例:
    python3 pr-merge-cleanup.py 42
    python3 pr-merge-cleanup.py 42 feat/add-validation
    python3 pr-merge-cleanup.py 42 --repo owner/repo

退出码:
    0  清理成功
    1  参数错误或前置条件不满足
    2  PR 尚未合并
    3  Git 或 gh 命令执行失败

依赖:
    - git（已安装并配置）
    - gh CLI（已安装并完成认证）
"""

import argparse
import json
import subprocess
import sys


def run_command(cmd, check=True):
    """执行命令并返回结果。"""
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


def check_pr_merged(pr_number, repo=None):
    """检查指定 PR 是否已合并，返回 PR 信息字典。"""
    command = ["gh", "pr", "view", str(pr_number)]
    if repo:
        command.extend(["--repo", repo])
    command.extend(["--json", "state,mergedAt,baseRefName,headRefName,title"])

    result = run_command(command)
    try:
        pr_info = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("错误: gh 返回了无效的 PR JSON 信息", file=sys.stderr)
        sys.exit(3)

    if pr_info.get("state") != "MERGED":
        print(
            f"PR #{pr_number} 尚未合并（当前状态: {pr_info.get('state', '未知')}）",
            file=sys.stderr,
        )
        sys.exit(2)

    if not pr_info.get("baseRefName") or not pr_info.get("headRefName"):
        print(f"错误: PR #{pr_number} 缺少 base/head 分支信息", file=sys.stderr)
        sys.exit(1)

    print(
        f"✓ PR #{pr_number} 已合并: {pr_info.get('title', '无标题')} "
        f"({pr_info['headRefName']} -> {pr_info['baseRefName']})"
    )
    return pr_info


def ensure_clean_working_tree():
    """确认工作区干净，无未提交变更。"""
    result = run_command(["git", "status", "--porcelain"])
    if result.stdout.strip():
        print("错误: 工作区存在未提交的变更，请先提交或暂存后再执行清理", file=sys.stderr)
        sys.exit(1)


def switch_to_base(base_branch):
    """切换到 PR 实际使用的 base 分支。"""
    result = run_command(["git", "switch", base_branch], check=False)
    if result.returncode != 0:
        run_command(["git", "switch", "--track", f"origin/{base_branch}"])
    print(f"✓ 已切换到 base 分支 {base_branch}")


def pull_latest(base_branch):
    """以 fast-forward-only 模式拉取 base 分支最新更新。"""
    run_command(["git", "pull", "--ff-only", "origin", base_branch])
    print(f"✓ 已以 fast-forward-only 模式同步 origin/{base_branch}")


def delete_branch(branch_name):
    """删除已合并的本地 head 分支。"""
    current = run_command(["git", "branch", "--show-current"])
    if current.stdout.strip() == branch_name:
        print(f"错误: 当前仍处于待删除分支 {branch_name}", file=sys.stderr)
        sys.exit(1)

    result = run_command(["git", "branch", "-d", branch_name], check=False)
    if result.returncode != 0:
        print(
            f"错误: 无法删除分支 {branch_name}（可能已删除或包含未合并提交）",
            file=sys.stderr,
        )
        if result.stderr:
            print(f"  详情: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(3)

    print(f"✓ 已删除本地分支 {branch_name}")


def main():
    parser = argparse.ArgumentParser(
        description="PR 合并后清理：读取实际 base、同步 base、删除本地 head 分支",
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
        help="需要删除的本地分支名称（可选，必须与 PR head 一致）",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="GitHub 仓库，格式为 owner/repo（可选，默认使用当前目录）",
    )
    args = parser.parse_args()

    ensure_clean_working_tree()
    pr_info = check_pr_merged(args.pr_number, args.repo)

    head_branch = pr_info["headRefName"]
    if args.branch and args.branch != head_branch:
        print(
            f"错误: 手动指定分支 {args.branch!r} 与 PR head {head_branch!r} 不一致",
            file=sys.stderr,
        )
        sys.exit(1)

    branch_name = args.branch or head_branch
    base_branch = pr_info["baseRefName"]
    if branch_name == base_branch:
        print("错误: head 分支不能与 base 分支相同", file=sys.stderr)
        sys.exit(1)

    switch_to_base(base_branch)
    pull_latest(base_branch)
    delete_branch(branch_name)

    print("\n清理完成！")


if __name__ == "__main__":
    main()
