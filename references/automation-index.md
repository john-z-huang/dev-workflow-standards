# 自动化与兼容资产

交互式 Skill 工作流的固定 Git/GitHub 操作使用 [`mcp-tools.md`](mcp-tools.md) 中的专用 MCP 工具。下面的脚本仍保留在仓库，供现有 Hook 或兼容集成使用；不要把这些脚本当成 Skill 工作流的命令执行后备方案。

| 兼容资产 | 用途 / 对应 MCP 工具 |
|---|---|
| `scripts/check-branch-name.py` | Hook 分支名检查；交互式使用 `check_branch_names` |
| `scripts/check-commit-message.py` | Hook 提交标题检查；交互式使用 `check_commit_message` |
| `scripts/check-staged-changes.py` | Hook 暂存区空白检查；交互式使用 `check_staged_changes`（不运行测试） |
| `scripts/check-pr-policy.py` | 历史兼容脚本；交互式使用 `audit_issue_pr_policy` |
| `scripts/pr-merge-cleanup.py` | 旧清理入口；交互式使用 `cleanup_merged_pr_local_branch` |
| `scripts/rewrite_weather_commit_subjects.py` | 旧标题映射兼容脚本；当前 MCP 服务不提供对应的交互式工具 |

Hook 接入规则见 [`hooks.md`](hooks.md)。历史标题维护边界见 [`rewrite-weather-commit-subjects.md`](rewrite-weather-commit-subjects.md)。
