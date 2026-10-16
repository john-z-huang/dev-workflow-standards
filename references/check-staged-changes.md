# 暂存区检查

提交前检查暂存区是否包含 Git 空白错误。获得用户暂存授权后，用 `stage_repository_paths(repo_path, paths)` 按显式完整文件路径暂存，再调用 `check_staged_changes(repo_path)`；该检查只读取暂存区并执行空白检查，不运行测试，也不判断文件是否属于当前需求。暂存工具不支持部分 hunk；若同一文件含有需要保留的其他改动则停止。

提交授权具备且分支、提交信息、暂存范围与适用检查均通过后，使用 `commit_repository_changes(repo_path, message, expected_paths)` 完成提交。该工具会再次核对路径集合、提交信息规则和暂存区空白检查，不接收任意命令。

若项目需要测试，先按项目文档确定合适的验证范围。只有用户要求测试或验证时才运行项目测试；本 Skill MCP 服务不接受任意测试命令。

Git Hook 集成见 [`hooks.md`](hooks.md)。Hook 调用的本地脚本可继续用于自动校验；交互式工作流应使用 MCP 工具。
