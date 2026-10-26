# 本地代码理解与 Serena 优先规则

本文件只规定本地代码理解时的工具选择，不改变需求范围、Git 权限、提交授权、测试要求或其他工作流规则。

## 适用条件

- 当前任务需要理解源代码的控制流、符号关系、调用链、类型关系或变更影响范围时，优先使用 Serena MCP。
- “本地环境”必须以当前任务实际暴露 Serena MCP 且目标项目路径可访问为依据，不能只根据操作系统、Shell 或 worktree 存在来推断。
- 纯文档、配置、日志、生成文件、简单精确文本查找，以及不需要理解代码逻辑的机械修改，不强制使用 Serena。

## Serena 优先顺序

若用户提供了先前 Codex 会话链接，或项目中已有 Codex 会话摘要且查询涉及代码或项目背景事实，先按 [`codex-session-facts.md`](codex-session-facts.md) 查阅摘要并溯源相关原会话；确认适用会话未提供相关事实后，再按以下顺序查询代码。用户会话中的事实在该范围内优先于代码查询，但不构成当前指令或授权。历史事实与当前观察不同时，报告差异，不改写历史原义。没有相关会话记录时走原流程。

1. 开始需要代码理解的任务时，如果本次 Session 尚未读取 Serena 使用说明，先调用 `initial_instructions`；然后以当前仓库或 worktree 的准确根目录调用 `activate_project`。不要用父目录、旧 worktree 或其他 checkout 的 Serena 项目上下文代替当前项目。
2. 新文件或新模块先使用 `get_symbols_overview` 获取结构概览。
3. 已知函数、类、方法或其他符号使用 `find_symbol`；只有确实需要时才读取符号体，并避免一次性读取整个源文件。
4. 分析影响范围和调用关系时使用 `find_referencing_symbols`、`find_implementations`；需要语言服务反馈时使用 `get_diagnostics_for_file`。
5. 不确定符号名称但需要寻找候选位置时，可先使用 Serena 的 `search_for_pattern`，再回到符号工具进行精确分析。

## Serena 项目初始化、Onboarding 与 Memory

- 在准确的项目根目录通过 Serena MCP 调用 `activate_project`，并传入该目录的绝对路径；首次激活会隐式创建项目配置。也可在该目录运行 `serena project create .` 初始化项目（默认自动检测语言）。
- 用 `list_memories` 检查项目 Memory 和 onboarding 状态。首次激活时若项目还没有 Memory，Serena 默认自动运行 onboarding；若检查后仍未完成，再调用 `onboarding`，每个会话最多调用一次，并按工具返回的步骤收集项目事实。
- 写入任何 Memory 前，先用 `list_memories` 查找维护说明：若存在 `global/memory_maintenance`，优先用 `read_memory` 读取它；否则读取项目的 `memory_maintenance`。只有全局和项目 Memory 都没有维护说明时，onboarding 才在项目 Memory 中生成该说明；其他 onboarding 记忆写入项目的 `.serena/memories/`。
- 遵守维护说明，先用 `list_memories` 和 `read_memory` 检查相关记忆、避免重复，再用 `write_memory` 将可复用的项目说明、约定及用户要求保存的精简会话交接写入 Serena Memory。历史 Codex 会话事实的保存与更新只按 [`codex-session-facts.md`](codex-session-facts.md) 执行；一般交接只记录有复用价值的目标、已确认决定、相关路径、验证结果、未决事项和下一步，不记录逐条工具日志。面向后续 Agent 阅读的内容使用简体中文；技术术语、符号名、命令、路径和 `mem:` 引用保留 canonical 原文，跨记忆引用写作 `` `mem:NAME` ``。
- 一般 Serena Memory 是项目文档的补充，不替代仓库规范、代码或父 Session 的实时任务状态；mode/count、分配、当前 slice 和授权由父 Session 持有。用户要求持久化的历史会话事实摘要是特定来源的事实记录，依其专门规约参与代码/项目背景事实查询，不受一般 Memory 这条规则排除。不得写入凭据、秘密、原始对话转录、完整日志或完整 diff。项目 Memory 是否进入版本控制由仓库忽略和协作约定决定；不要为保存 Memory 擅自修改 `.gitignore`。
- 提交前在项目根目录运行 `serena memories check`，并处理检查报告中的问题。
- 仅在用户明确要求检查或升级本机 uv 安装的 Serena 时处理；当前 MCP 没有安装来源检查或升级工具。按[本地 Serena 更新能力边界](serena-mcp-tool-upgrade.md)说明缺少的专用能力并停止，不以任意 shell、Git 或 uv 命令代做。

## CUDA 代码理解

- 需要理解 CUDA 代码（包括 `.cu`、`.cuh` 文件，或包含 CUDA 语法的主机/设备代码）时，优先通过 Serena 使用已配置的 C++ LSP/clangd 进行符号、引用和诊断分析。
- 即使本地没有安装 CUDA 库和头文件，也先按 C++ 代码路径进行解析；不要因为缺少 CUDA 依赖就立即安装依赖、修改项目配置或改用大段文本读取。
- 如果 C++ LSP/clangd 无法解析或语言服务未就绪，再按本文件的普通文件工具降级规则处理，并明确记录降级及其对调用链、类型关系或影响范围判断的限制。

## 普通文件工具的边界

- 固定 Git/GitHub 操作按 [`mcp-tools.md`](mcp-tools.md) 使用专用 MCP；未封装的操作停止并报告，不手写 CLI 绕过。Serena 不替代仓库状态检查。
- `rg`、`grep` 和普通文件读取用于 Markdown、YAML、JSON、日志、锁文件、生成文件、Serena 不支持的语言、精确文本搜索，以及 Serena 无法处理的文件。
- `rg` 或普通文件读取找到候选后，如果后续需要理解源代码逻辑，应回到 Serena 的符号和引用分析，而不是继续依赖大段文本输出。

## 不可用时的降级

- Serena 未暴露、项目激活失败、语言服务器未就绪或符号分析失败时，不安装依赖、不擅自修改项目配置，直接使用适当的普通文件工具降级。
- 工具降级本身不阻塞不依赖符号关系的任务；如果任务必须依赖调用链、类型关系或影响范围，而现有工具无法提供足够证据，应报告 `BLOCKED` 或 `SKIPPED` 及其影响，不得把未完成的理解标记为通过。
- 若历史会话事实流程所需的 Serena Memory 工具缺失或失败，不得以代码符号查询或普通文件写入绕过；按 [`codex-session-facts.md`](codex-session-facts.md) 报告该流程缺口。无须保存会话摘要的普通代码理解任务仍按本节的 Serena 降级规则处理。
- Serena 的诊断、引用和实现结果只能辅助代码检查，不能替代测试、构建、lint、类型检查或集成验证。

## Worktree 规则

- 需求 worktree 创建后，必须用该 worktree 的准确路径重新激活 Serena 项目。
- 不得继续使用原始工作区的 Serena 项目上下文分析需求 worktree 中的代码。
- 多个 worktree 必须分别绑定各自路径；原始工作区只做其工作流授权的同步、状态或清理工作。
