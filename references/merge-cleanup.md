# PR 合并后的本地分支清理

本文只处理已合并 PR 的本地 head 分支；PR 合并方式、worktree 状态和远端分支删除不在本文范围内。

1. **确认 PR 合并状态和分支关系**：确认 PR 状态为已合并（`MERGED`），并读取 `baseRefName` 与 `headRefName`：

   ```bash
   gh pr view <PR 编号> --json state,mergedAt,baseRefName,headRefName
   ```

   若 PR 尚未合并或状态异常，应终止后续步骤并报告原因。若工作区有未提交的变更，应先处理（提交或暂存）再切换分支。

2. **同步 base 分支**：切换到 PR 的实际 base 分支，并只用 fast-forward-only 模式拉取该分支。不要假设 base 一定是 `main`，也不要把 base 作为清理对象。

   ```bash
   git switch <base-branch>
   git pull --ff-only origin <base-branch>
   ```

3. **删除已合并 PR 的 head 分支**：在已同步的 base 分支上执行：

   ```bash
   git branch -d <head-branch>
   ```

   只删除已合并 PR 的 head 分支，不删除 PR 的 base 分支。若 `git branch -d` 报告分支未完全合并，先检查 PR 的实际合并方式和本地差异；未经用户明确授权，不得使用 `git branch -D`。远端 head 分支是否删除按仓库策略或用户明确要求处理。

**合并后命令示例**：

```bash
# 1. 确认 PR 已合并并读取 base/head
gh pr view <PR编号> --json state,mergedAt,baseRefName,headRefName

# 2. 切换到 PR 的基础分支
git switch <base-branch>

# 3. 拉取基础分支
git pull --ff-only origin <base-branch>

# 4. 删除已合并 PR 的本地 head 分支
git branch -d <head-branch>
```
