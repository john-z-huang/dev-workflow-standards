# GitHub 交付工作流

只用 `gh` CLI 或已授权 GitHub Connector/App；禁止浏览器/浏览器自动化。加载本工作流本身不授予网络、认证、推送、Issue、PR 或合并权限；但用户明确要求将改动推送到 GitHub 时，该请求授权按本流程自动补建缺失 Issue、推送分支并创建关联 PR，不再另行询问。该授权不包含自动关闭或合并 PR。

操作细节：[`github.md`](../references/github.md)；PR 审计：[`check-pr-policy.md`](../references/check-pr-policy.md)；合并方式：[`squash-merge.md`](../references/squash-merge.md)。

## 队列

| 步骤 | 完成条件 |
|---|---|
| 确认仓库和访问 | 仓库、网络、认证已确认 |
| 准备 Issue | 开放 Issue、类别 label、本人 assignee 已核验 |
| 推送 | 本地门禁和推送授权通过 |
| 创建/检查 PR | 拓扑、关联和 assignee 已核验 |
| 审计 PR | 只读策略审计通过 |
| 合并 | 获准合并且 main 使用 squash |

## 1. 确认仓库和访问

- 先确认目标仓库、Issue/PR、base/head；不猜 owner、用户名、编号或权限。
- `gh` CLI 先查 API 连通性，再查认证；云端无 `gh` 只用已授权集成，不改用浏览器。
- `GH_TOKEN` 不打印、回显、插值、记录、写文件或要求用户粘贴；重新认证只通过标准输入传给 `gh auth login --with-token`。
- 网络失败或认证失败时改读 [`recovery-and-exceptions.md`](recovery-and-exceptions.md)。

## 2. 准备 Issue

推送前必须有开放 Issue。用户明确要求推送时，如果没有相关联的开放 Issue，直接创建并完成核验，不再主动询问。Issue 至少写清需求/缺陷、影响、预期行为、验收标准；必要时写复现、约束和依赖。

1. 用 `gh api user --jq .login` 获取当前账号。
2. 先读取现有 labels，选择至少一个工作类型 label（优先仓库已有标签）。
3. 先将完整 Issue 描述生成到本地 Markdown 文件，例如 `issue-body.md`；然后使用 `gh issue create ... --body-file issue-body.md --label "<类别标签>" --assignee "@me"` 创建。禁止在 `--body` 或其他命令行参数中直接内联 Markdown 正文。
4. 创建时同时写入 label 和 `--assignee @me`，创建后回读状态、label、assignee。
5. 只有集成不能枚举 labels 但能写入/回读时，才使用可靠证据或保守候选降级；写入失败且修正后仍失败，禁止推送。

## 3. 推送

推送前确认：用户授权；正确工作区（如采用 worktree 则为正确 worktree）、分支和 remote；开放 Issue、类别 label、本人 assignee；测试和检查通过；分支/提交/暂存范围合规；堆叠 PR 的 base 已明确。

## 4. 创建/检查 PR

- 用户明确要求推送时，推送成功后默认创建关联 PR，不再主动询问；创建后保持 PR 开放，不自动关闭或合并。
- 显式确认仓库、base、head、Issue；堆叠 PR 不默认用 main。
- 先将完整 PR 描述生成到本地 Markdown 文件，例如 `pr-body.md`；在正文中用 `Closes #`、`Fixes #` 或 `Resolves #` 关联开放 Issue，并说明范围和验收。然后使用 `gh pr create ... --body-file pr-body.md ...` 创建，禁止在 `--body` 或其他命令行参数中直接内联 Markdown 正文。
- 创建时默认指派当前账号；接口不支持时立即补写并回读。
- 创建后核验 state/base/head/关联/assignee，并按 [`check-pr-policy.md`](../references/check-pr-policy.md) 运行只读审计。

## 5. 合并

仅在用户授权、PR 可合并且所需 checks 通过时合并。按 [`squash-merge.md`](../references/squash-merge.md) 选择合并方式；PR base 为 `main` 时必须使用 squash。合并后核验 PR 和 main 的单一代表提交；仓库禁止 squash 时停止并报告。
