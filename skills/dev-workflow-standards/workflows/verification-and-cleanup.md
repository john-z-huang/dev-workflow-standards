# 验证与清理工作流

测试通过不等于范围、GitHub 策略或合并后状态通过。按队列只执行适用步骤。强制 Git 检查调用 [`mcp-tools.md`](../references/mcp-tools.md) 点名的工具；补充只读查询按 [`read-only-queries.md`](../references/read-only-queries.md) 处理，不替代门禁。项目测试仍使用项目自己的测试入口。

## 队列

| 步骤 | 结果 |
|---|---|
| 分类验证 | 本地、Hook、GitHub 与合并后检查范围已确定 |
| 确认环境 | 权限、工作区和依赖已确认 |
| 本地验证 | 适用的测试、构建、lint、类型检查已运行或标记 |
| Hook 检查 | 使用固定校验工具确认规则 |
| PR 策略 | Issue/PR 状态、关联与拓扑已核验 |
| 提交门禁 | 分支、标题、暂存范围符合要求 |
| 合并后处理 | 只执行已授权的状态更新或清理 |

## 验证范围

| 变更 | 最小验证 |
|---|---|
| 文档/机械 | Markdown、链接、引用路径 |
| 行为/修复 | 有意义的测试；按风险增加构建、lint、类型、集成/回归 |
| 脚本/Hook | 成功、失败、参数错误、退出码、副作用 |
| GitHub | Issue/PR 状态、关联、base/head、label、assignee、策略 |

项目自定义测试和检查只从项目本身确认命令，不把任意命令交给 MCP 工具。未运行的检查标记 `SKIPPED`，失败标记 `FAIL`；不得写成通过。

## 本地校验工具

- `check_branch_names`：检查提供的分支名；省略名称时，传入 `repo_path` 检查该仓库当前分支。
- `check_commit_message`：检查标题格式、中文说明和禁止的工具署名；只传待检查文本，不触碰 Git 状态。
- `check_staged_changes`：对 `repo_path` 的暂存区执行固定空白检查，不运行测试。
- `stage_repository_paths`：只有用户授权后，按显式完整文件路径暂存；拒绝已有 staged 内容和范围不符。它不支持部分 hunk。
- `commit_repository_changes`：只有用户授权后，在 staged 路径与 `expected_paths` 完全一致、提交信息合规且暂存区无空白错误时创建提交。

Hook 接入和 `--no-verify` 规则见 [`hooks.md`](../references/hooks.md)。Serena 诊断仅辅助定位，不能替代测试、构建或集成验证；代码理解见 [`code-understanding.md`](../references/code-understanding.md)。

## PR 策略

创建 PR 或请求审核前调用 `audit_issue_pr_policy`，传入 `repo_path` 与 Issue/PR 编号，并按实际拓扑提供预期 base/head。检查不通过时停止推送、请求审核或合并，按 [`github-delivery.md`](github-delivery.md) 修正。

## 合并后清理

worktree 工作流默认保留已集成的 worktree 和本地分支。其他场景只有用户明确要求清理时，才调用 `cleanup_merged_pr_local_branch`；该工具会切换到实际 base、快进同步并删除本地 head，详细前置条件与副作用见 [`pr-merge-cleanup.md`](../references/pr-merge-cleanup.md)。不自动删除远端分支或 worktree。
