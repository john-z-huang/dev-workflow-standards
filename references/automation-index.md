# 自动化脚本目录

只列出可复用脚本及其解决的问题；具体使用时直接查看脚本的命令帮助或项目工作流。

## 脚本索引

| 脚本 | 用途 |
|---|---|
| `scripts/pr-merge-cleanup.py` | PR 合并后确认状态、同步 base、删除本地已合并 head 分支 |
| `scripts/check-branch-name.py` | 提交前检查当前分支名称 |
| `scripts/check-commit-message.py` | 提交前检查标题格式、中文说明和禁止署名 |
| `scripts/check-staged-changes.py` | 提交前检查暂存区空白错误，并可运行测试 |
| `scripts/rewrite_weather_commit_subjects.py` | 按映射重写历史提交标题 |
| `scripts/check-pr-policy.py` | 只读检查 Issue/PR 状态和分支拓扑 |
