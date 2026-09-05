### 堆叠 PR（Stacked PR）

当一个功能依赖尚未合并的 Issue 分支，或用户明确要求以已有功能分支作为 PR 目标时，使用堆叠 PR，不要默认将目标分支设为 `main`。

典型拓扑如下：

```text
main
└── agent/issue-7-session       # 基础 PR / 当前 Issue 分支
    └── agent/issue-8-runtime   # 新功能分支，PR base 为 issue-7 分支
```

标准流程：

1. 确认基础分支、远端分支和已有 PR：`git branch -vv`、`gh pr list`、`gh pr view`。
2. 从基础分支的最新远端状态创建新分支，例如 `git switch -c agent/issue-8-runtime`。
3. 只在新分支提交当前 Issue 的代码和测试；已有基础分支的改动不重复提交。
4. 推送新分支：`git push -u origin <head-branch>`。
5. 创建 PR 时显式指定 base 和 head，例如：

   ```bash
   gh pr create --draft --base <base-branch> --head <head-branch> \
     --title "<title>" --body-file <pr-body-file>
   ```

6. PR 正文说明依赖的基础分支或基础 PR，并使用 `Closes #<issue>` 关联当前 Issue。
7. 创建后核验目标没有意外变成 `main`：

   ```bash
   gh pr view <pr-number> --json baseRefName,headRefName,state,url
   git diff <base-branch>...<head-branch> --stat
   ```

如果已经错误地从基础分支向 `main` 发起了 PR，且该 PR 尚未合并：

- 按用户授权关闭错误 PR，并保留 Issue 开放状态；
- 已推送到基础分支的错误提交使用 `git revert <commit>` 撤回，不改写共享分支历史；
- 推送撤回提交后，从更新后的基础分支创建新的 Issue 分支；
- 使用 `git cherry-pick <original-commit>` 或重新实现，将已验证的功能提交到新分支；
- 新 PR 显式设置 `--base <base-branch>`，而不是依赖 CLI 默认目标分支。

基础 PR 合并后，再根据仓库协作约定将堆叠 PR 的 base 更新到 `main` 或其他新的基础分支；更新前先确认差异范围，并避免未经授权的强制推送。
