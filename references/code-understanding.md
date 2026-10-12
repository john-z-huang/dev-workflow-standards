# 本地代码理解与 Serena 优先规则

本文件只规定本地代码理解时的工具选择，不改变需求范围、Git 权限、提交授权、测试要求或其他工作流规则。

## 适用条件

- 当前任务需要理解源代码的控制流、符号关系、调用链、类型关系或变更影响范围时，优先使用 Serena MCP。
- “本地环境”必须以当前任务实际暴露 Serena MCP 且目标项目路径可访问为依据，不能只根据操作系统、Shell 或 worktree 存在来推断。
- 纯文档、配置、日志、生成文件、简单精确文本查找，以及不需要理解代码逻辑的机械修改，不强制使用 Serena。

## Serena 优先顺序

1. 开始需要代码理解的任务时，如果本次 Session 尚未读取 Serena 使用说明，先调用 `initial_instructions`；然后以当前仓库或 worktree 的准确根目录调用 `activate_project`。不要用父目录、旧 worktree 或其他 checkout 的 Serena 项目上下文代替当前项目。
2. 新文件或新模块先使用 `get_symbols_overview` 获取结构概览。
3. 已知函数、类、方法或其他符号使用 `find_symbol`；只有确实需要时才读取符号体，并避免一次性读取整个源文件。
4. 分析影响范围和调用关系时使用 `find_referencing_symbols`、`find_implementations`；需要语言服务反馈时使用 `get_diagnostics_for_file`。
5. 不确定符号名称但需要寻找候选位置时，可先使用 Serena 的 `search_for_pattern`，再回到符号工具进行精确分析。

## Serena 项目初始化、Onboarding 与 Memory

- 在准确的项目根目录通过 Serena MCP 调用 `activate_project`，并传入该目录的绝对路径；首次激活会隐式创建项目配置。也可在该目录运行 `serena project create .` 初始化项目（默认自动检测语言）。
- 用 `list_memories` 检查项目 Memory 和 onboarding 状态。首次激活时若项目还没有 Memory，Serena 默认自动运行 onboarding；若检查后仍未完成，再调用 `onboarding`，每个会话最多调用一次，并按工具返回的步骤收集项目事实。
- 写入任何 Memory 前，先用 `list_memories` 查找维护说明：若存在 `global/memory_maintenance`，优先用 `read_memory` 读取它；否则读取项目的 `memory_maintenance`。只有全局和项目 Memory 都没有维护说明时，onboarding 才在项目 Memory 中生成该说明；其他 onboarding 记忆写入项目的 `.serena/memories/`。
- 遵守维护说明，先用 `list_memories` 和 `read_memory` 检查相关记忆、避免重复，再用 `write_memory` 将可复用的项目说明、约定及用户要求保存的精简会话交接写入 Serena Memory。交接只记录有复用价值的目标、已确认决定、相关路径、验证结果、未决事项和下一步，不记录逐条工具日志。面向后续 Agent 阅读的内容使用简体中文；技术术语、符号名、命令、路径和 `mem:` 引用保留 canonical 原文，跨记忆引用写作 `` `mem:NAME` ``。
- Serena Memory 是项目文档的补充，不替代仓库规范、代码或父 Session 的实时任务状态；mode/count、分配、当前 slice 和授权由父 Session 持有。不得写入凭据、秘密、原始对话转录、完整日志或完整 diff。项目 Memory 是否进入版本控制由仓库忽略和协作约定决定；不要为保存 Memory 擅自修改 `.gitignore`。
- 提交前在项目根目录运行 `serena memories check`，并处理检查报告中的问题。

## 更新本地源码安装的 Serena

- 用户已允许 Agent 检查本机从本地源码安装的 Serena 是否有上游更新；先核实 uv 中 `serena-agent` 的实际 editable 来源、源码 checkout 路径、上游 remote、上游默认分支和工作区状态，不要假设路径或 remote 名称。
- 在源码 checkout 中先检查工作区；有任何本地改动时停止，不要 stash 或覆盖。工作区干净时获取上游并比较本地 `HEAD` 与已核实的上游分支：`git rev-list --left-right --count HEAD...$SERENA_UPSTREAM/$SERENA_BRANCH` 的左侧是本地独有提交数，右侧是上游独有提交数。只有左侧为 `0` 且右侧大于 `0` 时，才可快进更新：

  ```sh
  SERENA_SOURCE="/absolute/path/to/serena"
  SERENA_UPSTREAM=upstream
  SERENA_BRANCH=main
  git -C "$SERENA_SOURCE" status --short
  git -C "$SERENA_SOURCE" fetch "$SERENA_UPSTREAM"
  git -C "$SERENA_SOURCE" rev-list --left-right --count "HEAD...$SERENA_UPSTREAM/$SERENA_BRANCH"
  ```

  仅当结果为 `0 N` 且 `N > 0` 时继续：

  ```sh
  git -C "$SERENA_SOURCE" pull --ff-only "$SERENA_UPSTREAM" "$SERENA_BRANCH"
  uv tool upgrade serena-agent
  uv tool list --show-version-specifiers
  ```

- 先核实并设置三个变量；路径可含空格，remote 和分支名要取实际值，不要照抄示例。确认 `status --short` 没有输出。若比较结果为 `0 0`，不需要拉取或升级；若本地与上游分叉、安装来源不明或命令失败，保留现场并停止更新。升级后通过 `uv tool list --show-version-specifiers` 核对 `serena-agent` 的 required 来源是预期本地 `file://` URL，并检查 uv tool 目录内对应 `serena_agent-*.dist-info/direct_url.json` 的 `url` 指向 `$SERENA_SOURCE` 且 `dir_info.editable` 为 `true`；核实成功后重启 Serena MCP 服务或 Session，再依赖新代码。不得 stash、重置或强制覆盖。

## CUDA 代码理解

- 需要理解 CUDA 代码（包括 `.cu`、`.cuh` 文件，或包含 CUDA 语法的主机/设备代码）时，优先通过 Serena 使用已配置的 C++ LSP/clangd 进行符号、引用和诊断分析。
- 即使本地没有安装 CUDA 库和头文件，也先按 C++ 代码路径进行解析；不要因为缺少 CUDA 依赖就立即安装依赖、修改项目配置或改用大段文本读取。
- 如果 C++ LSP/clangd 无法解析或语言服务未就绪，再按本文件的普通文件工具降级规则处理，并明确记录降级及其对调用链、类型关系或影响范围判断的限制。

## 普通文件工具的边界

- Git 状态、差异、分支和 worktree 仍使用 Git 命令；Serena 不替代仓库状态检查。
- `rg`、`grep` 和普通文件读取用于 Markdown、YAML、JSON、日志、锁文件、生成文件、Serena 不支持的语言、精确文本搜索，以及 Serena 无法处理的文件。
- `rg` 或普通文件读取找到候选后，如果后续需要理解源代码逻辑，应回到 Serena 的符号和引用分析，而不是继续依赖大段文本输出。

## 不可用时的降级

- Serena 未暴露、项目激活失败、语言服务器未就绪或符号分析失败时，不安装依赖、不擅自修改项目配置，直接使用适当的普通文件工具降级。
- 工具降级本身不阻塞不依赖符号关系的任务；如果任务必须依赖调用链、类型关系或影响范围，而现有工具无法提供足够证据，应报告 `BLOCKED` 或 `SKIPPED` 及其影响，不得把未完成的理解标记为通过。
- Serena 的诊断、引用和实现结果只能辅助代码检查，不能替代测试、构建、lint、类型检查或集成验证。

## Worktree 规则

- 需求 worktree 创建后，必须用该 worktree 的准确路径重新激活 Serena 项目。
- 不得继续使用原始工作区的 Serena 项目上下文分析需求 worktree 中的代码。
- 多个 worktree 必须分别绑定各自路径；原始工作区只做其工作流授权的同步、状态或清理工作。
