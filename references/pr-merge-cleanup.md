# PR 合并后清理脚本

## 功能描述

在 Pull Request 合并后，确认 PR 的 base/head，使用 fast-forward-only 模式同步 base 分支，并删除本地已合并 head 分支。

## 触发时机

- PR 在 GitHub 上完成审核并合并后
- 由 Code Agent 或开发者手动调用

## 脚本

`scripts/pr-merge-cleanup.py` — Python 3 脚本，仅依赖标准库、`git` 和 `gh` CLI。脚本不会自动删除远端 head 分支。

## 手动执行

```bash
# 自动从 PR 信息获取分支名称
python3 scripts/pr-merge-cleanup.py 42

# 手动指定分支名称
python3 scripts/pr-merge-cleanup.py 42 feat/add-validation

# 显式指定 GitHub 仓库
python3 scripts/pr-merge-cleanup.py 42 --repo owner/repo
```

## 边界

脚本只清理本地已合并 head 分支，不合并 PR、不删除远端分支，也不处理未合并分支。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 清理成功 |
| 1 | 参数错误或前置条件不满足（如工作区不干净） |
| 2 | PR 尚未合并 |
| 3 | Git、gh 命令或删除本地分支失败 |
