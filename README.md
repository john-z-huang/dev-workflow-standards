# dev-workflow-standards

此项目将开发规范拆为两层：Skill 文档保留场景分析、顺序、授权与验收；本地 MCP 服务执行固定 Git/GitHub 操作。当前维护的本地 MCP 服务为 Python 实现，由 `uv` 管理，并通过 `uv tool` 安装到本机供 Codex 使用。

## Codex 中安装

在本仓库根目录执行：

```bash
uv tool install ./mcp-server
codex mcp add dev-workflow-standards-tools -- "$(uv tool dir --bin)/dev-workflow-standards-tools"
codex mcp list
```

注册成功后，在 Codex 配置文件 `~/.codex/config.toml` 中生成的 `[mcp_servers.dev-workflow-standards-tools]` 段落内设置：

```toml
default_tools_approval_mode = "writes"
```

`writes` 会要求 Codex 确认未标记为只读的工具。Skill 的用户授权规则仍然适用；MCP 注解和 Codex 确认都不能替代任务语境中的授权。Codex 桌面端、CLI 和 IDE 共享该配置；若当前桌面会话尚未加载新服务，重启或新开会话后使用。

安装为普通本机 uv tool 后，工具从本机安装位置运行，不依赖仓库 worktree 路径。更新本地源码后，重新执行 `uv tool install --force ./mcp-server` 以更新安装。

### 从旧名称迁移

如果旧版本已安装并注册了 `dev-workflow-standards-mcp`，先移除旧 Codex 注册和 uv tool，再按上面的步骤安装并注册新名称。只对本机确实存在的旧条目执行移除命令：

```bash
codex mcp remove dev-workflow-standards-mcp
uv tool uninstall dev-workflow-standards-mcp
```

此迁移说明只描述命令；不会自动修改本机 Codex 配置或安装。

## 使用

使用 [`SKILL.md`](SKILL.md) 时按 [`workflows/index.md`](workflows/index.md) 选择工作流，再按 [`references/mcp-tools.md`](references/mcp-tools.md) 调用对应工具。所有仓库操作都要传入本次目标项目的绝对 `repo_path`；服务器不会把启动时的目录当作目标仓库。

Git/GitHub 写操作必须先满足工作流中的用户授权和安全前置条件。服务只接受固定领域参数，不提供任意 shell、git、gh 或项目测试命令。工具未覆盖的操作要停止并报告，不要改用手写命令绕过。

## 项目结构

- `SKILL.md`：短入口、共用边界和加载顺序。
- `workflows/`：保留场景判断、先后依赖、授权和完成条件。
- `references/`：按需加载的决策细节和 MCP 工具名/参数映射。
- `mcp-server/`：Python/uv MCP v2 stdio 服务和固定操作工具。
- `archive/mcp-server-ts/`：已归档且不再支持的历史 TypeScript MCP 实现；其历史说明见该目录的 [`README.md`](archive/mcp-server-ts/README.md)。
- `scripts/`、`.githooks/`：供标准 Git Hook 集成使用的可移植校验资产。

当前 MCP 服务实现与调用约束见 [`mcp-server/pyproject.toml`](mcp-server/pyproject.toml) 和 [`references/mcp-tools.md`](references/mcp-tools.md)。
