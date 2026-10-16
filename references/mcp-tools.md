# MCP 工具目录

本地 Codex MCP 服务名为 `dev-workflow-standards-mcp`。固定 Git/GitHub 操作只用本表所列的专用工具，不传 shell、git、gh 或测试命令。所有 repo-bound 工具都要求本次目标仓库的绝对 `repo_path`，且只在该 Git 根目录/worktree 内操作；不要假设 MCP 进程启动目录就是目标项目。

只读工具带 `read_only_hint`；其他工具带写入/破坏性注解，Codex 服务配置为 `default_tools_approval_mode="writes"`。这些确认与注解不取代 Skill 中的用户授权前置条件。`gh` 工具使用本机已授权的 GitHub CLI，不接受或输出令牌。

## 检查与只读审计

| 工具 | 输入 | 用途 |
|---|---|---|
| `check_branch_names` | `branch_names?`, `repo_path?` | 校验一组分支名；不传 `branch_names` 时必须传 `repo_path`，检查当前分支。 |
| `check_commit_message` | `message` | 校验提交标题、中文说明和禁止的署名；纯文本操作。 |
| `check_staged_changes` | `repo_path` | 固定执行暂存区空白检查，不运行测试。 |
| `audit_repository_state` | `repo_path` | 读取 Git 根目录、分支、状态、remote 名称及 GitHub Fork/default branch；不输出 remote URL。 |
| `list_repository_worktrees` | `repo_path` | 读取 worktree 路径、HEAD 和分支。 |
| `capture_untracked_file_manifest` | `repo_path` | 返回未忽略未跟踪普通文件的相对路径、SHA-256 和大小；不复制/保存；拒绝符号链接和特殊文件。 |
| `list_github_issue_labels` | `repo_path`, `repo?` | 读取仓库最多 100 个现有 Issue label。 |
| `audit_issue_pr_policy` | `repo_path`, `repo?`, `issue_number?`, `pr_number?`, `expected_base?`, `expected_head?` | 只读检查 Issue/PR 开放状态、PR base/head 和正文关联；至少提供 Issue 或 PR 编号。 |
| `rewrite_legacy_commit_message` | `message` | 按已配置映射转换旧提交标题；只返回文本，不改写 Git 历史。 |

## 本地 Git 操作

这些操作均要求 Skill 前置授权。切换、拉取、合并、rebase 和复制会先检查工作区状态或身份；冲突时保留现场并停止。

| 工具 | 输入 | 固定动作与边界 |
|---|---|---|
| `stage_repository_paths` | `repo_path`, `paths` | 按显式相对文件路径暂存；拒绝绝对路径、路径穿越、目录、符号链接、重复项和已有暂存内容；只允许经过 index 核验的已跟踪删除；暂存后复核路径集合完全一致。整文件操作，不支持 hunk。 |
| `commit_repository_changes` | `repo_path`, `message`, `expected_paths` | 要求暂存路径与预期集合精确一致，提交信息符合固定格式且 `git diff --cached --check` 通过；调用固定 `git commit -m`，不跳过 hooks，并回读提交 SHA、message、文件和状态。 |
| `switch_repository_branch` | `repo_path`, `branch_name` | 切换到已存在的本地分支；tracked dirt 时拒绝。 |
| `pull_origin_branch_fast_forward` | `repo_path`, `branch_name` | 当前同名分支执行 `origin` 快进拉取；tracked changes 时拒绝。 |
| `fetch_upstream_branch` | `repo_path`, `branch_name` | 获取 `upstream` 的指定分支；要求 remote 已存在，不合并/推送。 |
| `merge_upstream_branch_fast_forward` | `repo_path`, `branch_name` | 将已获取的 `upstream` 同名分支快进合入当前同名分支；要求工作区干净。 |
| `rebase_repository_branch` | `repo_path`, `branch_name`, `base_branch` | 将指定当前分支 rebase 到本地 base；要求两分支存在且工作区干净。冲突不自动继续或回滚。 |
| `create_repository_worktree` | `repo_path`, `target_worktree_path`, `branch_name`, `base_branch` | 在不存在的绝对目标路径创建新分支/worktree；要求起点存在、分支合规且未被检出。 |
| `remove_repository_worktree` | `repo_path`, `target_worktree_path`, `branch_name` | 按精确路径和分支身份移除干净 worktree；不删除本地分支或远端分支，不强制清理。 |
| `copy_untracked_files_to_worktree` | `repo_path`, `target_worktree_path`, `manifest` | 从清单按相对路径复制到同仓库 worktree；复制前复核大小、指纹和未跟踪状态，拒绝覆盖/路径穿越/symlink。失败时可能已有部分文件复制，按返回清单检查。 |
| `configure_project_hooks_path` | `repo_path` | 要求 `.githooks/pre-commit` 和 `commit-msg` 已存在，且配置未指向其他路径；设置仓库本地 `core.hooksPath`。不复制 Hook 资产。 |

## GitHub 写操作

仅当用户意图已授权对应动作时调用。创建 Issue/PR 时传完整正文；工具以临时 body-file 调用 `gh`，创建后回读。推送不会强推；合并会关闭 PR。

| 工具 | 输入 | 前置条件 |
|---|---|---|
| `create_github_issue` | `repo_path`, `repo`, `title`, `body`, `labels` | label 必须是仓库已有且至少一个表达工作类型；创建后核验状态、labels 和本人 assignee。 |
| `push_issue_branch_to_origin` | `repo_path`, `repo`, `branch_name`, `issue_number` | 当前干净工作区位于对应非主分支；Issue 开放、有 label 且指派给当前账号；只推同名分支到 `origin`。 |
| `create_github_pull_request` | `repo_path`, `repo`, `title`, `body`, `base_branch`, `head_branch`, `issue_number` | Issue 开放、head 存在且正文含 `Closes/Fixes/Resolves #N`；创建后核验，默认指派本人并保持开放。 |
| `merge_github_pull_request` | `repo_path`, `repo`, `pr_number`, `merge_method` | PR 开放、可合并、required checks 全通过且无 changes-requested；`main` base 只允许 squash。不使用 admin/auto/delete-branch。成功执行合并后返回合并前 head OID `pre_merge_head_oid`，可供后续授权的本地清理工具核验。 |
| `push_fork_main_fast_forward` | `repo_path`, `repo` | 必须确认为 Fork，当前在干净 `main`，`upstream/main` 是 `main` 祖先；只快进推送 `origin/main`。 |
| `cleanup_merged_pr_local_branch` | `repo_path`, `pr_number`, `repo?`, `branch_name?`, `merged_head_oid?` | PR 已合并且工作区干净；切到实际 base 并快进同步，再删除本地 head。默认 `-d`；只有合并前 OID 精确匹配时才允许 `-D`。不删除远端或 worktree。 |

## 明确未封装的操作

当前没有首次添加 `upstream` remote、创建/设置个人维护分支、GitHub branch protection/rulesets、复制 Hook 资产、空远端 bootstrap、跨 worktree 恢复未跟踪文件、部分 hunk 暂存、revert，或检查/升级本地 Serena uv 工具的 MCP 工具。遇到这些步骤时保留现场，按恢复流程说明缺少的专用能力；不要用原先文档中的命令或通用命令执行器绕过。

同样不封装代码编辑、项目自定义测试、任意脚本和需要产品/架构判断的冲突解决。
