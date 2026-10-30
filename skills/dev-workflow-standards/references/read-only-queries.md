# Git/gh 只读查询边界

本规约允许 Code Agent 在当前任务和已核实的仓库范围内自主查询，无须逐次申请额外的业务授权。它不覆盖上级指令、宿主审批、沙箱或产品限制；也不是通用命令执行器或技术安全隔离机制。

## 入口选择与失败处理

1. 专用 MCP 或当前已授权的 GitHub Connector/App 能满足查询时，优先使用。repo-bound MCP 调用仍须传入准确的绝对 `repo_path`。
2. 工具未覆盖所需的信息查询时，允许按本文执行只读 CLI；先核实本地根目录或远端 `owner/repo`，限定字段、路径和输出数量。CLI 用 `git -C` 或 `gh --repo` 等明确目标，不依赖偶然的启动目录。
3. 工作流要求的 `audit_repository_state`、`check_branch_names`、`check_commit_message`、`check_staged_changes`、`audit_issue_pr_policy` 等门禁仍用规定工具。补充查询不替代这些门禁，也不把 API 失败视为通过。
4. “查询未覆盖”不同于工具不可用或执行失败。缺失必需工具、权限/认证/网络失败、脏工作区、状态冲突或校验拒绝时，停止对应步骤，保留现场并按[恢复流程](../workflows/recovery-and-exceptions.md)报告。不能换 CLI、旧结果或兼容脚本绕过；独立且不依赖失败结果的查询可继续。

## 按完整操作判定

逐项核对实际子命令、全部参数、配置及附带效果，不能只按 `git`、`gh` 或子命令前缀放行。以下示例使用合成路径和仓库，调用前替换为已核实目标；示例只说明合法形态，不要求重复执行已有工具覆盖的查询。

| 查询 | 完整调用示例 | 排除项或条件 |
|---|---|---|
| 工作区状态 | `git --no-pager --no-optional-locks -C /workspace/repo status --short` | 避免默认刷新 index 的可选写回；不能作为强制仓库审计的替代品。 |
| 有界历史 | `git --no-pager --no-optional-locks -C /workspace/repo log --no-ext-diff --no-textconv -n 20 --oneline -- src/` | 不运行别名、外部 pager、diff 驱动或文本转换。 |
| 提交内容 | `git --no-pager --no-optional-locks -C /workspace/repo show --no-ext-diff --no-textconv --stat HEAD -- src/` | 不使用 `--output` 写文件；先确认所需对象在本地。 |
| 工作区差异 | `git --no-pager --no-optional-locks -C /workspace/repo diff --no-ext-diff --no-textconv -- src/` | 暂存内容可加 `--cached` 查看，但不替代 `check_staged_changes`。 |
| 分支或标签列表 | `git --no-pager --no-optional-locks -C /workspace/repo branch --list`；`git --no-pager --no-optional-locks -C /workspace/repo tag --list` | 创建、删除、移动、重命名或修改 tracking 均为写操作。 |
| remote 名称 | `git --no-pager --no-optional-locks -C /workspace/repo remote` | 不默认输出 URL，避免暴露嵌入式凭据；`add`、`set-url`、`remove`、`update` 不在豁免内。 |
| Issue/PR 查询 | `gh issue view 65 --repo example/project --json number,title,body,state`；`gh pr list --repo example/project --limit 20 --json number,title,baseRefName,headRefName` | 不附加 `--web`、checkout、download、comment、edit、merge 等动作。 |
| 仓库信息 | `gh repo view example/project --json nameWithOwner,defaultBranchRef,parent` | 使用明确的仓库参数，不进行 clone、sync 或配置修改。 |
| REST 查询 | `gh api --method GET repos/example/project/issues/65 --jq '{number,title,state}'` | 仅已核对的只读 GitHub 端点；不任意切换 hostname、覆盖认证头或输出完整请求头。 |

`git fetch`、pull、checkout/switch、add、commit、reset、stash、配置修改及 worktree 增删等会改变本地状态；push、Issue/PR 创建/修改、评论和合并等会改变远端状态，均不属于只读豁免。`--dry-run` 或“不改远端”不自动证明完整调用无副作用。

只读命令也可能受执行环境影响：外部 pager、Git/gh 别名、扩展、配置指定的 helper、文件系统监视器或 partial clone 缺失对象的隐式抓取均须核对；未知效果不能推定安全。示例中的参数不能消除所有配置副作用；如对象不在本地或无法核实 helper 行为，停止该查询，不修改配置或自动下载来补齐。既有认证由已授权工具正常使用，不代表允许主动读取、打印或导出凭据。

## REST 与 GraphQL

- REST 始终显式指定 `--method GET` 并核实端点用途。`gh api` 添加 `-f`/`-F` 会使默认方法转为 POST；需要 GET 参数时也必须保留显式 GET。方法名本身不能证明陌生端点只读。
- GraphQL 通过 POST 传输不自动属于写操作；须审阅完整、静态可见的 query、变量、fragment 和选中的 operation。只允许已核实的查询，排除 mutation、含混的多操作文档或无法核实的动态拼接。例：`gh api graphql -f query='query { repository(owner:"example", name:"project") { nameWithOwner } }'`。这里的 POST 承载已明确的 GraphQL query，不适用 REST GET 规则。
- 查询可以联网，但不扩大仓库、数据和权限范围。分页须有任务需要和输出预算，不读取无关账号或敏感信息。

## 文件、复合命令与授权

- 重定向、`--output`、下载、tee、管道后续程序、命令替换及命令连接中的每个实际步骤须分别判断，不能继承外层查询的豁免。获准的项目文件编辑和测试仍按原工作流处理，不因本规约自动禁止或授权。
- 禁止输出、回显、插值或持久化凭据；错误报告只保留非敏感摘要。不要执行 `gh auth token` 或批量输出可能含秘密的配置。
- 写操作必须先有当前任务范围内的用户意图授权，再满足宿主审批、沙箱权限和既有工作流门禁；优先使用规定写工具，未封装的写操作停止并报告。已授予且未撤回的授权在原范围内持续有效，无须重复索取；新增动作或扩大范围需相应授权。
- 本仓库文档调整不修改用户全局 AGENTS、已安装 Skill 或运行中的服务配置。如果上层仍禁止 CLI，当前会话继续遵守上层规则，报告冲突来源及影响，不能用仓库文档覆盖它。

## 核对案例

交付时确认：未覆盖的 PR 列表查询可按上述入口执行；同名 `branch --list` 与 `branch -D` 分类不同；`fetch` 仍走写流程；REST 参数不能悄悄切换方法；GraphQL mutation 不放行；工具失败不走 CLI 后备；强制检查不被手工 diff 替代。本文描述 Agent 的选择规则，不声称新增了命令解析、拦截或审批能力。

依据：[Git status 后台刷新](https://git-scm.com/docs/git-status#_background_refresh)、[Git diff 外部驱动和 textconv](https://git-scm.com/docs/git-diff)、[gh api 方法和参数](https://cli.github.com/manual/gh_api)。
