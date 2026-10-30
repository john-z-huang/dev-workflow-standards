# PR 合并后的本地清理工具

统一使用 `cleanup_merged_pr_local_branch` 清理已合并 PR 的本地 head 分支。调用前必须明确得到用户对同步 base 和删除该本地分支的授权；PR 已合并不代表已授权清理。

参数为 `repo_path`、`pr_number`，可选 `repo`、`branch_name` 和 `merged_head_oid`。工具会确认工作区干净和 PR 已合并，切换到 PR 实际 base，以 fast-forward-only 同步 `origin`，然后优先尝试普通分支删除。它不删除远端分支或 worktree。

Squash merge 可能因 ancestry 不匹配无法通过普通删除。只有在合并前保存了 `merge_github_pull_request` 返回的 `pre_merge_head_oid`，并将其作为 `merged_head_oid` 传入，且本地 head SHA 精确匹配时，工具才允许强制删除。禁止用合并后的 head SHA 代替。缺少 SHA 或匹配失败时，工具保留分支并停止。

查看 [`merge-cleanup.md`](merge-cleanup.md) 的清理顺序与部分成功后的处理方式，以及 [`mcp-tools.md`](mcp-tools.md) 中对该工具的完整说明。
