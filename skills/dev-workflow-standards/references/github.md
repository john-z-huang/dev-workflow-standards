# GitHub 操作策略

固定写操作和强制 GitHub 门禁使用 [`mcp-tools.md`](mcp-tools.md) 中规定的工具；一般查询优先用专用 MCP 或当前已授权的 GitHub Connector/App，未覆盖的只读信息按 [`read-only-queries.md`](read-only-queries.md) 使用 CLI。禁止浏览器和浏览器自动化。服务器调用本机 `gh` 身份，不收集、不输出令牌。

## 授权、网络与身份

- 每次外部写操作都须有覆盖该操作的用户授权并满足执行层审批；已有授权在原范围内持续有效，无须重复索取。Skill 加载、工具可用或注解均不自动授权。
- GitHub 网络/认证问题按恢复流程处理；不得因代理/API 不通直接判定登录凭据失效，也不得要求用户粘贴 token。
- `GH_TOKEN` 与其他凭据不得打印、回显、插值、记录或写入文件/参数/错误报告。出错时只保留非敏感摘要。
- 目标仓库、Issue/PR 编号、assignee 和 base/head 必须来自当前任务或工具返回值，不猜测账号/权限。

## Issue

任何待推送功能或修复必须有关联的开放 Issue。用户明确要求推送时，若没有相关 Issue，可以按该用户指令直接补建，不再另问。

1. 用 `audit_repository_state` 确认目标仓库与 GitHub 身份；用 `list_github_issue_labels` 读取仓库现有标签。
2. 按 Issue 的主要目的选择至少一个已有工作类型 label；辅助标签不能替代工作类型 label。不得把未核验的 GitHub 默认标签说成仓库已有标签。
3. 正文说明需求/缺陷、影响、预期行为和验收标准，必要时补充复现、约束或依赖。
4. 获得创建授权后调用 `create_github_issue`。工具只接受已存在的 label，默认指派当前账号并回读状态/labels/assignee；校验失败时停止推送。

## 推送与 PR

- 推送前检查开放 Issue、分类 label、本人 assignee、分支拓扑、测试、提交范围和用户授权。
- `push_issue_branch_to_origin` 只推送当前同名分支到 `origin`，不强推；Fork 的镜像 main 使用独立工具并遵守 Fork 流程。
- PR 正文需说明范围和验收，并用 `Closes #N`、`Fixes #N` 或 `Resolves #N` 关联 Issue。获授权后使用 `create_github_pull_request`；工具通过临时 body-file 创建、默认指派本人并保持 PR 开放。
- 创建后用 `audit_issue_pr_policy` 核对开放状态、关联关系和预期 base/head。推送/创建/审计失败时停止后续交付。

## 合并

不自动合并 PR。只有用户明确授权且 required checks 通过、PR 可合并、无 changes-requested 时调用 `merge_github_pull_request`。Fork 需求 PR 合并到个人维护分支；`main` base 只允许 squash。合并后回读实际 base 和状态。

## 能力边界

MCP 不提供 branch protection/rulesets 的增删改查、首次 upstream URL 配置或 GitHub 账号修复工具。保护规则回读等未覆盖的信息查询可按只读规约使用已授权 Connector 或显式 GET CLI；权限不足等失败仍须停止对应查询，不能把失败解释为无规则。未封装的写操作保留现场并报告，不使用原始命令或通用执行器绕过。
