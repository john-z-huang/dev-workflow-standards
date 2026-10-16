# 分支名称检查

调用 `check_branch_names(branch_names?, repo_path?)` 校验分支命名策略。传入 `branch_names` 时检查指定名称；省略名称时必须提供 `repo_path`，检查仓库当前分支。策略允许 `main`、`master`，以及 `agent/`、`feat/`、`fix/`、`docs/`、`refactor/`、`personal/` 和 `personal-<project>` 等规定格式，并拒绝空格、大写、非 ASCII 字符和命中的特定 Code Agent 产品名。

分支策略在创建/重命名分支后和提交前检查。工具只判断名称，不创建、切换或删除分支，也不安装 Git Hook。Hook 可继续使用仓库内的兼容脚本；交互式 Skill 工作流使用 MCP 工具。
