# 个人 Fork 的上游同步与长期维护

仅当 `audit_repository_state` 返回非空 GitHub `parent` 时启用。独立仓库跳过本文，沿用项目自己的默认分支、开发分支和保护规则。

## 拓扑

```text
upstream/main → origin/main → personal-<project> → feat/fix/docs/... → PR
```

- `upstream` 是原项目，只读同步来源；`origin` 是个人 Fork。
- `main` 只镜像上游默认分支，不承载个人需求提交。
- 个人长期改动放入 `personal-<project>` 或 `personal/<project>`；以已核验的项目约定为准。
- 需求分支从最新个人维护分支创建，PR base 默认是该分支。

## 同步上游

先调用 `audit_repository_state` 核对 Fork、仓库、默认分支、remote 和工作区。

1. 确认 `upstream` remote 已配置。MCP 不会猜 URL 或首次添加 remote；若缺失，停止并报告，不手写命令绕过。
2. 在工作区允许时，依次使用 `fetch_upstream_branch` 获取上游分支、`switch_repository_branch` 切到本地 `main`、`merge_upstream_branch_fast_forward` 快进更新 `main`。
3. 仅当 `main` 与 `upstream/main` 快进一致且用户授权时，调用 `push_fork_main_fast_forward` 更新 `origin/main`。
4. 切换回已核验的个人维护分支。若该分支需新建或设置跟踪关系，当前没有对应 MCP 工具；保留现场并报告。

任何 fetch、切换、快进或推送失败都保留现场，不使用过期 remote-tracking 信息、任意 SHA、重置或强推绕过。

## 日常开发与保护

- 需求提交和推送只在需求分支进行；`push_issue_branch_to_origin` 的固定规则拒绝把需求分支推入主分支。
- 需求 PR 显式以个人维护分支为 base，通过 `create_github_pull_request` 提交并核验。
- `main` 和个人维护分支应禁止删除及强推；个人维护分支应要求通过 PR。保护规则尚未封装为本服务 MCP 工具；回读可按 [`read-only-queries.md`](read-only-queries.md) 使用已授权 Connector 或显式 GET CLI。创建/修改仍报告缺少专用写能力，不改用通用 shell/gh runner 执行；回读权限失败不能绕过或当作无规则。

## 发现拓扑异常

- `origin/main` 含个人需求提交时，先核验提交归属；不能继续把它当作上游镜像。
- `merge_upstream_branch_fast_forward` 失败表示发生分叉或基线不符；保留状态并检查差异，不改写公开历史。
- 个人维护分支含未合并需求时，确认 PR base/head；不要直接 rebase 已公开分支或裸强推。
- 更改默认分支、规则集或保护策略需要用户明确授权和执行层审批；目前相应写操作不受 MCP 支持，故在写入前停止。只读回读按前述规约处理。
