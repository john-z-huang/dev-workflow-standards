# 工作流导航

只做文档选择，不增加授权。匹配后只读取最相关的工作流；工作流无法解决时，再按下表查找参考文档。

## 按场景选择工作流

| 场景 | 读取 |
|---|---|
| 无 remote、无需 GitHub、只要本地结果 | [`standard-development.md`](standard-development.md) |
| Git 仓库有可同步 remote，需要隔离开发 | [`worktree-development.md`](worktree-development.md) |
| Issue、推送、PR 或合并 | [`github-delivery.md`](github-delivery.md) |
| 测试、提交前检查、PR 审计、合并后清理 | [`verification-and-cleanup.md`](verification-and-cleanup.md) |
| Hook、自动化、历史标题重写 | [`special-operations.md`](special-operations.md) |
| 阻塞、冲突、失败或无法安全继续 | [`recovery-and-exceptions.md`](recovery-and-exceptions.md) |

## 按问题选择参考文档

| 遇到的问题 | 读取 |
|---|---|
| remote、worktree、未跟踪文件、空远端、串行交付或合并后 worktree 状态 | [`../references/worktree.md`](../references/worktree.md) |
| 依赖未合并分支，需要确定 PR 的 base/head | [`../references/stacked-pr.md`](../references/stacked-pr.md) |
| GitHub 网络、认证、Issue、标签、assignee 或 PR 流程 | [`../references/github.md`](../references/github.md) |
| PR 合并到 `main` 的方式 | [`../references/squash-merge.md`](../references/squash-merge.md) |
| 创建 PR 前检查 Issue、关联关系或 base/head | [`../references/check-pr-policy.md`](../references/check-pr-policy.md) |
| 本地代码探索、逻辑分析、符号引用和调用链 | [`../references/code-understanding.md`](../references/code-understanding.md) |
| 手动处理已合并 PR 的本地分支 | [`../references/merge-cleanup.md`](../references/merge-cleanup.md) |
| 用脚本自动处理 PR 合并后的清理 | [`../references/pr-merge-cleanup.md`](../references/pr-merge-cleanup.md) |
| 分支名不符合项目约定 | [`../references/check-branch-name.md`](../references/check-branch-name.md) |
| Commit message 不符合格式或含禁止署名 | [`../references/check-commit-message.md`](../references/check-commit-message.md) |
| 暂存区范围、空白错误或提交前测试 | [`../references/check-staged-changes.md`](../references/check-staged-changes.md) |
| 将校验脚本和 Hook 接入目标项目 | [`../references/hooks.md`](../references/hooks.md) |
| Git 元数据写权限或沙箱限制 | [`../references/environment.md`](../references/environment.md) |
| 查找可复用的自动化脚本及其调用方式 | [`../references/automation-index.md`](../references/automation-index.md) |
| 获准重写历史提交标题 | [`../references/rewrite-weather-commit-subjects.md`](../references/rewrite-weather-commit-subjects.md) |

若问题仍无法归类，停止操作，保留现场并请求最小的补充信息或授权。

## Completion Gate

- 目标和批准范围已满足；
- 适用步骤、references 和验证已完成；
- 文件、worktree、分支、暂存区和 GitHub 状态已核验；
- 未验证、跳过、失败和阻塞项已明确标记；
- 未泄露凭据，未添加 Agent 署名/生成声明；
- 当前状态为 `COMPLETE`，否则只能报告具体阻塞。
