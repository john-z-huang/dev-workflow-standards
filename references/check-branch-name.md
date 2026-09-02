# Push 前分支名称检查

## 功能描述

`scripts/check-branch-name.py` 使用不区分大小写的正则表达式检查 Git 分支名称，拦截特定 Code Agent 产品名称。当前名单包括：

`codex`、`claude`、`antigravity`、`opencode`、`cursor`、`copilot`、`cline`、`roo-code`、`roo_code`、`aider`、`continue`、`windsurf`、`devin`、`gemini`、`cody`、`junie`、`kiro`、`goose`、`augment`、`amazon-q` 和 `amazon_q`。

名单集中定义在脚本的 `FORBIDDEN_AGENT_NAMES` 常量中。匹配为产品名子串匹配，例如 `feat/codex-api` 和 `fix/CURSOR-timeout` 都会被拦截。

## 触发时机

- 推荐作为标准 Git `pre-push` hook，在本地执行 `git push`、向 GitHub 推送 patch 前自动触发。
- 也可以手动传入分支名称，用于创建或重命名分支后的即时检查。

脚本检查本地待推送的 `refs/heads/*` 和目标远端的 `refs/heads/*`。删除远端分支时没有新的 patch，脚本会跳过该 ref，避免阻止分支清理。

## 手动执行

```bash
# 检查指定分支
python3 scripts/check-branch-name.py feat/add-validation

# 一次检查多个分支
python3 scripts/check-branch-name.py feat/add-validation fix/repair-timeout

# 不传分支时检查当前分支
python3 scripts/check-branch-name.py
```

## 集成方式

仓库已提供可版本化的 `.githooks/pre-push` wrapper。首次在仓库中启用：

```bash
git config core.hooksPath .githooks
```

之后正常执行：

```bash
git push origin <分支名称>
```

`.githooks/pre-push` 会把 Git 的标准 pre-push 输入交给检查脚本。命中禁止名称时，脚本输出违规分支和命中项并返回非零退出码，Git 不会继续推送。

如果项目已有自定义 hook，应将检查命令合并到现有的 `pre-push` 流程，而不是覆盖已有检查：

```bash
python3 scripts/check-branch-name.py --pre-push "$@"
```

本地 hook 可以被 `git push --no-verify` 绕过；如组织要求不可绕过，还应在 GitHub 仓库侧配置对应的分支保护或服务端检查。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 所有待检查的分支名称均通过 |
| 1 | 至少一个分支名称命中禁止名称，push 应被阻止 |
| 2 | 参数错误、无法确定当前分支或 pre-push 输入格式错误 |
