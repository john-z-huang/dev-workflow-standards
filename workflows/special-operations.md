# 专项操作工作流

只在用户或项目明确要求时执行。固定 Git 配置或文本转换使用 [`mcp-tools.md`](../references/mcp-tools.md) 点名的专用工具。

## Hook

按 [`hooks.md`](../references/hooks.md) 确认目标项目已有正确的 `.githooks/pre-commit` 和 `commit-msg`。满足条件且用户授权后，调用 `configure_project_hooks_path` 配置该仓库的 Hook 路径。MCP 不自动复制或安装 Hook 脚本；`--no-verify` 不能替代检查。配置前后均核对本地 Git 配置和文件范围。

## 自动化

使用可移植 Shell/Python、标准库、Git/公开 CLI，不使用专有 Hook 或内部状态；按 [`automation-index.md`](../references/automation-index.md) 记录用途、调用和退出码。项目专属脚本、测试和自定义检查仍由项目工作流执行；不把任意 shell 命令交给 MCP 工具。GitHub 写操作按 [`github-delivery.md`](github-delivery.md)。

## 历史标题维护

按 [`rewrite-weather-commit-subjects.md`](../references/rewrite-weather-commit-subjects.md) 确认精确映射。`rewrite_legacy_commit_message` 只转换传入的提交文本，不调用 Git，也不重写历史。实际历史重写、强推或垃圾回收须单独获得明确授权；若没有对应的专用工具，则停止并报告，不能以文本转换工具替代。
