# PR 合并后的本地分支清理

清理只针对已合并 PR 的本地 head 分支；不删除远端分支。同步 base 和删除分支都是本地写操作，必须先有用户对此操作的明确授权，再调用 MCP 工具 `cleanup_merged_pr_local_branch`。必填输入为 `repo_path`、`pr_number`，可选输入为 `repo`、`branch_name` 和 `merged_head_oid`。PR 已合并本身不构成清理授权。

工具先确认工作区干净、PR 状态为 `MERGED`，然后切换到 PR 的实际 base 并执行 fast-forward 同步，再尝试普通分支删除。它不会假定 base 是 `main`，也不会删除 worktree 或远端分支。

如果普通删除因 squash merge 的 ancestry 不匹配而失败，只有 `merged_head_oid` 与本地分支当前 SHA 完全一致时才允许强制删除。该值应从成功调用 `merge_github_pull_request` 后返回的 `pre_merge_head_oid` 保存并传入。不能使用合并后的 `headRefOid` 替代合并前记录值；没有记录时工具会保留分支并停止。

工具返回的 `actions` 表示已经完成的步骤。若切换或同步 base 成功、随后删除失败，base 仍可能保持在已同步状态；检查返回结果后决定下一步。冲突、脏工作区、身份不一致或权限错误时，保留现场并报告。

先查看 [`mcp-tools.md`](mcp-tools.md) 中授权、Codex writes approval 和该工具的完整边界。
