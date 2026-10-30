# Git Worktree 工作流

仅当用户在当前指令中明确要求 worktree 时适用；remote、GitHub 交付、分支或并行任务都不会单独触发。固定写操作和强制 Git 门禁用 [`mcp-tools.md`](../references/mcp-tools.md) 指定的工具；补充只读查询按 [`read-only-queries.md`](../references/read-only-queries.md) 处理，不能代替成功同步。操作细节与例外见 [`worktree.md`](../references/worktree.md)；Fork 拓扑见 [`fork-maintenance.md`](../references/fork-maintenance.md)。

原始工作区只用于同步基线和管理 worktree。需求代码、测试、文档、暂存与提交都在对应需求 worktree 中完成。同步、隔离、清理均须符合用户授权及项目权限；创建 worktree 不自动授权提交或 GitHub 操作。

## 队列

| 步骤 | 完成条件 |
|---|---|
| 记录未跟踪内容 | 逐项路径和内容指纹已保存 |
| 审计并同步基线 | remote、默认分支、Fork 状态和工作区已核验，快进同步成功 |
| 创建 worktree | 新目录和分支基于批准的最新基线 |
| 携带未跟踪文件 | 按指纹安全复制，无覆盖 |
| 在 worktree 中实现 | 代码修改和验证均位于需求 worktree |
| 串行交付 | 一个工作项集成后，再同步基线和处理下一个 |
| 合并后状态 | 默认保留 worktree 与本地分支 |

## 1. 记录未跟踪文件

先调用 `capture_untracked_file_manifest`，传入原始工作区的绝对 `repo_path`。工具返回未忽略普通文件的相对路径、SHA-256 和大小；按需求归属分类并保留返回清单。符号链接、特殊文件和 ignored 文件不由该工具复制；对这些内容保留现场并按 [`worktree.md`](../references/worktree.md) 处理，不擅自删除或覆盖。

## 2. 审计并同步基线

调用 `audit_repository_state` 确认仓库、remote、实际默认分支、当前分支、跟踪改动和 Fork `parent`。若有已跟踪未提交内容或无法安全切换/同步，停止并保留现场。

- 普通仓库：调用 `switch_repository_branch` 切到实际默认分支，然后调用 `pull_origin_branch_fast_forward` 快进同步 `origin` 同名分支。
- 个人 Fork：依序调用 `fetch_upstream_branch`、切换到 `main`、`merge_upstream_branch_fast_forward`，再在 `main` 调用 `push_fork_main_fast_forward`；随后切到已核验的个人维护分支。若维护分支存在保护或同步拓扑不明确，停止并读取 [`fork-maintenance.md`](../references/fork-maintenance.md)。
- 未跟踪文件冲突、网络/认证失败、非快进、权限不足或同步结果不确定时，立即停止；不得使用旧 remote-tracking 信息、SHA 或旧分支绕过同步门禁。

只有在最新基线确认同步成功后，才能继续创建需求 worktree。

## 3. 创建并准备 worktree

先用 `check_branch_names` 检查分支名，再用 `list_repository_worktrees` 确认分支未被其他 worktree 使用。调用 `create_repository_worktree` 时明确传入原仓库 `repo_path`、目标绝对路径、唯一分支名和起始基线。普通仓库从刚同步的默认分支创建；Fork 从刚同步的个人维护分支创建。依赖分支只在上层流程已明确批准时使用。

创建成功后，调用 `copy_untracked_files_to_worktree`，将初始清单里允许携带的文件按相对路径复制。工具拒绝覆盖并复核源内容指纹；失败时停止，不手动覆盖。原始工作区副本继续保留，文件不自动暂存或提交。

## 4. 实现与串行交付

在需求 worktree 中实现并按要求验证。只有用户授权暂存和提交时，才用 `stage_repository_paths` 指定完整文件，再用 `commit_repository_changes` 提交；工具只支持整文件暂存。多个 worktree 可以并行实现，但共享同一基线的交付必须串行：先完成一个工作项的验证、提交、推送和 PR 集成，再回原始工作区快进同步实际 base；随后在下一个需求 worktree 调用 `rebase_repository_branch`，传入该 worktree 的 `repo_path`、当前 `branch_name` 和已同步的 `base_branch`，再重验。冲突需要新业务或架构决定时先暂停。

合并后默认保留 worktree 与本地分支，不 checkout、pull、merge、rebase、delete 或移除已集成的需求 worktree。只有用户另行明确要求移除 worktree 时才调用 `remove_repository_worktree`；它只移除干净的 worktree 目录，不删除分支。若需清理分支，另按 [`verification-and-cleanup.md`](verification-and-cleanup.md) 中的 PR 清理工具处理。若对应工具不可用，停止并报告，不用手写删除命令替代。

## 空远端例外

远端确认为空、没有默认分支或没有 PR base 时，先按用户授权处理最小 bootstrap；bootstrap 不得包含需求内容。当前 MCP 工具不覆盖的 bootstrap 操作必须停止并报告所缺的专用能力，不得把需求文件混入初始化提交。
