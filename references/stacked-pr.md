# 堆叠 PR 拓扑

当当前分支依赖另一条尚未合并的分支，或用户明确要求以已有功能分支作为目标时，PR 的 base 应为该基础分支，不要默认设为 `main`。

```text
main
└── agent/issue-7-session       # 基础 PR / 当前 Issue 分支
    └── agent/issue-8-runtime   # 新功能分支，PR base 为 issue-7 分支
```

## 创建与核验

1. 调用 `audit_repository_state` 并传入 `repo_path`，核实仓库、当前分支和 Fork/default-branch 信息；调用 `list_repository_worktrees` 并传入 `repo_path`，核对现有 worktree。若已知基础分支和 head 分支，从指定基础分支创建隔离 worktree 时调用 MCP 工具 `create_repository_worktree`，传入 `repo_path`、`target_worktree_path`、`branch_name` 和 `base_branch`。先经 `check_branch_names` 校验新分支名。
2. 只在 head 分支提交当前工作项；不重复提交基础分支已有改动。项目具体改动与测试仍由项目流程决定。
3. 创建 PR 时调用 MCP 工具 `create_github_pull_request`，传入 `repo_path`、`repo`、`title`、`body`、`base_branch`、`head_branch` 和 `issue_number`，显式设置预期 base/head，并确保正文关联对应 Issue。若 PR 已存在且编号已知，调用 `audit_issue_pr_policy` 显式核验 Issue、PR、预期 base/head。
4. 推送前根据 Issue 状态、标签和指派关系确认适用条件；符合时调用 `push_issue_branch_to_origin`。该工具只推送当前同名分支，不强推。

当前 MCP 服务不能列出未知 PR 编号，也不提供改 PR base、关闭错误 PR、revert、cherry-pick 或解决拓扑冲突的工具。遇到错误拓扑或无法发现对应 PR 时，保留现场并报告缺少的能力，不以任意命令绕过。

基础分支合并后，如需更新堆叠 PR 的 base，先由用户提供确切 PR 编号和新的 base，再按项目约定评估差异；目前没有自动更新 base 的工具。
