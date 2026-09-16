# 普通开发工作流

适用：无 remote、无需 GitHub，或用户只要求本地结果。若发现 Git 仓库有可同步 remote，改读 [`worktree-development.md`](worktree-development.md)。

## 队列

| 步骤 | 完成后 |
|---|---|
| 明确需求 | 范围 |
| 确认范围 | 实现 |
| 实现 | 验证 |
| 验证 | 提交门禁 |
| 提交门禁 | 完成或停在本地结果 |

## 1. 明确需求

- 明确目标、输入、输出、不可改变项和验收标准。
- 确认是否需要 remote/worktree、GitHub、Hook、自动化或历史重写；需要时改读索引中的对应工作流。
- 未获授权的提交、推送、外部消息、合并、删除和历史重写保持禁止。
- 只读取当前步骤所需的 `references/`。

## 2. 确认范围

- 先看当前目录和现有差异；保留用户改动。
- 区分本任务、已有改动、未跟踪文件和无关内容。
- 记录允许修改的文件/hunk；不覆盖、删除、移动或静默恢复不属于本任务的内容。
- 提交边界必须是可独立审查、验证和回滚的逻辑单元。

## 3. 实现

- 只实现已批准范围；新的业务/架构决定先停下请求决定。
- 文档和提交使用中文；不添加 Agent 署名或生成声明。
- 自动化使用可移植 Shell/Python 和标准 Git Hook，不依赖专有 Hook。
- 新增行为/修复补充有意义的测试；纯文档/机械修改不强制新增测试。

## 4. 验证

- 文档：检查 Markdown、链接和引用路径。
- 行为：运行相关测试，并按风险运行构建、lint、类型、集成或回归检查。
- 脚本/Hook：覆盖成功、失败、参数错误、退出码和副作用范围。
- 失败时改读 [`recovery-and-exceptions.md`](recovery-and-exceptions.md)；未运行不得标为通过。

## 5. 提交门禁

只有用户授权提交且以下均通过才提交：

- 分支符合 [`check-branch-name.md`](../references/check-branch-name.md)；
- 提交信息符合 [`check-commit-message.md`](../references/check-commit-message.md)；
- 标题符合 `<type>: 中文说明`，type 为 `feat/fix/docs/refactor/test/chore/perf/build/ci`；
- 只暂存本任务文件/hunk，无令牌、用户改动或无关内容；
- `git diff --cached --check` 和适用测试通过；
- 相关 GitHub 交付已按索引进入 GitHub 工作流；未授权则停在本地结果。
