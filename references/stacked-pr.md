# 堆叠 PR 拓扑

本文只描述“当前分支依赖另一条尚未合并分支”时的 base/head 关系；Issue 内容、标签、认证、合并和清理由上层工作流处理。

当一个功能依赖尚未合并的分支，或用户明确要求以已有功能分支作为 PR 目标时，使用堆叠 PR，不要默认将目标分支设为 `main`。

典型拓扑如下：

```text
main
└── agent/issue-7-session       # 基础 PR / 当前 Issue 分支
    └── agent/issue-8-runtime   # 新功能分支，PR base 为 issue-7 分支
```

## 创建拓扑

1. 确认基础分支、head 分支和已有 PR：`git branch -vv`、`gh pr list`、`gh pr view`。
2. 从基础分支的最新状态创建或更新 head 分支。
3. 只在 head 分支提交当前工作项；不重复提交基础分支已有改动。
4. PR 必须显式指定 base 和 head，例如：

   ```bash
   gh pr create --draft --base <base-branch> --head <head-branch> \
     --title "<title>" --body-file <pr-body-file>
   ```

5. 创建或更新后核验目标没有意外变成 `main`：

   ```bash
   gh pr view <pr-number> --json baseRefName,headRefName,state,url
   git diff <base-branch>...<head-branch> --stat
   ```

## 拓扑错误

如果已经错误地从基础分支向 `main` 发起了 PR，且该 PR 尚未合并：

- 按授权关闭错误 PR；
- 已推送到基础分支的错误提交使用 `git revert <commit>` 撤回，不改写共享分支历史；
- 推送撤回提交后，从更新后的基础分支创建新的 head 分支；
- 使用 `git cherry-pick <original-commit>` 或重新实现，将已验证的功能提交到新分支；
- 新 PR 显式设置 `--base <base-branch>`，而不是依赖 CLI 默认目标分支。

基础分支合并后，再根据仓库协作约定更新堆叠 PR 的 base；更新前先确认差异范围，并避免未经授权的强制推送。
