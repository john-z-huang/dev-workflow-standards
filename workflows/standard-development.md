# 普通开发工作流

适用：默认直接在当前工作区开发，无论仓库是否有 remote、是否需要 GitHub 交付或是否需要分支。只有用户在指令中明确要求 worktree 时，才改读 [`worktree-development.md`](worktree-development.md)。固定 Git/GitHub 操作使用 [`mcp-tools.md`](../references/mcp-tools.md) 中的专用工具。

## 队列

| 步骤 | 完成后 |
|---|---|
| 明确需求 | 范围与授权清楚 |
| 确认范围 | 用户改动和任务边界已识别 |
| 代码理解 | 影响范围已掌握，或记录跳过理由 |
| 实现 | 仅包含批准的改动 |
| 验证 | 适用检查已完成或标记 |
| 提交门禁 | 完成或停在本地结果 |

## 1. 明确需求

- 明确目标、输入、输出、不可改变项和验收标准。
- 确认是否需要 remote、GitHub、Hook、自动化或历史重写；remote 本身不改变默认工作区模式。
- 对 GitHub 仓库调用 `audit_repository_state` 检查仓库身份、remote、默认分支和 Fork parent；只有确认 `parent` 非空才启用 [`fork-maintenance.md`](../references/fork-maintenance.md)。
- 未获授权的提交、推送、外部消息、合并、删除和历史重写保持禁止。

## 2. 确认范围

- 调用 `audit_repository_state`，传入目标仓库绝对 `repo_path`，检查分支、工作区和 remote；保留已有改动。
- 区分本任务、已有改动、未跟踪文件和无关内容；记录允许修改的文件/hunk，不覆盖、删除、移动或静默恢复其他内容。
- 本地代码任务按 [`code-understanding.md`](../references/code-understanding.md) 在目标仓库准确根目录激活 Serena；Memory 只保留可复用的项目说明。
- 提交边界必须是可独立审查、验证和回滚的逻辑单元。

## 3. 代码理解

- 任务需要理解源代码逻辑时优先使用 Serena 的符号、引用、实现和调用链能力。
- 先形成相关文件和影响范围的最小理解，再开始实现。
- 纯文档、机械修改或 Serena 不可用时记录降级原因；证据不足以判断影响范围时停止并报告。

## Fork 仓库边界

仅对已确认 Fork 生效。`main` 只镜像上游默认分支；个人改动必须从个人维护分支或其需求分支进入。需求 PR 默认以个人维护分支为 base。`main` 和个人维护分支的保护规则应符合 [`fork-maintenance.md`](../references/fork-maintenance.md)；规则不适用时不得修改独立仓库现有拓扑。

## 4. 实现与验证

- 只实现已批准范围；新的业务或架构决定先停下请求决定。
- 文档和提交使用中文；不添加 Agent 署名或生成声明。
- 自动化使用可移植 Shell/Python 和标准 Git Hook，不依赖专有 Hook。MCP 不接收任意脚本或测试命令。
- 按用户要求或项目明确要求运行适用验证；不把未运行的检查写成通过。项目自定义测试由项目配置决定，不传入 MCP 工具。
- 失败时改读 [`recovery-and-exceptions.md`](recovery-and-exceptions.md)；未运行不得标为通过。

## 5. 提交门禁

只有用户授权暂存和提交且以下条件满足时继续：

- `check_branch_names` 检查分支合规；
- `check_commit_message` 检查完整提交信息；标题格式为 `<type>: 中文说明`，type 为 `feat/fix/docs/refactor/test/chore/perf/build/ci`；
- 只包含本任务的完整文件，无令牌、用户改动或无关内容。MCP 暂存工具按整文件工作；若同一文件含有需保留的无关 hunk，停止并报告工具不支持部分暂存；
- `check_staged_changes` 和适用项目检查通过；
- 调用 `stage_repository_paths(repo_path, paths)` 后，再用 `commit_repository_changes(repo_path, message, expected_paths)` 完成提交；工具不可用时停在本地结果，不手写 Git 命令绕过；
- 需要 GitHub 交付时进入 [`github-delivery.md`](github-delivery.md)。
