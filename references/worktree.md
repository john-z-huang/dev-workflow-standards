# Git Worktree 开发与交付

仅当用户明确要求 worktree 时使用。Git 仓库、remote、GitHub 交付或并行任务本身不触发该模式。固定 Git 操作使用 [`mcp-tools.md`](mcp-tools.md) 中的专用工具。

## 工作区边界

- 一个完整需求使用独立 worktree 和工作分支；仅可独立审查的拆分工作项才并行。
- 原始工作区用于基线同步、查看和管理 worktree；代码、测试、配置、文档、暂存与提交都在需求 worktree 完成。
- worktree 不授权 GitHub 写入或提交。保留原始工作区现有文件和用户改动。

## 创建前的同步门禁

先用 `audit_repository_state` 检查准确仓库根目录、分支、tracked 状态、remote、默认分支和 Fork parent。已跟踪改动妨碍切换或同步时，先停止；不得暂存、清理、移动或覆盖用户内容。

- 普通仓库：`switch_repository_branch` 切换到实际默认分支，`pull_origin_branch_fast_forward` 同步同名远端分支。
- Fork：按 [`fork-maintenance.md`](fork-maintenance.md) 快进同步上游 `main`，再基于个人维护分支创建需求 worktree。
- 只有同步成功后才能创建需求 worktree；remote-tracking 引用、SHA 或旧本地分支不能代替成功同步。
- 网络、认证、权限、非快进或文件冲突失败时，保留现场并按恢复流程处理。

## 保留未跟踪文件

`capture_untracked_file_manifest` 为未忽略的未跟踪普通文件生成相对路径、SHA-256 与字节数；清单需要保留在当前任务上下文中，并标记是否属于需求。工具不包括 ignored 文件，也拒绝符号链接或特殊文件。

创建基线冲突时，不覆盖文件、不使用 reset/clean/stash，也不改名或移动。目标 worktree 建立后，用 `copy_untracked_files_to_worktree` 按清单复制；工具会再次核验源指纹、路径安全、目标仓库及目标未占用状态。若调用返回部分复制，依据 `copied` 列表核对，保留原始副本并停止继续处理失败项。文件不会自动暂存或提交。

要携带 ignored、symlink 或特殊文件时，工具无法安全搬运；保持原始副本并报告限制。需求完成后恢复无关未跟踪文件回原始工作区的跨 worktree 复制也未封装，不得猜测或覆盖。

## 创建并实现

1. 用 `check_branch_names` 校验新分支名；用 `list_repository_worktrees` 确认目标分支未被检出。
2. 用 `create_repository_worktree` 传入原仓库路径、目标绝对路径、新分支和已同步的本地基线。它拒绝已存在的路径/分支以及在源仓库目录内创建。
3. 按上一节复制允许携带的未跟踪内容；然后只在该 worktree 中实现和验证。

若 Fork 的个人维护分支缺失，先停止：当前 MCP 没有首次添加 `upstream`、创建或设置个人分支的工具。

## 并行工作与串行交付

共享同一目标基线的工作项依次集成：完成一个 worktree 的验证、提交、推送和 PR 集成后，在原始工作区同步实际 base；再在下一个尚未交付的 worktree 用 `rebase_repository_branch` 指定当前 branch 与新 base，并重新验证。冲突需要新业务/架构决定时暂停；工具不会自动继续、abort 或 reset rebase。

已集成 worktree 默认保持原状。只有用户明确要求移除时，才调用 `remove_repository_worktree`；该工具只移除干净的指定 worktree 目录，不删本地分支或远端分支。清理分支另按 [`pr-merge-cleanup.md`](pr-merge-cleanup.md) 执行。

## 空远端

空远端、无默认分支或无 PR base 时，标准同步门禁不成立。当前 MCP 没有 bootstrap README/提交/推送工具；停下并报告所缺能力，不要把需求内容混入初始化操作。
