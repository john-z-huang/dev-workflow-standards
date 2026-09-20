# Commit 前分支名称检查

## 功能描述

`scripts/check-branch-name.py` 检查 Git 分支命名策略，包括根分支、类别前缀、ASCII/小写格式，以及特定 Code Agent 产品名称。产品名使用不区分大小写的正则表达式匹配，当前名单包括：

`codex`、`claude`、`antigravity`、`opencode`、`cursor`、`copilot`、`cline`、`roo-code`、`roo_code`、`aider`、`continue`、`windsurf`、`devin`、`gemini`、`cody`、`junie`、`kiro`、`goose`、`augment`、`amazon-q` 和 `amazon_q`。

名单集中定义在脚本的 `FORBIDDEN_AGENT_NAMES` 常量中。匹配为产品名子串匹配，例如 `feat/codex-api` 和 `fix/CURSOR-timeout` 都会被拦截。

除 `main` 和 `master` 外，工作分支必须符合以下格式。`personal-<project>` 用于个人 Fork 的长期维护分支，`personal/<project>` 也可用于需要层级命名的仓库：

```text
^(?:(?:agent|feat|fix|docs|refactor|personal)/[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)*|personal-[a-z0-9]+(?:-[a-z0-9]+)*)$
```

## 触发时机

- 作为标准 Git `pre-commit` hook，在本地执行 `git commit` 时自动触发。
- 也可以手动传入分支名称，用于创建或重命名分支后的即时检查。

分支名称策略在提交前检查，分支不合规时不会创建 commit，也不需要等到向远端仓库推送时才发现问题。

## 手动执行

```bash
# 检查指定分支
python3 scripts/check-branch-name.py feat/add-validation

# 一次检查多个分支
python3 scripts/check-branch-name.py feat/add-validation fix/repair-timeout

# 在当前 Git 仓库中检查当前分支
python3 scripts/check-branch-name.py --pre-commit
```

## 边界

脚本只判断分支名称，不创建、切换或删除分支，也不安装 Git Hook；Hook 集成由独立的项目配置负责。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 当前或指定分支名称通过检查 |
| 1 | 至少一个分支名称违反格式或命中禁止名称，commit 应被阻止 |
| 2 | 参数错误、无法确定当前分支或 Git 状态无效 |
