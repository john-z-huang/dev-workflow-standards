---
name: dev-workflow-standards
description: >-
  通用开发工作流规范：按情境选择本地开发、worktree、GitHub、Fork、验证、Hook 与恢复流程；
  保留分析、顺序、权限和验收规则，并用 dev-workflow-standards MCP 的专用工具执行固定操作。
---

# 通用开发规范

本 Skill 保留场景判断、执行顺序、授权边界和完成条件。固定 Git/GitHub 操作交给本地 MCP 服务；不要自行重建这些工具已经封装的命令。

## 必须执行

1. 读取 [`workflows/index.md`](workflows/index.md)，只选择并读取适用工作流。
2. 严格按工作流顺序执行；按需读取指定的 `references/`，不要启动时通读。
3. 固定 Git/GitHub 操作使用 [`references/mcp-tools.md`](references/mcp-tools.md) 中点名的 MCP 工具，并传入本次目标仓库的绝对 `repo_path`。
4. 用户授权先于工具调用。MCP 工具的可用性或注解不构成授权；Codex 对非只读工具另行执行配置的调用确认。
5. 用户上下文相关的判断、代码/文档修改、项目自定义测试和检查继续按适用工作流处理；不得把任意 shell、git、gh 或测试命令作为 MCP 工具参数。
6. 工具缺失、仓库身份不明、权限或网络失败、结果校验失败时，停止该操作并按恢复流程报告；不要改用手写命令绕过固定工具。
7. 完成前通过工作流的 Completion Gate，核对工作区、worktree、分支和 GitHub 状态，并明确说明未验证或未覆盖项。

## 授权边界

- 加载本 Skill 不自动授权 Git 写入、Hook 配置、推送、Issue/PR、合并、删除、强制操作或历史重写。
- 用户明确要求将改动推送到 GitHub 时，按 GitHub 工作流补齐缺失 Issue 并创建关联 PR；这不授权合并或关闭 PR。
- 不输出、记录、插值、写入或要求用户粘贴令牌、密码或凭据；使用既有授权连接。
- 用户明确要求 worktree 时才使用 worktree；GitHub remote、分支需求或并行工作本身不改变默认工作区。

## 按需加载

由 [`workflows/index.md`](workflows/index.md) 决定工作流与参考文档。只有在处理固定 Git/GitHub 操作时读取 [`references/mcp-tools.md`](references/mcp-tools.md) 查找工具名和参数。
