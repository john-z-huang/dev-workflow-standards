# Git Worktree 工作流

适用：仅当用户在当前指令中明确要求使用或创建 worktree 时。仓库存在 remote、需要 GitHub 交付、需要分支或存在并行工作项，都不会单独触发本工作流；未明确要求时按 [`standard-development.md`](standard-development.md) 在当前工作区执行。

操作细节：[`worktree.md`](../references/worktree.md)；依赖拓扑：[`stacked-pr.md`](../references/stacked-pr.md)；分支命名：[`check-branch-name.md`](../references/check-branch-name.md)；提交信息：[`check-commit-message.md`](../references/check-commit-message.md)。原始工作区只同步主分支和管理 worktree；需求实现、验证、暂存、提交在需求 worktree 中完成。

## 队列

| 步骤 | 完成条件 |
|---|---|
| 保存未跟踪清单 | 清单和指纹已保存 |
| 同步主分支 | main 上 `git pull --ff-only` 成功 |
| 创建 worktree | 新分支和 worktree 已创建 |
| 携带未跟踪文件 | 文件已复制并校验 |
| 在 worktree 中实现 | 所有需求工作都在 worktree 中 |
| 处理堆叠依赖 | base/head 拓扑已核验 |
| 串行交付 | 前一 worktree 已完成交付并同步 base |
| 合并后状态 | 按规则保留或按授权清理 |

## 1. 保存未跟踪清单

创建 worktree 前记录 `git status --short` 中每个未跟踪文件的相对路径、初始指纹和需求归属。默认不含被忽略文件；需携带被忽略文件时必须明确记录。禁止用 `git clean`、`reset`、普通 stash、删除、改名或移动消除冲突。

## 2. 同步主分支

1. 确认 remote、实际默认主分支和当前分支。
2. 确认没有妨碍切换/拉取的已跟踪未提交改动。
3. 安全切换到主分支，执行一次 `git pull --ff-only origin <main>`。
4. pull 失败、非 fast-forward、认证/网络失败、未跟踪冲突或权限不足：停止，不创建 worktree。
5. 不用过期 remote-tracking 引用、SHA 或旧本地分支替代同步。

## 3. 创建 worktree

- 分支先按 [`check-branch-name.md`](../references/check-branch-name.md) 检查；通常使用 `agent/`、`feat/`、`fix/`、`docs/` 或 `refactor/` 前缀。
- 确认分支未被其他 worktree 使用。
- 从刚同步的本地主分支创建：`git worktree add <path> -b <branch> main`。
- 原始工作区不实现、暂存或提交需求改动；worktree 不自动授予 GitHub 或 Git 写权限。

## 4. 携带未跟踪文件

pull 成功且 worktree 建立后，按清单复制相同相对路径并校验指纹；不自动暂存/提交。目标已由主分支提供时视为冲突，停止且不覆盖。原始副本继续保留。

## 5. 在 worktree 中实现

在需求 worktree 中完成代码理解、实现、验证、暂存和提交；只纳入本任务文件/hunk。进入代码理解前，按 [`code-understanding.md`](../references/code-understanding.md) 使用需求 worktree 的准确路径重新激活 Serena 项目，不得继续使用原始工作区的 Serena 上下文分析需求代码。提交信息按 [`check-commit-message.md`](../references/check-commit-message.md) 检查；推送前读取 [`github-delivery.md`](github-delivery.md)，并完成 [`verification-and-cleanup.md`](verification-and-cleanup.md) 中的适用检查。

## 6. 处理堆叠依赖

仅当用户明确要求或确实依赖未合并分支时使用；按 [`stacked-pr.md`](../references/stacked-pr.md) 核验 base/head 和差异范围。错误提交到共享分支用 `git revert`，不擅自改写历史。

## 7. 串行交付

多个 worktree 的交付顺序：一个 worktree 验证、提交、推送、建 PR并等待合并 → 原始工作区同步 base → 下一个 worktree 在自身目录 rebase、重新验证、再交付。已推送分支 rebase 仅在获授权时用 `--force-with-lease`，不用裸 `--force`。

## 8. 合并后状态

确认合并后只在原始工作区同步主分支；worktree 工作流默认不 checkout/pull/rebase/delete 已合并 worktree/分支，也不恢复或删除远端 head。需清理时必须用户明确要求。未跟踪文件先同步 main，再按清单和指纹恢复，worktree 仍保留。

## 空 remote 的例外

远端确认为空/无默认分支/无 PR base 时，只允许先用最小 README bootstrap 到 `main`；不得带入本次需求。随后原始工作区 `git pull --ff-only`，再创建需求 worktree，进入正常 Issue/验证/PR 流程。
