# MCP 工具目录

本项目支持通过本机 Codex 配置使用 Python MCP 服务 `dev-workflow-standards-tools`。固定 Git/GitHub 操作只用本表所列的专用工具，不传 shell、git、gh 或测试命令。所有 repo-bound 工具都要求本次目标仓库的绝对 `repo_path`，且只在该 Git 根目录/worktree 内操作；不要假设 MCP 进程启动目录就是目标项目。

只读工具带 `read_only_hint`；其他工具带写入/破坏性注解，Codex 服务配置为 `default_tools_approval_mode="writes"`。这些确认与注解不取代 Skill 中的用户授权前置条件。`gh` 工具使用本机已授权的 GitHub CLI，不接受或输出令牌。

## OpenAI 判断与生成

以下工具通过 OpenAI Python SDK 调用固定的 `gpt-6-luna`，每次强制读取并显式使用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`，不提供模型或配置覆盖参数。API 工具具有 `open_world_hint=true`、`idempotent_hint=false`；只读注解表示不修改本地或 GitHub 资源，不表示没有外部 API 请求。接口失败、未知分支、拒绝或未完成的生成不能当作成功结果。

| 工具 | 输入 | 返回 |
|---|---|---|
| `decide_skill_workflow` | 强类型 `request`：用户请求、明确 worktree、GitHub 交付、仅验证、特殊操作和阻塞条件 | Decisions 固定选项中的工作流分支，供 Agent 核对后采用。 |
| `decide_codex_session_action` | 强类型 `request`：历史读取状态、事实覆盖、保存限制和新增事实来源 | Decisions 的查询与持久化分支；不能用当前新事实更新历史摘要。 |
| `generate_skill_content` | 强类型 `request`：内容种类、用户要求、带引用的证据、查询重点、输出格式及可选会话来源 | Responses 结构化生成的标题、正文、引用、缺失事实与审阅说明，供 Agent 优化或采纳。 |

`check_branch_names`、`check_commit_message`、`audit_issue_pr_policy` 的公开参数保持不变：先执行原本地硬校验，通过后再调用 Decisions。API 结果不能放宽本地失败，API 不可用时不能默认为通过。其余精确计算、Git 写操作和 Hook 不迁移到模型。详细输入范式、Instruction Prompt、强度配置及错误边界见 [`openai-workflow-tools.md`](openai-workflow-tools.md)。

## Codex 会话事实辅助工具

这三个工具均为只读，不访问 Codex 原始会话、不发起网络请求、不调用 Serena，也不保存摘要。前两个是纯输入处理，不需要 `repo_path`；第三个必须显式传入目标仓库/worktree 的绝对根路径。默认问题与模板随 Python 包发布，不依赖服务启动目录。

| 工具 | 输入 | 用途 |
|---|---|---|
| `get_codex_session_summary_guidance` | `custom_questions?`, `custom_template?` | 返回默认阅读清单和 Markdown 模板；自定义问题或模板替换对应默认内容，不强加默认章节。 |
| `order_codex_session_sources` | `sources` | 对来源去重并按创建时间倒序分组；缺时间、时间相等或同一会话元数据冲突时标明歧义，不推断优先级。 |
| `prepare_codex_session_memory` | `repo_path`, `source`, `summary`, `evidence_refs`, `topic?`, `persistence_allowed?`, `existing_memory_name?` | 校验项目、来源和安全名称，生成 Serena `write_memory` 的参数。用户禁止保存时跳过，不生成写入载荷。已有记录可保留原名。 |

`source`/`sources` 的必填字段为 `source_link`，可选字段为 `thread_id`、`created_at`、`ended_at`、`title`。这些数据由调用者从宿主会话读取结果提取。链接严格使用 `codex://threads/<小写标准UUID>`；时间使用带时区、包含秒且小数最多六位的 ISO 8601，缺少结束元数据时不推算结束时间。工具只检查调用者提供的数据，不证明这些元数据来自宿主，也不证明事实或证据引用真实。时间排序只用于已读取来源的事实优先级，不能据此宣布原会话没有相关事实或允许跳过原文查询。

排序工具返回 `priority_groups`、`missing_created_at`、`ambiguities` 和 `ready`；`ready=false` 表示需要澄清，不能把组内列表顺序当作优先级。同一会话的冲突元数据会报错。准备工具在允许保存时另要求非空 `title`、明确的 `created_at`、非空 `summary` 和 `evidence_refs`；成功返回 `status=prepared` 及 `payload={memory_name, content}`，禁止保存时返回 `status=skipped`、`payload=null`，项目路径校验失败时返回 `ok=false`、`error`、`payload=null`。

`summary` 是 Code Agent 按默认模板或用户指定结构撰写的完整 Markdown 文档。准备工具令 `payload.content` 与其精确一致，来源元数据单独放在响应的 `metadata`；其中 `memory_project_root` 只表示当前 Serena 的目标项目，不能当作原会话的 `project_scope`。Code Agent 必须逐项核对 `evidence_refs` 与原会话，确保未混入当前会话的新事实。默认 `topic` 为 `codex-sessions`，禁止绝对路径、路径穿越和 `global` 跨项目主题；主题每段最多 100 个 UTF-8 字节，已有条目的名称须为同主题下以相同 thread ID 结尾的安全名称，并计入 Serena 自动添加的 `.md` 长度。`persistence_allowed` 只是调用参数，不能替代用户指令或实际权限。

调用顺序：宿主 `read_thread` 读取来源 → 获取清单/模板并按用户要求总结 → 去重并处理优先级歧义 → Serena 激活准确项目、读取维护说明及已有记录 → 准备写入参数 → Serena `write_memory` → `read_memory` 回读。用户禁止持久化时仅只读参考；本工具不会绕过该限制。完整规约见 [`codex-session-facts.md`](codex-session-facts.md)。

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
