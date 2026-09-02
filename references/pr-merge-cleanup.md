# PR 合并后清理脚本

## 功能描述

在 Pull Request 合并后，自动执行标准化清理流程：确认 PR 合并状态，读取 PR 实际 base/head，使用 fast-forward-only 模式同步 base 分支，并删除本地已合并 head 分支。该流程对应 SKILL.md 中「PR 合并后」检查清单中的操作步骤。

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

## 集成方式

- **人工或自动化流程调用**：PR 合并后执行 `python3 scripts/pr-merge-cleanup.py <PR编号>` 完成清理。
- **Git Hooks**：可在自定义 hook 脚本中调用，但注意 `git` hook 无法自动获取 PR 编号，需额外传参。
- **CI/CD**：在 PR 合并触发的 CI 流水线末尾添加清理步骤（适用于需要清理本地工作区的场景）。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 清理成功 |
| 1 | 参数错误或前置条件不满足（如工作区不干净） |
| 2 | PR 尚未合并 |
| 3 | Git、gh 命令或删除本地分支失败 |
