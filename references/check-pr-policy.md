# Issue/PR 工作流审计

## 功能描述

`scripts/check-pr-policy.py` 通过 GitHub CLI 的 REST API 只读检查：

- Issue 是否处于开放状态；
- PR 是否处于开放状态；
- PR 的 base/head 是否符合显式指定的预期；
- PR 描述是否包含 `Closes #<Issue>`、`Fixes #<Issue>` 或 `Resolves #<Issue>`。

脚本不创建、修改、关闭或合并任何 GitHub 资源。

## 触发时机

- 创建 PR 后、请求审核前执行；
- 对堆叠 PR 进行拓扑核验时执行；
- 也可以在 CI 中作为只读策略检查。

该检查不放入每次本地 `pre-push`，因为它需要网络和 GitHub 授权，且推送前可能尚未存在 PR。

## 手动执行

```bash
# 只检查 Issue 是否开放
python3 scripts/check-pr-policy.py \
  --repo owner/repo --issue 7

# 同时检查 Issue、PR 关联关系和 base/head
python3 scripts/check-pr-policy.py \
  --repo owner/repo \
  --issue 7 \
  --pr 42 \
  --expected-base main \
  --expected-head feat/add-validation
```

`--expected-base` 和 `--expected-head` 必须与 `--pr` 一起使用。对于堆叠 PR，应将实际依赖分支作为 `--expected-base` 传入，而不是默认假设 `main`。

## 约束边界

脚本可以验证状态、编号、关键词和分支拓扑，但不能判断 Issue 描述是否“足够清晰”、提交是否混入多个语义模块，也不能检测用户是否绕过浏览器完成 GitHub 操作。这些内容仍需人工 Review 或 CI 规则补充。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 所有请求的 Issue/PR 检查通过 |
| 1 | GitHub 资源存在但违反工作流策略 |
| 2 | 参数错误 |
| 3 | gh 命令、网络或 JSON 响应失败 |
