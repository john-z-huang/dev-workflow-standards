# 本地 Serena MCP 工具更新能力边界

只有用户明确要求检查或升级本机 uv 安装的 Serena 时，才考虑此流程。普通代码任务、Serena MCP 项目初始化或激活都不构成授权。

当前 dev-workflow MCP 没有读取 uv 安装来源、检查 Serena 上游版本或升级 Serena 工具的专用能力。不要根据旧安装文档改用任意 shell、Git 或 uv 命令；说明缺少专用工具并停止。即使用户要求更新，也不能把 `rewrite_legacy_commit_message`、仓库同步工具或其他工具当成 Serena 安装管理器。

如后续版本提供 Serena 专用检查/升级工具，应先核验 editable 安装路径与仓库身份、工作区干净、remote 和默认分支；检查请求仅报告上游状态，不升级。执行升级必须得到明确授权，且只允许 fast-forward 更新和 uv 工具核验；发现来源不明、工作区有改动、分叉或任一阶段失败时停止并保留现场。
