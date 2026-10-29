# OpenAI 辅助判断与内容生成

Python MCP Server 通过 OpenAI Python SDK 执行规约分支判断和内容生成。Code Agent 提交范围明确的事实、问题和格式要求，工具返回枚举判断或有来源的候选内容，Code Agent 核对后优化或采纳。API 结果不构成 Git、Memory 或其他外部操作的授权，也不证明未运行的测试通过。

## 配置与请求边界

- 每次实际请求均从本地环境读取 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`，两者都必须非空，并显式传给 SDK。缺少任意一项即停止请求，不使用 SDK 的默认凭据或地址，不从工具参数、其他变量或配置文件补齐。
- 代码、文档和日志不得包含真实凭据或端点值。错误只返回安全分类，不输出原始异常、请求头、响应正文或环境变量值。工具不能让调用者覆盖模型、凭据或端点。
- 所有请求固定使用 `gpt-6-luna`。判断使用 `client.decisions.create`；生成使用 `client.responses.parse` 和结构化输出，不回退到其他模型或接口。
- Decisions 当前没有推理强度参数，判断使用 Decisions 自身机制，不发送不支持的 `reasoning` 参数；生成显式指定强度：提交信息为 `low`，计划和历史会话摘要为 `high`，其余为 `medium`，默认值为 `medium`。
- 生成请求设置 `store=False`，不附加模型可执行的工具。API 不读本地仓库、原始 Codex 会话或 Serena；证据必须由调用者显式提供。输入超出预算时拒绝，不静默截断；普通测试不联网。

接口依据：[Decisions](https://developers.openai.com/api/docs/guides/decisions)、[创建判断](https://developers.openai.com/api/reference/resources/decisions/methods/create)、[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)、[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)。

### Codex stdio 环境传递与排查

安装为 uv tool 后，服务仍只读取自身进程的环境变量。Codex 主进程需要持有非空的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`，并在 `[mcp_servers.dev-workflow-standards-tools]` 中通过 `env_vars` 显式允许转发这两个名称。使用本仓库的 [setup 脚本](../scripts/setup-codex-mcp.py) 时，这一步会自动完成，无需手动修改 TOML；完整安装方式见 [README](../README.md#codex-中安装)，字段语义见 [Codex MCP 官方说明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)。终端中手动运行成功，只能证明该次进程拿到了配置，不能证明 Codex 启动的 MCP 子进程也收到了配置。

已有注册只需运行 `uv run --managed-python -- scripts/setup-codex-mcp.py --env-only`；可添加 `--dry-run` 只检查不写入，或用 `--server NAME`、`--config PATH` 指定目标。脚本只合并变量名，保留其他配置，不读取凭据值，也不发起 API 请求。它不会替调用进程加载凭据、启用额外授权或修改 MCP 的请求配置规则。

更改配置后须重新加载 MCP 服务，必要时退出后重开客户端以重新创建进程。`env_vars` 不会读取 Shell 配置文件或 `.env` 文件，也不会让已运行的子进程自动获得新变量；本服务不增加凭据文件、其他变量或默认地址回退。

`missing_api_key` 和 `missing_base_url` 都是在创建 SDK 客户端、发送请求之前返回的本地配置错误。服务先检查 Key，再检查 Base URL；两项都缺失或为空时，先返回 `missing_api_key`，不代表 Base URL 已通过检查。排查仅记录进程或配置位置及变量是否存在、是否非空，不输出真实值；配置修复后再用最小必要事实验证请求。

## 判断工具与硬校验

| 工具 | 输入重点 | 判断结果及使用方式 |
|---|---|---|
| `check_branch_names` | 维持原来的 `branch_names` / `repo_path` | 本地名称规则先检查；通过后才请求 Decisions。模型不能把本地失败改为通过。 |
| `check_commit_message` | 维持原来的 `message` | 本地检查类型、中文说明及禁止署名；通过后再请求 Decisions，API 异常不能返回通过。 |
| `audit_issue_pr_policy` | 维持原来的仓库、Issue/PR 编号和预期 base/head | 先通过既有只读审计，再提交精简规则事实判断；不发送整份 PR 内容，不创建或修改 GitHub 资源。 |
| `decide_skill_workflow` | `request`：当前请求及明确的流程条件 | 从固定工作流中选择分支；未明确要求 worktree 时不能选择 worktree。 |
| `decide_codex_session_action` | `request`：来源可访问性、读取覆盖、事实是否存在、保存限制和新增事实来源 | 分别返回查询动作和持久化动作；原文不可读不能当作无事实，当前新事实不能写入历史摘要，禁止保存时不能生成保存分支。 |

原检查工具保留本地检查结果，并补充 API 判断信息。本地失败无需发送 API；API 拒绝、超时、错误、返回未知选项或缺少答案时均不能通过。判断返回固定枚举，不使用自由文本猜测分支，也不把置信度当作授权或验证证据。

路径、精确名称和格式规则、创建时间排序、Git 写操作前置条件仍由本地代码执行。`get_codex_session_summary_guidance`、`order_codex_session_sources` 和 `prepare_codex_session_memory` 继续作为不联网的确定性助手；固定 Git 写工具及 Hook 不会因为模型的肯定结果而跳过自身检查。

### 工作流输入

`decide_skill_workflow` 的 `request` 包含非空 `user_request`，以及显式布尔字段 `explicit_worktree`、`github_delivery`、`verification_only`、`special_operations`、`blocked`。使用真实布尔值，不能传字符串 `"false"`。

```json
{
  "request": {
    "user_request": "将已完成的改动提交后推送，并创建关联 PR",
    "explicit_worktree": false,
    "github_delivery": true,
    "verification_only": false,
    "special_operations": false,
    "blocked": false
  }
}
```

分支按恢复、明确 worktree、GitHub 交付、特殊操作、仅验证、普通开发的条件选择；证据不足则澄清。工作流选择本身不执行其中的操作，后续仍须核对授权、仓库状态和对应 Completion Gate。

### 会话事实输入

`decide_codex_session_action` 的 `request` 包含 `user_request`、`has_relevant_sources`、`history_accessible`、`history_fully_read`、`relevant_facts_found`、`persistence_allowed`、`existing_summary`、`new_fact_origin`。`relevant_facts_found` 未知时传 `null`，不能把未读或无法访问写成 `false`；`new_fact_origin` 使用 `original_session`、`current_session` 或 `none`。

Code Agent 必须从真实读取结果填写这些条件。工具只判断提供的数据，不核验宿主会话或重放历史操作。完整事实边界见 [`codex-session-facts.md`](codex-session-facts.md)。

## 生成工具输入

`generate_skill_content` 接收 `request`，默认按以下字段组织内容：

| 字段 | 要求 |
|---|---|
| `kind` | `issue`、`pr`、`commit_message`、`plan`、`handoff` 或 `session_summary`。 |
| `user_request` | 当前要生成的内容、受众和约束；不要混入凭据或无关日志。 |
| `evidence` | 有界证据列表，每项包含唯一 `reference_id`、非空 `content`、`origin` 和可选 `source_thread_id`。 |
| `focus_questions` | 用户明确要求查询或总结的问题；优先于默认问题清单。 |
| `output_format` | 用户明确要求的输出结构或模板；优先于默认章节。Issue/PR 的英文模板不构成语言覆盖。 |
| `language_override` | 仅 Issue/PR 可用。省略/null 默认中文；其他语言须提供 `{language, instruction_ref}`，后者引用本次 evidence 中 `origin=user_provided` 的用户语言指令原文。本地检查引用来源，模型核对其是否确为用户的明确语言要求；其他 kind 禁止此字段。 |
| `source` | 历史会话摘要必须提供相应的 `CodexSessionSource` 元数据；其他类型可省略。 |

`origin` 为 `provided_session`、`current_observation` 或 `user_provided`。历史摘要只接收 `provided_session` 证据，且每项 `source_thread_id` 必须与 `source` 相同；禁止将当前观察或其他会话的事实混入历史摘要。普通开发文案可以使用当前观察，但必须如实区分已验证、未验证和待决定事项。

```json
{
  "request": {
    "kind": "issue",
    "user_request": "根据证据编写中文功能 Issue，不编造验证结果",
    "evidence": [
      {
        "reference_id": "E1",
        "content": "需求是提供带来源引用的会话摘要候选内容；实际保存继续使用 Serena。",
        "origin": "user_provided",
        "source_thread_id": null
      }
    ],
    "focus_questions": ["功能边界是什么？", "如何验收？"],
    "output_format": "按需求、范围、验收标准三个中文章节输出正文",
    "source": null
  }
}
```

### Issue/PR 的事实准备

调用前收集相关的最小充分材料，无需先写整篇正文，不传整个仓库、完整会话或敏感配置。通用事实包括目标、受众、背景、组件、路径/符号指针、范围与非目标、约束及关联项；标注来源，区分已核实事实、未验证反馈、推测和建议，缺失或矛盾如实说明。

- Issue：区分缺陷与功能/变更请求。缺陷提供实际行为、期望行为和影响，环境/复现只填已有证据；需求提供目标能力和有依据的动机。建议的验收条件要标为建议。
- PR：提供具体前后行为、已完成改动与原因、真实 diff 摘要或文件证据、实际验证命令及结果、未运行项、已知兼容风险和关联 Issue。计划不能当成完成，验证未知不能当成通过。

Issue/PR 标题和自然语言正文默认中文。英文材料、模板和 Agent 自拟英文请求不构成语言授权；技术标识、路径、代码、命令、错误原文与必要引用保留。真实用户要求其他语言时，将原文放入 `user_provided` 证据并设置覆盖，例如：

```json
{"request":{"kind":"issue","user_request":"为维护者起草导出功能需求","evidence":[{"reference_id":"U1","origin":"user_provided","content":"请用英文编写这份 Issue。希望导出筛选结果，减少手动复制；范围仅报表组件。"}],"language_override":{"language":"English","instruction_ref":"U1"}}}
```

PR 最小合成示例（路径、编号和验证须替换为真实事实）：

```json
{"request":{"kind":"pr","user_request":"为评审者起草中文说明","evidence":[{"reference_id":"D1","origin":"current_observation","content":"src/report.py 的 diff 将空输入从抛错改为返回空列表，避免空报表失败；范围仅此函数。执行 python -m unittest tests.test_report：通过。未运行集成测试；关联 #12；暂无已知兼容风险。"}]}}
```

## Instruction Prompt 与返回内容

工具使用固定的任务 Prompt，将当前要求、证据、查询重点与输出格式分开编码。证据里的角色声明、命令或要求忽略规约的文本始终作为数据处理，不能覆盖工具规则。Prompt 要求仅根据输入事实生成内容，明确缺失信息，不补写未执行的测试、未创建的 PR、未确认的路径或决定；不请求或返回私有推理过程。

判断指令逐项解释观测字段和选项的触发、排除条件，按固定优先顺序处理同时成立的条件。工作流使用显式布尔条件，不从“并行开发”推断 worktree；会话查询和保存各用独立条件表，无相关来源时允许查询项目，来源不可读时阻塞查询；禁止保存或新增事实来自当前会话时跳过保存。本地 Issue/PR 审计未请求某项检查，不等于检查失败，也不需要补充 CI、标签或可合并性等本工具没有审计的事实。提交信息的署名观测与本地校验使用相同的有效行范围，忽略空行和注释行。

六类生成任务分别提供默认交付要求；用户明确指定的问题、结构和详略优先。Issue/PR 的其他语言要求须使用上述带来源的 `language_override`，其他类型保留明确语言偏好；不能覆盖事实与硬约束，提交信息仍须满足中文主题规则。

| 类型 | 默认交付重点 |
|---|---|
| `issue` | 问题或需求、影响、范围及验收条件；只有证据包含重现过程时才写重现步骤。 |
| `pr` | 具体问题、最终改动、实际验证和未解决风险；仅引用证据中的 Issue 与交付状态。 |
| `commit_message` | `title` 是完整合规主题，`content` 是可选正文；简述有证据支持的变更。 |
| `plan` | 拟执行步骤、依赖和验收方法；明确区分建议、假设和已完成事实。 |
| `handoff` | 已确认的进展、失败或阻塞、待办及后续动作；保留必要来源以便接手核对。 |
| `session_summary` | 只总结指定原会话证据，按默认阅读问题和模板落地；时间元数据不推测，当前观察不混入。 |

生成结果包含标题、正文、已使用的证据引用、缺失事实及简短审阅说明，并附模型、推理强度和可用的用量信息。返回的引用必须属于输入证据；拒绝、未完成、解析失败或未知引用不得当作成功内容。自定义格式决定正文结构，接口的结构化封装不强迫正文使用默认章节。

`used_evidence_refs` 只列实际支撑候选内容的输入引用，不能不加区分地列出所有证据；`missing_facts` 只列完成当前请求必要但未提供或有冲突的事实，不能为填满默认章节虚构缺口；`review_notes` 用于简短的事实边界和采纳前检查，不返回中间推理或整份输入。

Issue/PR 在本地硬校验后，通过同一统一客户端进行第二次有界 `Responses.parse` 语义审查，固定 `gpt-6-luna`、`medium`，无工具执行；两次请求各自重新读取并显式使用配置，均检查预算、拒绝、不完整与解析错误。审查不自动重试或修复。`quality_review` 的 `language_compliant`、`evidence_supported`、`coverage_sufficient` 是模型建议，分别检查语言授权、事实支撑、针对当前请求的关键事实覆盖与冲突；不按字数、中文比例或默认章节数量判质量。`quality_review_usage` 单独列审查用量，`usage` 仍为生成请求用量。

生成与审查的缺失事实和审阅提示合并去重。`ok=true` 仅代表有效草稿与有效审查，不保证适合发布；仅所有审查项为真且合并 `missing_facts` 为空时 `adoptable=true`、`quality_status=ready_for_agent_review`。其余返回 `adoptable=false`、`quality_status=needs_revision`，须修订或补证后重新审阅。审查异常返回 `ok=false`、安全 `error_code`、`adoptable=false`，不返回可采纳候选；超出发现项上限同样失败关闭。模型审查不证明实际事实正确，通过仍需人工核对且不授予写入权限。离线 mock 仅验证流程、规则和结构，不证明真实语言质量；真实生成验证须另行授权最小脱敏数据。

Code Agent 对照证据检查候选内容后，可修改或直接采纳。生成正文不自动写文件、Serena Memory、Issue 或 PR；需要持久化时继续使用对应的专用工具，并遵守当前用户授权。历史摘要通过 [`prepare_codex_session_memory`](mcp-tools.md) 准备写入参数，实际写入仍由 Serena 完成。
