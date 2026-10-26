# 已归档的 TypeScript MCP 实现

此目录包含历史 TypeScript MCP v2 stdio 实现。该实现已归档且不再支持；它不是当前维护的 MCP 服务，也不会由当前设置安装或注册。当前维护的本机 Codex MCP 服务是 [`../../mcp-server`](../../mcp-server) 中的 Python 包，通过 `uv tool` 安装。当前工具 schema、输入、副作用和授权边界见 [`../../references/mcp-tools.md`](../../references/mcp-tools.md)。

历史 TypeScript 服务面向 Codex，需要 Node.js 20 或更高版本，并暴露与 Python 服务相同的 25 个工具名，每个名称末尾追加 `_ts`。下文仅为参考而保留工具映射和历史设置步骤。请勿使用这些步骤配置当前安装。

## 历史构建和注册说明

旧流程会在仓库根目录安装锁定的依赖并构建服务：

```bash
npm --prefix ./archive/mcp-server-ts ci
npm --prefix ./archive/mcp-server-ts run build
```

旧注册流程使用 ChatGPT Desktop 捆绑的 Node 可执行文件绝对路径，以及构建后入口文件的绝对路径。其 server id 为 `dev-workflow-standards-ts`：

```bash
CHATGPT_APP="${CHATGPT_APP:-/Applications/ChatGPT.app}"
NODE="$CHATGPT_APP/Contents/Resources/cua_node/bin/node"
test -x "$NODE" || { echo "ChatGPT Desktop bundled Node not found: $NODE" >&2; exit 1; }
SERVER="$(cd ./archive/mcp-server-ts && pwd)/dist/server.js"
codex mcp add dev-workflow-standards-ts -- \
  "$NODE" \
  "$SERVER"
```

以上仅为历史示例，并非受支持的安装流程。运行时会写入本机 Codex MCP 配置。旧说明使用 `codex mcp get dev-workflow-standards-ts` 检查该条目，并用 `codex mcp list` 列出已配置的服务。如果新服务未加载，旧说明建议重启 Codex 桌面应用。服务直接启动 `dist/server.js`，以免 npm 启动脚本横幅干扰 stdio MCP 通信。

旧开发说明还提到，可编辑安装的 Python uv tool 指向活动检出目录，而此 TypeScript MCP 注册项指向单独的 worktree。因此，旧说明建议在移动检出目录前重新安装可编辑工具，并在集成完成前保留 worktree，因为已注册的服务和活动 Skill 文档当时尚未切换。这些是特定检出目录的历史说明，不代表当前注册了 TypeScript 服务。

## 历史工具名映射

旧 TypeScript 服务在对应的 Python 工具名后追加 `_ts`。当前行为和安全说明见 [`../../references/mcp-tools.md`](../../references/mcp-tools.md)。

| Python 工具 | 历史 TypeScript 工具 |
|---|---|
| `check_branch_names` | `check_branch_names_ts` |
| `check_commit_message` | `check_commit_message_ts` |
| `check_staged_changes` | `check_staged_changes_ts` |
| `stage_repository_paths` | `stage_repository_paths_ts` |
| `commit_repository_changes` | `commit_repository_changes_ts` |
| `audit_issue_pr_policy` | `audit_issue_pr_policy_ts` |
| `cleanup_merged_pr_local_branch` | `cleanup_merged_pr_local_branch_ts` |
| `audit_repository_state` | `audit_repository_state_ts` |
| `list_github_issue_labels` | `list_github_issue_labels_ts` |
| `create_github_issue` | `create_github_issue_ts` |
| `push_issue_branch_to_origin` | `push_issue_branch_to_origin_ts` |
| `create_github_pull_request` | `create_github_pull_request_ts` |
| `merge_github_pull_request` | `merge_github_pull_request_ts` |
| `push_fork_main_fast_forward` | `push_fork_main_fast_forward_ts` |
| `list_repository_worktrees` | `list_repository_worktrees_ts` |
| `switch_repository_branch` | `switch_repository_branch_ts` |
| `pull_origin_branch_fast_forward` | `pull_origin_branch_fast_forward_ts` |
| `fetch_upstream_branch` | `fetch_upstream_branch_ts` |
| `merge_upstream_branch_fast_forward` | `merge_upstream_branch_fast_forward_ts` |
| `rebase_repository_branch` | `rebase_repository_branch_ts` |
| `remove_repository_worktree` | `remove_repository_worktree_ts` |
| `create_repository_worktree` | `create_repository_worktree_ts` |
| `capture_untracked_file_manifest` | `capture_untracked_file_manifest_ts` |
| `copy_untracked_files_to_worktree` | `copy_untracked_files_to_worktree_ts` |
| `configure_project_hooks_path` | `configure_project_hooks_path_ts` |

历史说明曾称两种实现的输入、行为和安全边界保持一致。旧工具目录记载：只读工具带有 `read_only_hint`，其他工具带有写入/破坏性注解，Codex 使用 `default_tools_approval_mode="writes"`；同时说明，这些注解和 Codex 确认均不能替代 Skill 中用户授权的前置要求。绑定仓库的工具要求目标仓库的绝对 `repo_path`，且操作范围限于该 Git 根目录/worktree。GitHub CLI 集成使用本机 `gh` 授权，不接收或返回令牌。当前以 Python 服务的说明为准；本归档不保证 TypeScript 实现仍与其兼容。
