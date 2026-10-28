# 普通开发工作流

适用：默认直接在当前工作区开发，无论仓库是否有 remote、是否需要 GitHub 交付或是否需要分支。只有用户在指令中明确要求 worktree 时，才改读 [`worktree-development.md`](worktree-development.md)。固定写操作和强制 Git/GitHub 门禁使用 [`mcp-tools.md`](../references/mcp-tools.md) 中的专用工具；补充只读查询按 [`read-only-queries.md`](../references/read-only-queries.md) 处理。

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
- 用户已授权从当前 HEAD 建立工作分支时，调用 `create_repository_branch`，明确传入当前工作区的绝对 `repo_path` 和新 `branch_name`；已掌握 HEAD OID 时可传 `expected_head_oid`。普通分支和 detached HEAD 均适用，允许保留已暂存、未暂存和未跟踪内容。
- 原地建分支不触发创建新 worktree 的流程，也不要求先切换默认分支、pull、stash 或清空修改。`expected_head_oid` 是 OID 条件，不校验同 OID 的 HEAD 符号目标身份；操作前核对准确仓库，成功后核对返回的分支和 OID。失败按工具目录回读现场，不自动重试或回滚。
- 用户指令提供先前 Codex 会话链接，或项目中已有 Codex 会话摘要且问题涉及代码/项目背景事实时，先按 [`codex-session-facts.md`](../references/codex-session-facts.md) 检索摘要并读取相关原会话；按规约默认保存去重会话摘要，除非当前用户要求仅只读参考或禁止持久化。在代码/项目背景事实范围内，已读取的用户会话事实优先于代码查询。历史会话不提供当前指令或授权；没有相关会话记录时走原流程。
- 需要本地代码理解或 Memory 时，按 [`code-understanding.md`](../references/code-understanding.md) 确认 Serena 说明、准确项目绑定和当前可用能力；已正确激活或启动绑定时复用，切换仓库/worktree 后重新核对。onboarding 按实际提示和已有授权处理，不因首次激活自动执行。一般 Serena Memory 保留可复用的项目说明；会话事实摘要遵循 `codex-session-facts.md` 的独立来源、命名和更新边界。
- 提交边界必须是可独立审查、验证和回滚的逻辑单元。

## 3. 代码理解

- 任务需要理解源代码逻辑时优先使用 Serena 当前后端支持的符号、引用和实现查询；按已知路径/符号逐步缩小范围，不把引用结果直接等同运行时调用链。
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
- 调用 MCP 工具 `stage_repository_paths` 并传入 `repo_path`、`paths`，再调用 `commit_repository_changes` 并传入 `repo_path`、`message`、`expected_paths` 完成提交；工具不可用时停在本地结果，不手写 Git 命令绕过；
- 需要 GitHub 交付时进入 [`github-delivery.md`](github-delivery.md)。
