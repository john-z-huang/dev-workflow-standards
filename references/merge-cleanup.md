# PR 合并后的本地分支清理

本文只清理已合并 PR 的本地 head 分支，不删除远端分支。同步 base 和删除本地分支都是 Git 写操作，须有用户明确授权；PR 已合并本身不构成授权。

如果 PR 计划使用 Squash merge，在合并前记录 PR head SHA。合并后查询到的 `headRefOid` 是 PR 关联 head ref 的 OID，不保证是合并时的历史快照，不能用它证明本地分支没有额外提交：

```bash
gh pr view <PR 编号> --json headRefOid --jq .headRefOid
```

保存命令输出，作为后续比较的“合并前记录的 SHA”。如果没有该记录，仍可尝试 `git branch -d`；它拒绝 Squash merge 分支时停止，不得以合并后的 `headRefOid` 代替记录。

1. **确认授权和 PR 信息**：用户明确授权同步 base 并清理本地分支后，读取 PR 状态、实际 base/head：

   ```bash
   gh pr view <PR 编号> --json state,mergedAt,baseRefName,headRefName
   ```

   只有 PR 状态为 `MERGED` 且信息完整时继续；否则停止并报告。

2. **确认工作区干净并同步 base**：若工作区有未提交变更或未跟踪文件，停止并保留现场。切换到 PR 的实际 base 分支，并只用 fast-forward-only 模式同步；不要假设 base 一定是 `main`，也不要把 base 作为清理对象。

   ```bash
   git status --porcelain
   git switch <base-branch>
   git pull --ff-only origin <base-branch>
   git status --porcelain
   ```

   两次 `git status --porcelain` 都必须无输出，且 `git pull --ff-only` 成功；否则停止。

3. **先尝试普通删除**：确认当前分支不是 PR head 后，在已同步的 base 上尝试：

   ```bash
   git branch --show-current
   git branch -d <head-branch>
   ```

   若 `-d` 成功，清理完成。若 Git 因 ancestry 不匹配拒绝删除，且 PR 确实通过 Squash merge（或其他会重写 commit ancestry 的方式）合并，继续下一步；其他错误应先报告并停止。

4. **Squash merge 使用强制删除**：重新确认 PR 仍为 `MERGED`、base 已同步、工作区仍干净、当前分支不是 head。读取本地 head SHA：

   ```bash
   git status --porcelain
   git branch --show-current
   git rev-parse --verify refs/heads/<head-branch>
   ```

   只有在用户已明确授权删除本地 head、且本地 head SHA 与合并前记录的 PR head SHA 完全一致时，才执行：

   ```bash
   git branch -D <head-branch>
   ```

   SHA 无记录、不匹配或任何前置条件不满足时停止，不得删除该分支。`-D` 只用于本地分支；不要删除远端 head 分支。

**合并前/后的命令示例**：

```bash
# 1. PR 合并前：记录 head SHA，并保留输出供合并后核验
gh pr view <PR 编号> --json headRefOid --jq .headRefOid

# 2. 用户明确授权清理后：确认 PR 已合并并读取 base/head
gh pr view <PR 编号> --json state,mergedAt,baseRefName,headRefName

# 3. 在干净工作区切换并同步实际 base
git status --porcelain
git switch <base-branch>
git pull --ff-only origin <base-branch>
git status --porcelain

# 4. 先保留普通 ancestry 检查
git branch -d <head-branch>

# 5. 仅当 -d 因 Squash merge ancestry 不匹配而失败、用户已授权，且本地 SHA
#    与步骤 1 留存的 SHA 完全一致时，才执行
git branch --show-current
git rev-parse --verify refs/heads/<head-branch>
git branch -D <head-branch>
```
