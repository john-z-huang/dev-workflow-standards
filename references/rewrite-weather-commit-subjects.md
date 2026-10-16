# 历史提交标题重写能力边界

本 Skill 的 MCP 工具不执行 Git 历史改写。调用 `rewrite_legacy_commit_message` 并传入 `message`，只会将单条旧标题文本按映射转换并返回结果；它不会读取提交、调用 Git、批量验证提交范围或修改历史。

历史重写会改变提交 SHA，且可能影响共享分支。本 Skill MCP 服务没有 `filter-branch`、rebase 或批量改写工具。遇到历史改写请求时，先记录风险与目标范围，说明当前没有专用执行能力；不要通过通用命令或直接运行脚本绕过工具边界。

仓库中的 `scripts/rewrite_weather_commit_subjects.py` 是原有兼容资产，不由 Skill 的 MCP 工具调用。它保留旧标题映射、合并提交过滤和未知标题失败等纯文本转换逻辑；如需查看转换结果，优先使用 `rewrite_legacy_commit_message`。
