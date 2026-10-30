# dev-workflow-standards

此项目将开发规范拆为两层：Skill 文档保留场景分析、顺序、授权与验收；本地 MCP 服务执行固定 Git/GitHub 操作，并提供只读的 Codex 会话事实辅助工具。当前维护的本地 MCP 服务为 Python 实现，由 `uv` 管理，并通过 `uv tool` 安装到本机供 Codex 使用。

工作流判断与开发文案生成通过 OpenAI Python SDK 完成：判断使用 Decisions API，生成使用 Responses API。所有请求固定为 `gpt-6-luna`，强制在调用时读取 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`；缺少任意配置即拒绝请求，不使用默认凭据、默认地址或其他模型。Decisions 使用接口自身机制，生成按任务复杂度显式指定推理强度，默认 `medium`。

## 独立安装 Skill

仓库可以位于任意开发目录。Skill 的唯一指令源在 [`skills/dev-workflow-standards/`](skills/dev-workflow-standards/)，构建时封装进发布包，安装后为普通文件快照，不引用开发仓库。

从本地源码构建 wheel 和 sdist（默认先构建 sdist，再从它构建 wheel）：

```text
uv build ./mcp-server --out-dir ./dist
```

取得构建产物后，在任意目录安装工具；以下 wheel 路径替换为实际绝对路径。本项目不假定已有公开包索引。

```text
uv tool install /absolute/path/dev_workflow_standards_tools-0.2.0-py3-none-any.whl
dev-workflow-standards skills install --dry-run
dev-workflow-standards skills install
dev-workflow-standards skills show
```

默认目标为 `~/.agents/skills/dev-workflow-standards`；`--target /absolute/path/dev-workflow-standards` 可指定完整目标目录。首次安装拒绝所有已有目标，包括旧 Skill、Git checkout 和未知非空目录；不会自动迁移、覆盖或删除旧项目。`~/.codex/skills` 不作为默认自定义安装位置，显式选择兼容路径时也执行同样的保护检查。

安装软件包不会自动更新已安装指令。升级工具后，显式运行：

```text
dev-workflow-standards skills update --dry-run
dev-workflow-standards skills update
```

显式目标安装的，查看和更新也要传同一 `--target`。更新只接受本工具管理且未修改的完整安装；用户修改、额外内容、链接或特殊文件都会阻止覆盖。macOS/Linux 通过原子目录发布保全原安装，不支持的文件系统/平台不降级执行。预览不写文件，独立 Skill 安装离线且不注册 MCP、不读取 OpenAI 凭据、不安装 Hook。旧版共存、中断残留和人工迁移边界见 [完整安装说明](skills/dev-workflow-standards/references/installation.md)。

`dev-workflow-standards` 是独立管理入口；原 `dev-workflow-standards-tools` 仍直接启动 stdio MCP。安装 Skill 后，需要 MCP 功能的仍须按下一节注册服务。

## Codex 中安装

推荐通过本仓库的 [Codex 安装配置脚本](scripts/setup-codex-mcp.py) 一次完成 uv tool 安装、MCP 注册和环境变量转发配置：

```bash
uv run --managed-python -- scripts/setup-codex-mcp.py --install
```

脚本从自身位置定位 `mcp-server/`，不依赖调用时的工作目录。它默认处理 `dev-workflow-standards-tools`，将 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 两个名称合并到该服务的 `env_vars`。只有变量名会写入配置，脚本不读取或打印这两个变量的值，不发起 OpenAI 请求。

可先预览安装和配置计划；`--install --dry-run` 不运行安装或注册命令，也不读写配置：

```bash
uv run --managed-python -- scripts/setup-codex-mcp.py --install --dry-run
```

如果已经通过 `uv tool install ./mcp-server` 安装，省略 `--install` 即可完成注册和转发配置；如果服务也已经注册，只需修复转发声明：

```bash
uv run --managed-python -- scripts/setup-codex-mcp.py --env-only
```

`--env-only` 不安装软件、不调用 Codex CLI，也不会创建缺失的服务条目；其 `--dry-run` 会读取并验证配置，但不写入。重复运行时只追加缺失的名称；已经完整配置时，文件内容和修改时间保持不变。已有转发变量名、服务启动参数、审批设置及其他配置会保留。

常用选项：

| 选项 | 行为 |
| --- | --- |
| `--install` | 安装本仓库的 uv tool，然后注册服务并补齐 `env_vars`。 |
| `--install --force` | 更新已有 uv tool 安装，再完成注册和转发配置。 |
| `--env-only` | 仅修复已有服务的转发声明。 |
| `--server NAME` | 指定服务注册名；默认是 `dev-workflow-standards-tools`。 |
| `--config PATH` | 选择配置文件；注册模式要求文件名为 `config.toml`，并让 Codex CLI 使用同一目录；仅修复模式可指定其他文件名。 |
| `--executable PATH` | 注册已有安装时显式指定可执行文件绝对路径。 |
| `--replace` | 明确允许替换冲突的注册；已有匹配注册直接复用。 |
| `--dry-run` | 预览，不执行写入。 |

配置文件默认是 `$CODEX_HOME/config.toml`，未设置 `CODEX_HOME` 时使用 `~/.codex/config.toml`。写入前验证 TOML 和目标服务，通过同目录临时文件替换，并检测读取后发生的文件变化。无效配置、符号链接或特殊文件、所需变量的远端来源冲突，以及会导致无关排版被重新整理的文档，都会被拒绝；已经完整的仅修复操作保持无改动。发现并发修改时应先核对当前文件，避免其他客户端同时写入。

替换 stdio 注册时会保留原附加设置和转发变量，只更新入口、参数及预期启用状态；HTTP 转为 stdio 时保留通用工具策略和超时设置，不复制旧传输或认证字段。安装、注册、转发配置是不同阶段，后续失败不代表前面的操作已回滚；脚本会给出安全的阶段提示，不输出捕获的子进程内容或配置值。

审批策略仍由用户选择；脚本不覆盖已有策略。如需对未标记为只读的工具启用 Codex 写入确认，可在对应服务段落中设置：

```toml
default_tools_approval_mode = "writes"
```

`env_vars` 允许 Codex 将自身环境中的变量转发给 MCP 子进程。调用工具的终端能读取变量，不代表 Codex 启动的 MCP 进程也能读取；Codex 主进程本身也必须持有这两个非空变量。该设置不会从 Shell 配置文件或 `.env` 文件加载变量。配置含义见 [Codex MCP 官方说明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。

`writes` 会要求 Codex 确认未标记为只读的工具。Skill 的用户授权规则仍然适用；MCP 注解和 Codex 确认都不能替代任务语境中的授权。Codex 桌面端、CLI 和 IDE 共享该配置。修改配置后，重新加载 MCP 服务；若客户端未提供重载入口，退出后重新打开客户端，确保重新创建服务进程。已有 MCP 进程不会自动获得新配置或环境变量。

安装为普通本机 uv tool 后，工具从本机安装位置运行，不依赖仓库 worktree 路径。更新本地源码后，可重新执行安装脚本并添加 `--install --force`。单独运行 `uv tool install` 不会自动配置 Codex；推荐始终通过上述脚本完成安装流程。

### 从旧名称迁移

如果旧版本已安装并注册了 `dev-workflow-standards-mcp`，先移除旧 Codex 注册和 uv tool，再按上面的步骤安装并注册新名称。只对本机确实存在的旧条目执行移除命令：

```bash
codex mcp remove dev-workflow-standards-mcp
uv tool uninstall dev-workflow-standards-mcp
```

此迁移说明只描述命令；不会自动修改本机 Codex 配置或安装。

## 使用

使用 [`SKILL.md`](skills/dev-workflow-standards/SKILL.md) 时按 [`workflows/index.md`](skills/dev-workflow-standards/workflows/index.md) 选择工作流，再按 [`references/mcp-tools.md`](skills/dev-workflow-standards/references/mcp-tools.md) 调用对应工具。所有仓库操作都要传入本次目标项目的绝对 `repo_path`；服务器不会把启动时的目录当作目标仓库。

Python 执行和依赖环境任务按需读取 [`references/python-environment.md`](skills/dev-workflow-standards/references/python-environment.md)，Shell 脚本开发和验证按需读取 [`references/shell-environment.md`](skills/dev-workflow-standards/references/shell-environment.md)。独立脚本无需先进入 Git 工作流；非开发任务不增加环境规则加载步骤。

Git/GitHub 写操作必须先满足工作流中的用户授权和执行层审批；已有授权在原范围内持续有效。服务只接受固定领域参数，不提供任意 shell、git、gh 或项目测试命令。固定写操作和强制门禁使用规定工具；查询优先用 MCP 或已授权 Connector，未覆盖的只读信息查询可按 [`只读查询规约`](skills/dev-workflow-standards/references/read-only-queries.md) 使用 CLI，无须逐次申请额外的业务授权。工具不可用、权限/认证/网络/状态/校验失败时停止对应步骤，不通过 CLI 绕过。

已在当前 checkout 开始工作、需要从当前 HEAD 原地建立工作分支时，使用 `create_repository_branch`。它支持 detached HEAD 和普通分支，保留已暂存、未暂存及未跟踪内容；只新增本地分支并改变 HEAD，不创建其他 checkout。它与切换已有分支的 `switch_repository_branch`、创建新目录的 `create_repository_worktree` 分别适用不同场景。参数、OID 并发条件、Hook 限制和失败后的回读要求见 [`MCP 工具目录`](skills/dev-workflow-standards/references/mcp-tools.md#原地创建工作分支)。

只读按完整子命令、参数、配置和副作用判定：`status` 避免可选 index 写回，差异展示禁用外部 diff/textconv，`fetch` 仍属本地写入；REST 显式 GET，GraphQL 审阅 query/mutation；凭据、文件输出和复合步骤不自动豁免。这是 Agent 操作规范，不是新增命令解析器。用户全局 AGENTS 或已安装 Skill 仍有限制时继续遵守并报告；本仓库修改不自动更新全局规则或重载已安装服务。

### MCP 客户端可见的使用说明

服务初始化指令说明工具分组、选择依据、通用前置条件和典型调用顺序；工具发现返回的描述说明各工具的用途、边界、前置步骤、结果含义及失败后的处理。参数 Schema 同时提供顶层参数和嵌套字段的说明，复杂输入附有合成示例。Code Agent 应先依据这些元数据选择工具，再按参数要求提供事实，无需先自行完成工具承担的判断或内容生成。

维护服务或工具时，必须同步更新客户端可见的说明，不能只改本文件。尤其要区分只读与离线、本地校验与 API 建议、候选内容与已执行操作，以及操作失败与部分副作用。初始化和工具发现检查应验证说明、输入约束和工具注解与实现一致；说明不得改变已有参数类型、默认值或校验规则。

### Codex 会话事实辅助工具

- `get_codex_session_summary_guidance`：获取默认阅读问题与完整摘要模板；可传自定义问题或模板，以用户明确要求为准。
- `order_codex_session_sources`：按 thread ID 去重，按明确的会话创建时间排序；元数据冲突、缺失或时间相同时提示需要澄清。
- `prepare_codex_session_memory`：校验来源、项目路径与 Memory 名称，生成 Serena 写入参数；不读取原会话、不写入文件或 Memory。

原会话通过宿主的 `read_thread` 工具读取，实际保存仍通过 Serena 的项目激活、Memory 读取、写入与回读完成。这些辅助工具只能校验结构，不能证明摘要忠实于原文，也不能授予持久化权限。工具签名见 [`references/mcp-tools.md`](skills/dev-workflow-standards/references/mcp-tools.md)，事实来源和更新边界见 [`references/codex-session-facts.md`](skills/dev-workflow-standards/references/codex-session-facts.md)。

### API 判断与生成工具

- `decide_skill_workflow`：根据明确流程条件选择工作流。
- `decide_codex_session_action`：判断查询历史、查询项目、澄清/阻塞，以及摘要创建、更新或跳过的分支。
- `generate_skill_content`：根据证据、查询重点和用户格式生成 Issue、PR、提交信息、计划、交接或历史会话摘要候选内容。

MCP 的分支名、提交信息和 Issue/PR 策略检查在本地硬校验通过后调用 Decisions；API 失败不能返回通过。原始本地校验服务、Hook、Git 写工具的前置检查及不联网的会话辅助工具保持确定性执行。API 工具不执行生成内容里的命令，不自动创建 Issue/PR 或保存 Memory。

MCP 进程必须能继承上述两个环境变量；不要把真实值写入仓库。API 只接收调用者显式提交的必要事实，不自动发送整个仓库或会话。输入字段、Prompt 边界、返回结果与推理强度配置见 [`references/openai-workflow-tools.md`](skills/dev-workflow-standards/references/openai-workflow-tools.md)。

若手动运行成功，但 Codex 调用返回 `missing_api_key`，先检查上面的 `env_vars` 转发配置、Codex 主进程的变量存在性，以及服务是否已重新加载。uv tool 安装提供独立的执行环境，不会替 MCP 客户端补齐凭据。`missing_api_key` 表示服务进程中的 Key 缺失或为空，请求尚未发送；Key 检查先于 Base URL，因此两项都缺失时也只返回 `missing_api_key`。Key 存在而 Base URL 缺失时返回 `missing_base_url`。排查时只检查存在性和非空状态，不输出配置值；不要通过给服务增加凭据文件回退来绕过环境要求。

## 项目结构

- `skills/dev-workflow-standards/SKILL.md`：唯一 Skill 入口、共用边界和加载顺序。
- `skills/dev-workflow-standards/workflows/`：场景判断、先后依赖、授权和完成条件。
- `skills/dev-workflow-standards/references/`：按需加载的决策细节、独立安装说明和 MCP 工具映射。
- `mcp-server/`：Python/uv MCP v2 stdio 服务和固定操作工具。
- `archive/mcp-server-ts/`：已归档且不再支持的历史 TypeScript MCP 实现；其历史说明见该目录的 [`README.md`](archive/mcp-server-ts/README.md)。
- `scripts/`：Codex 安装配置脚本，以及供标准 Git Hook 集成使用的可移植校验资产；`.githooks/`：Hook 入口。

当前 MCP 服务实现与调用约束见 [`mcp-server/pyproject.toml`](mcp-server/pyproject.toml) 和 [`references/mcp-tools.md`](skills/dev-workflow-standards/references/mcp-tools.md)。

## 本地验证

在 `mcp-server/` 使用项目环境运行离线测试：

```text
uv sync --managed-python
uv run --managed-python -- python -m unittest discover -s ../tests -v
```

构建测试会在临时目录生成并解包 sdist、重建 wheel、安装到隔离环境后运行 CLI，不会写入现有用户 Skill 目录。

`uv sync` 的可编辑开发环境不提供已封装的 Skill 快照；安装命令需从完整 wheel 安装的工具运行。资源缺失时安装器会拒绝执行，不从源码目录回退读取。

### Codex SDK 集成测试

Codex Python SDK 仅在 `codex-test` 测试依赖组中声明，测试驱动位于 `tests/codex_sdk_smoke.py`；运行时不导入 SDK，发布包不依赖 SDK，也不包含测试驱动。SDK 及匹配的 CLI 版本由 `mcp-server/uv.lock` 锁定。普通离线测试不安装该依赖组、不启动 Codex 或发起模型请求。

先按上面的命令构建 wheel，再从 `mcp-server/` 执行：

```text
uv run --locked --group codex-test -- python ../tests/codex_sdk_smoke.py --wheel ../dist/dev_workflow_standards_tools-0.2.0-py3-none-any.whl
```

默认只执行 SDK/CLI 初始化、临时 MCP 注册、工具发现和直接工具调用，不发起模型请求。测试将 wheel 安装到临时目录，核对加载的确是该安装，再使用临时 Codex 配置和只读测试工作区；不读取原用户的 Codex 配置、登录文件或修改现有 Skill 安装。仅暴露不联网、不读历史、不写 Memory 的 `get_codex_session_summary_guidance` 工具，输入为合成问题和模板。

需要真实模型端到端检查时显式添加 `--live`：

```text
uv run --locked --group codex-test -- python ../tests/codex_sdk_smoke.py --wheel ../dist/dev_workflow_standards_tools-0.2.0-py3-none-any.whl --live
```

所有 SDK 测试固定模型 `gpt-6-luna`、推理强度 `medium`，不接受命令行或环境变量覆盖，也不自动切换模型。两种模式都要求当前进程提供非空的 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`；每次读取并显式配置测试 provider，不使用默认地址或其他登录凭据。真实值不写入仓库或配置文件，不输出原始 SDK/HTTP 错误。

`--live` 会发起真实模型请求并产生相应费用。测试检查 Codex 回读的模型/推理强度、MCP 发现结果、直接调用结果及模型实际发出的 `item/completed` 工具调用事件；模型仅回复“测试通过”不会被采纳。失败不重试或回退；总时限为 120 秒。输出仅含安全状态、固定模型/强度和实际工具调用计数。普通离线测试另覆盖配置缺失时零启动、环境读取、模型限制、错误脱敏及发布包依赖隔离。
