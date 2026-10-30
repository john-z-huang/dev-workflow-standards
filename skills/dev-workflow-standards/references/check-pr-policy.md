# Issue/PR 工作流审计

使用只读 MCP 工具 `audit_issue_pr_policy` 检查 GitHub Issue/PR。输入字段为必填 `repo_path`，以及可选 `repo`、`issue_number`、`pr_number`、`expected_base` 和 `expected_head`。该工具检查 Issue 或 PR 是否开放、PR base/head 是否符合显式预期，以及 PR 正文是否用 `Closes`、`Fixes` 或 `Resolves` 关联指定 Issue。

至少提供一个编号。`expected_base` 和 `expected_head` 只能与 `pr_number` 一起传入。创建 PR 后、请求审核前，以及需要核验已知 PR 的分支拓扑时调用。该工具不创建、修改、关闭或合并资源，也不提供任意 GitHub API 请求。

它只能判断状态、编号、关键词和分支拓扑，不能判断 Issue 描述是否足够清晰、提交是否混入多个语义模块，也不能代替人工 Review 或项目 CI。需要发现未知 PR 编号时，本服务没有 PR 列表工具；请依据用户提供的信息或现有上下文处理，无法确定时说明当前能力限制。
