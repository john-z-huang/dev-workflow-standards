# dev-workflow-standards

此项目将开发规范拆为两层：Skill 文档保留场景分析、顺序、授权与验收；本地 Python MCP 服务执行固定 Git/GitHub 操作。MCP 使用官方 Python SDK v2 与 stdio transport，项目依赖由 `uv` 管理。

## Codex 中安装

在本仓库根目录执行：

```bash
uv tool install --editable ./mcp-server
codex mcp add \
  -c 'mcp_servers.dev-workflow-standards-mcp.default_tools_approval_mode="writes"' \
  dev-workflow-standards-mcp -- "$(uv tool dir --bin)/dev-workflow-mcp"
codex mcp list
```

`writes` 会要求 Codex 确认未标记为只读的工具。Skill 的用户授权规则仍然适用；MCP 注解和 Codex 确认都不能替代任务语境中的授权。CLI 写入的 MCP 配置由 Codex 桌面端、CLI 和 IDE 共享；若当前桌面会话尚未加载新服务，重启或新开会话后使用。

editable uv tool 指向本地 `mcp-server/` 源码；移动或归档其所在 worktree 前，应先将工具重新安装到稳定路径。

本次开发保留在独立 worktree 中。已注册的 MCP server 指向该 worktree；`~/.agents/skills/dev-workflow-standards` 下的活动 Skill 文档要等本分支集成后才会切换到此版本。集成前不要归档该 worktree。

## 使用

使用 [`SKILL.md`](SKILL.md) 时按 [`workflows/index.md`](workflows/index.md) 选择工作流，再按 [`references/mcp-tools.md`](references/mcp-tools.md) 调用对应工具。所有仓库操作都要传入本次目标项目的绝对 `repo_path`；服务器不会把启动时的目录当作目标仓库。

Git/GitHub 写操作必须先满足工作流中的用户授权和安全前置条件。服务只接受固定领域参数，不提供任意 shell、git、gh 或项目测试命令。工具未覆盖的操作要停止并报告，不要改用手写命令绕过。

## 项目结构

- `SKILL.md`：短入口、共用边界和加载顺序。
- `workflows/`：保留场景判断、先后依赖、授权和完成条件。
- `references/`：按需加载的决策细节和 MCP 工具名/参数映射。
- `mcp-server/`：Python/uv 项目、MCP v2 stdio 服务和固定操作工具。
- `scripts/`、`.githooks/`：供标准 Git Hook 集成使用的可移植校验资产。

MCP 服务实现与调用约束见 [`mcp-server/pyproject.toml`](mcp-server/pyproject.toml) 和 [`references/mcp-tools.md`](references/mcp-tools.md)。
