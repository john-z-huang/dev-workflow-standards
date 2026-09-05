### PR 合并后流程

当用户在 GitHub 上完成 PR 合并后，须先根据 PR 的 base/head 分支执行清理。不要假设所有 PR 都以 `main` 为目标分支。

1. **确认 PR 合并状态和分支关系**：使用以下命令确认该 PR 在 GitHub 上的状态为已合并（`MERGED`），并读取 `baseRefName` 与 `headRefName`：

   ```bash
   gh pr view <PR 编号> --json state,mergedAt,baseRefName,headRefName
   ```

   若 PR 尚未合并或状态异常，应终止后续步骤并报告原因。若工作区有未提交的变更，应先处理（提交或暂存）再切换分支。

2. **按 base 分支选择清理目标**：

   - **普通 PR（base 为 `main`、`master` 或仓库默认分支）**：切换到该 base 分支，并拉取对应远端更新。

     ```bash
     git switch main
     git pull --ff-only origin main
     ```

   - **堆叠 PR（base 为其他未合并的功能/Issue 分支）**：切换到该 base 分支，并只拉取该分支；不要因为 PR 已合并就切换到 `main`。

     ```bash
     git switch <base-branch>
     git pull --ff-only origin <base-branch>
     ```

     base 分支是后续 PR 的依赖，必须保留，不得作为本次清理对象。

3. **删除已合并 PR 的 head 分支**：在已同步的 base 分支上执行：

   ```bash
   git branch -d <head-branch>
   ```

   只删除已合并 PR 的 head 分支，不删除堆叠 PR 的 base 分支。若 `git branch -d` 报告分支未完全合并，先检查 PR 的实际合并方式和本地差异；未经用户明确授权，不得使用 `git branch -D`。远端 head 分支是否删除按仓库策略或用户明确要求处理。

4. **继续清理上层堆叠分支**：当 base 分支后续也合并到 `main` 时，再对那个 PR 重复本流程；此时才切换到 `main`、拉取 `origin/main`，并删除该层已合并的 head 分支。

**合并后命令示例**：

```bash
# 1. 确认 PR 已合并并读取 base/head
gh pr view <PR编号> --json state,mergedAt,baseRefName,headRefName

# 2. 如果是堆叠 PR，切换到它的基础分支
git switch <base-branch>

# 3. 拉取基础分支
git pull --ff-only origin <base-branch>

# 4. 删除已合并 PR 的本地 head 分支
git branch -d <head-branch>
```
