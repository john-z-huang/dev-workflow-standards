# 本地代码理解与 Serena 优先规则

本文件只规定本地代码理解时的工具选择，不改变需求范围、Git 权限、提交授权、测试要求或其他工作流规则。

## 适用条件

- 当前任务需要理解源代码的控制流、符号关系、调用链、类型关系或变更影响范围时，优先使用 Serena MCP。
- “本地环境”必须以当前任务实际暴露 Serena MCP 且目标项目路径可访问为依据，不能只根据操作系统、Shell 或 worktree 存在来推断。
- 纯文档、配置、日志、生成文件、简单精确文本查找，以及不需要理解代码逻辑的机械修改，不强制使用 Serena。

## 项目绑定与能力确认

- 本次 Session 尚未读取 Serena 使用说明时，先调用 `initial_instructions`，保存返回的 Serena session id；按当前工具 Schema 向需要它的工具传入 `session`。已读取且上下文仍有效时复用，不为每次查询重复调用或自行编造 id。
- 以目标仓库/worktree 的绝对根路径调用 `activate_project`，核对返回的项目路径、语言/后端及激活提示；若当前说明已经确认准确项目处于激活状态，无须重复激活。单项目启动上下文可能不暴露该工具，此时核对启动绑定，不能仅因工具缺席判定 Serena 不可用。项目不匹配且无法切换时，停止依赖该项目上下文的查询。
- `activate_project` 可隐式创建项目配置、初始化语言后端，并可能执行项目配置的 `activation_command`；不要把激活当成保证无副作用的只读查询。遵守项目可信范围和宿主权限，不擅自增加启动命令、索引、依赖或语言配置。独立 CLI 初始化、索引或配置修改不是普通代码查询的必经步骤。
- 工具清单随版本、context、mode、项目配置及语言后端变化。以当前可见的说明和 Schema 为准；必要时调用已暴露的 `get_current_config` 核对。LSP 和 JetBrains 后端的工具名及能力可能不同，不要求未暴露的同名工具，也不因某个可选工具缺失放弃其余可用能力。
- 排查语言服务配置时，注意项目 `ls_specific_settings` 按语言块替换该语言的全局设置，不是逐字段深合并；项目新加一个字段可能遮蔽原有服务路径或参数。先核对实际配置和日志，再提出最小修复，不擅自写入配置。
- 区分经典 tools 接口和 v2 REPL 接口。后者可通过 `s` 的已暴露 facade 提供等价操作，缺少独立 MCP 工具不等于能力缺失；先按当前 REPL 说明用 `s.info(...)` 获取所需签名，不凭文档示例猜参数或主动切换接口。`lsp` 与 `jb` facade 随后端互斥，只使用实际暴露的入口；以下工具名表示操作用途，不强制一种接口。
- Serena session id 用于会话状态，不是独立项目或权限隔离证明。同一服务可能共享当前活动项目；多 Agent、多个 checkout 或交替查询多个仓库时，重新确认目标绑定，避免一个会话切换项目后另一个继续查询旧路径。

## 按问题选择查询

若用户提供了先前 Codex 会话链接，或项目中已有 Codex 会话摘要且查询涉及代码或项目背景事实，先按 [`codex-session-facts.md`](codex-session-facts.md) 查阅摘要并溯源相关原会话；确认适用会话未提供相关事实后，再按以下顺序查询代码。用户会话中的事实在该范围内优先于代码查询，但不构成当前指令或授权。历史事实与当前观察不同时，报告差异，不改写历史原义。没有相关会话记录时走原流程。

1. 不熟悉文件结构且尚不知道目标符号时，先对候选文件使用 `get_symbols_overview`。已知目标符号时直接 `find_symbol`，不增加无助于问题的概览步骤。
2. 用 `relative_path` 将查询限定到已知文件或目录；先读名称、签名或必要的子符号，确需实现细节时再设 `include_body=true`。使用当前 Schema 支持的 `depth`、`max_matches` 和 `max_answer_chars` 控制输出；结果超限时缩小路径或名称，不直接放大到全仓全文。
3. `name_path` 是文件内的符号层级路径，例如 `Class/method`，不是文件路径；与 `relative_path` 一起定位目标。重载消歧和名称匹配按当前工具说明处理。用已暴露的 `find_declaration` 从使用位置查声明，`find_referencing_symbols` 查引用，`find_implementations` 查实现；引用不一定是函数调用，实现也不等于运行时调用链。
4. 不知道名称时先用已暴露的 `search_for_pattern` 或宿主 `rg` 在限定范围查候选，再回到符号工具确认结构关系。文本命中不能作为引用、类型或调用关系的证明。
5. 需要语言服务反馈且能力已暴露时使用 `get_diagnostics_for_file`；空诊断或空引用不能单独证明代码正确、符号未使用或影响范围完整，仍需考虑语言支持、索引及项目配置。
6. 已读过完整文件时复用已有内容，不再用符号读取重复获取相同实现。Serena 返回的行号按当前说明为 0-based；提供面向用户的 1-based 文件链接或评论前转换并核对位置。

## 修改方式与验证边界

- 替换完整函数、方法或类时，优先使用已暴露的 `replace_symbol_body`；围绕顶层符号插入代码可用 `insert_before_symbol` / `insert_after_symbol`。只改较大符号中的几行，或修改文档、配置时，使用宿主的精确文件编辑工具，不为此重写整段符号。
- 重命名或安全删除优先使用当前后端支持的 `rename_symbol` / `safe_delete_symbol`，按返回的成功、引用阻止或错误状态处理。工具不可用时，先确认所有必要引用和影响范围，再决定能否手工修改；证据不足则停止该修改。
- 成功的编辑结果不需要仅为确认落盘而再次读取相同内容；但仍须检查任务范围和最终 diff，并完成适用测试、构建、lint、类型检查或集成验证。工具的成功状态或“无需重复确认传播”的提示不能豁免这些验收要求。

## Serena 项目初始化、Onboarding 与 Memory

- 项目激活、onboarding 和 Memory 写入是不同步骤。当前源码在没有项目 Memory 且 onboarding 工具可用时，返回“询问用户是否执行”的提示；不会自动完成项目调查或写出全部记忆。按当前提示先征询用户，已有明确授权则沿用；本任务不需要 onboarding 时记录跳过并继续必要查询，不把它设为所有任务的前置条件。
- `list_memories` 列出可见记忆，不是专用 onboarding 状态接口。已有记忆不证明调查完整；空列表也可能受过滤或配置影响。`no-onboarding` / `no-memories` 可禁用相应功能；不要为满足固定顺序自行启用。获准后每个会话最多调用一次 `onboarding`，读取其维护说明与调查步骤；调用本身可能种下维护记忆，返回调查提示不等于后续调查、写入已完成。
- 写入任何 Memory 前，先用 `list_memories` 查找维护说明：若存在 `global/memory_maintenance`，优先用 `read_memory` 读取它；否则读取项目的 `memory_maintenance`。只有全局和项目 Memory 都没有维护说明时，onboarding 才在项目 Memory 中生成该说明；其他 onboarding 记忆写入项目的 `.serena/memories/`。
- 遵守维护说明，先用 `list_memories` 和 `read_memory` 检查相关记忆、避免重复，再用 `write_memory` 将可复用的项目说明、约定及用户要求保存的精简会话交接写入 Serena Memory。历史 Codex 会话事实的保存与更新只按 [`codex-session-facts.md`](codex-session-facts.md) 执行；一般交接只记录有复用价值的目标、已确认决定、相关路径、验证结果、未决事项和下一步，不记录逐条工具日志。面向后续 Agent 阅读的内容使用简体中文；技术术语、符号名、命令、路径和 `mem:` 引用保留 canonical 原文，跨记忆引用写作 `` `mem:NAME` ``。
- 一般 Serena Memory 是项目文档的补充，不替代仓库规范、代码或父 Session 的实时任务状态；mode/count、分配、当前 slice 和授权由父 Session 持有。用户要求持久化的历史会话事实摘要是特定来源的事实记录，依其专门规约参与代码/项目背景事实查询，不受一般 Memory 这条规则排除。不得写入凭据、秘密、原始对话转录、完整日志或完整 diff。项目 Memory 是否进入版本控制由仓库忽略和协作约定决定；不要为保存 Memory 擅自修改 `.gitignore`。
- Memory 默认在项目 `.serena/memories/`；`modules/auth` 这样的逻辑名对应主题子目录并由 Serena 添加 `.md`。遵守配置的数据目录、`read_only_memory_patterns` 和 `ignored_memory_patterns`；列表不可见不表示磁盘上不存在，不通过普通文件工具绕过隐藏或只读限制。`global/` 是跨项目作用域，仅在明确要求时写入；维护说明优先级不授予修改全局记忆的权限。
- 需要重命名/移动 Memory 时，优先使用已暴露且获准的 `rename_memory`，其会维护规范的 `mem:` 引用，但不改写只读记忆。删除 Memory 仅在用户明确指示或授权后调用 `delete_memory`。更名、删除及覆盖前核对目标和引用，不因一般写入授权扩大操作范围。
- 本次修改 Memory 或其引用时，检查目标与规范的 `mem:` 引用能否解析。官方将没有 MCP 对应工具的 `serena memories check` 定位为人工 CLI 检查；默认报告 stale 引用，裸名称和模糊扫描需显式启用，且它不验证事实正确性。在当前工作流禁止以 CLI 补齐未封装操作时，报告此项未执行及人工检查入口，不自行运行或编造 MCP 替代工具；已有明确授权且适用规则允许 CLI 时才执行。只改代码或普通文档不因此强制执行 Memory CLI。
- 仅在用户明确要求检查或升级本机 uv 安装的 Serena 时处理；当前 MCP 没有安装来源检查或升级工具。按[本地 Serena 更新能力边界](serena-mcp-tool-upgrade.md)说明缺少的专用能力并停止，不以任意 shell、Git 或 uv 命令代做。

## CUDA 代码理解

- 需要理解 CUDA 代码（包括 `.cu`、`.cuh` 文件，或包含 CUDA 语法的主机/设备代码）时，先确认当前后端能将相关文件交给已配置的 C++ 语言服务，再尝试符号、引用和诊断分析。Serena 的 C/C++ LSP 可使用 clangd（`cpp`）或 ccls（`cpp_ccls`），不要把 clangd 当成唯一后端或保证 CUDA 全部语义受支持。
- C/C++ 跨文件分析依赖正确的 `compile_commands.json`、编译参数和包含路径；缺失时结果可能不完整。clangd 默认可能下载服务并生成 `.serena/compile_commands.json` 等派生文件，不能将语言服务初始化视为必定离线、无写入；受当前授权和环境限制约束，不擅自安装 CUDA 或改写编译配置。
- 即使本地没有安装 CUDA 库和头文件，也先按 C++ 代码路径进行解析；不要因为缺少 CUDA 依赖就立即安装依赖、修改项目配置或改用大段文本读取。
- 如果当前 C++ 语言服务无法解析或未就绪，再按本文件的普通文件工具降级规则处理，并明确记录降级及其对调用链、类型关系或影响范围判断的限制。新建文件未被语言服务打开或索引时，跨文件引用可能遗漏；先做该文件的限定符号查询，不据空结果判定没有引用，也不擅自重启服务。

## 普通文件工具的边界

- 固定写操作和强制 Git/GitHub 门禁按 [`mcp-tools.md`](mcp-tools.md) 使用专用工具；未覆盖的信息查询按 [`read-only-queries.md`](read-only-queries.md) 选择只读 CLI。未封装的写操作或必需工具失败仍停止并报告。Serena 和补充查询均不替代规定的仓库状态检查。
- `rg`、`grep` 和普通文件读取用于 Markdown、YAML、JSON、日志、锁文件、生成文件、Serena 不支持的语言、精确文本搜索，以及 Serena 无法处理的文件。
- `rg` 或普通文件读取找到候选后，如果后续需要理解源代码逻辑，应回到 Serena 的符号和引用分析，而不是继续依赖大段文本输出。

## 不可用时的降级

- Serena 未暴露、项目激活失败、语言服务器未就绪或符号分析失败时，记录失败工具、目标路径、原因和证据限制，再用适当的普通文件工具做限定范围的降级；无需为可降级查询安装依赖、修改配置或反复重试同一失败调用。激活失败后不得继续使用其他项目的符号结果。
- 工具降级本身不阻塞不依赖符号关系的任务；如果任务必须依赖调用链、类型关系或影响范围，而现有工具无法提供足够证据，应报告 `BLOCKED` 或 `SKIPPED` 及其影响，不得把未完成的理解标记为通过。
- 若历史会话事实流程所需的 Serena Memory 工具缺失或失败，不得以代码符号查询或普通文件写入绕过；按 [`codex-session-facts.md`](codex-session-facts.md) 报告该流程缺口。无须保存会话摘要的普通代码理解任务仍按本节的 Serena 降级规则处理。
- Serena 的诊断、引用和实现结果只能辅助代码检查，不能替代测试、构建、lint、类型检查或集成验证。

## Worktree 规则

- 需求 worktree 创建后，必须用该 worktree 的准确路径重新激活 Serena 项目。
- 不得继续使用原始工作区的 Serena 项目上下文分析需求 worktree 中的代码。
- 多个 worktree 必须分别绑定各自路径；原始工作区只做其工作流授权的同步、状态或清理工作。

## 本次核对依据与版本边界

本机源码 `/Users/johannyellow/Documents/GitHub/serena` 对应提交 `05d5808570f452a09c9fede4789b914bd81b3f0b`（2026-10-28）；重新读取的 libs-local-docs-skill `docs/serena` 缓存对应 `ede329aaf0c824bea75455a2926f01420d7aa620`（2026-10-28）。两者不是同一提交，当前运行服务也不据此推定相同；后续调用以实际工具说明、Schema 和激活结果为准。关键依据：

- 源码 `src/serena/agent.py` 的 `create_system_prompt`、`get_project_activation_message`、`activate_project_from_path_or_name`，以及 `src/serena/tools/config_tools.py` 的 `ActivateProjectTool.apply`：会话 id、项目激活与 onboarding 提示。
- 源码 `src/serena/tools/workflow_tools.py` 的 `OnboardingTool.apply`、`src/serena/repl/api/mem_api.py` 的 `MemoryApi.onboarding`，以及 `src/serena/resources/config/prompt_templates/system_prompt.yml`、`src/serena/resources/config/modes/editing.yml`：调查提示、维护记忆与符号操作边界。
- 本地文档根目录 `/Users/johannyellow/.agents/skills/libs-local-docs-skill/docs/serena/` 中的 `docs/01-about/035_tools.md`、`docs/02-usage/040_workflow.md`、`docs/02-usage/045_memories.md`、`docs/02-usage/050_configuration.md` 和 `docs/03-special-guides/cpp_setup.md`：接口、项目、Memory、工具配置和 C/C++ 条件。更新后的文档仍有“默认执行 onboarding”的概括，应结合上述源码的实际询问流程理解。
