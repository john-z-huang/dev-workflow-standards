# Git 写操作与 Codex 审批

固定写操作和强制审计/检查由 MCP 专用工具执行；查询优先使用专用 MCP 或已授权 Connector，未覆盖的只读查询按 [`read-only-queries.md`](read-only-queries.md) 使用 CLI，无须逐次申请额外的业务授权。Codex MCP 配置使用 `default_tools_approval_mode="writes"`，让写工具在执行前进入 Codex 审批流程。工具审批与用户意图授权是独立前置条件；既有授权在原范围内持续有效，没有相应授权不调用写工具。

只读 CLI 不替代规定门禁，不在工具拒绝后更换路径或执行器绕过审批。查询未覆盖可按只读规约处理；必需工具缺失或执行失败时保留现场，说明已完成步骤、失败原因及缺少条件。`fetch`、index/refs/配置修改均为本地写入；只读也可以联网，仍受宿主审批和沙箱限制。

本服务提供固定路径暂存和提交工具 `stage_repository_paths`、`commit_repository_changes`，但不提供任意命令或项目自定义测试工具。调用只读工具 `check_staged_changes` 时传入 `repo_path`，检查暂存区空白问题；是否运行项目测试按项目要求和用户指示处理。

仓库规则不能覆盖用户全局 AGENTS 或已安装 Skill 中的更高层限制。交付时核对并报告仍存在的冲突；不自动编辑全局配置或声称运行中服务已加载新说明。验证本仓库源码的初始化和工具发现，与验证已安装服务完成重载是两件事。
