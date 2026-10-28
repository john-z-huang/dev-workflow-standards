# GitHub 交付工作流

固定写操作和强制 GitHub 门禁使用 [`mcp-tools.md`](../references/mcp-tools.md) 中点名的工具；查询优先用 MCP 或已授权 Connector，未覆盖的只读信息按 [`read-only-queries.md`](../references/read-only-queries.md) 使用 CLI。禁止浏览器/浏览器自动化。加载本工作流本身不授予 GitHub 写入权限；用户明确要求推送时，按本流程补齐缺失 Issue、推送分支并创建关联 PR，不再另行询问，但不自动合并或关闭 PR。

操作策略见 [`github.md`](../references/github.md)、Fork 拓扑见 [`fork-maintenance.md`](../references/fork-maintenance.md)、合并策略见 [`squash-merge.md`](../references/squash-merge.md)。

## 队列

| 步骤 | 完成条件 |
|---|---|
| 确认仓库与访问 | 仓库、Fork 状态、网络和认证已确认 |
| 准备 Issue | 开放 Issue、工作类型 label、本人 assignee 已核验 |
| 推送 | 本地门禁通过，目标分支和授权正确 |
| 创建/审计 PR | 关联、base/head、assignee 与开放状态已核验 |
| 合并 | 用户已授权且合并策略、required checks 已核验 |

## 1. 确认仓库和访问

- 调用 `audit_repository_state`，传入目标仓库绝对 `repo_path`，确认仓库身份、remote、实际默认分支和 Fork `parent`。
- 先确认目标仓库、Issue/PR、base/head；不猜 owner、用户名、编号或权限。
- 网络或认证失败时按 [`recovery-and-exceptions.md`](recovery-and-exceptions.md) 停止。令牌不得输出、回显、插值、记录、写入或要求用户粘贴；不得因 CLI 受阻改用浏览器。
- 个人 Fork 的 remote、个人维护分支和保护规则按 [`fork-maintenance.md`](../references/fork-maintenance.md) 判定；保护规则等未覆盖的信息可按只读规约回读。写工具或强制门禁工具未提供时仍停止并报告，不手写命令绕过。

## 2. 准备 Issue

推送前必须有开放 Issue。用户明确要求推送时，如果没有相关联的开放 Issue，先创建并核验。

1. 调用 `list_github_issue_labels` 读取现有分类；根据 Issue 主要目的选取至少一个已有工作类型 label。
2. 整理描述，至少说明需求/缺陷、影响范围和验收标准；必要时补充复现、约束和依赖。
3. 获得用户对创建 Issue 的授权后，调用 `create_github_issue`，传入 `repo_path`、标题、完整正文和已存在的工作类型 labels。工具默认指派本人，并在创建后回读核验。
4. 若标签枚举、创建或回读失败，按工具结果停止并修复；没有可验证的分类标签时不得推送。

## 3. 推送

推送前确认用户已授权，且仓库、`repo_path`、分支、remote、开放 Issue、label、本人 assignee、适用验证、提交范围和堆叠 PR base 均正确。提交须已通过 `stage_repository_paths` 与 `commit_repository_changes`。调用 `push_issue_branch_to_origin` 将已提交的当前分支推送到 `origin`；该工具只允许非强制推送，并核验 Issue 前置条件。Fork 的同步 `main` 使用单独的 `push_fork_main_fast_forward`，不得把需求分支推到 `main`。

## 4. 创建/检查 PR

- 用户明确要求推送时，推送成功后创建关联 PR，保持 PR 开放。
- 明确仓库、base、head 和开放 Issue；堆叠 PR 不默认用 main。
- 整理完整 PR 描述，包含范围、验收和 `Closes #`、`Fixes #` 或 `Resolves #` 关联。获得用户授权后调用 `create_github_pull_request`；工具使用安全临时正文文件，设置本人 assignee 并回读核验。
- 创建后调用 `audit_issue_pr_policy` 核验 state、base/head 和 Issue 关联。失败时停止后续交付。

## 5. 合并

仅用户明确授权合并且 PR 可合并、required checks 通过时，才调用 `merge_github_pull_request`。该工具会远端合并并关闭 PR。`main` base 按项目规则只允许 squash；Fork 需求 PR 合并到个人维护分支，独立仓库遵循已核验策略。合并后回读实际 base 和结果；仓库策略不支持要求的方式时停止并报告。
