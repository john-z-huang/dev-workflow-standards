# 自动化案例

以下案例展示如何按照可移植方案实现自动化功能：文档描述自动化逻辑，独立脚本实现具体功能，任何 Code Agent 或人工流程均可参照执行。

各脚本的完整功能描述（含触发时机、用法、集成方式和退出码）存放于 `references/` 目录，按需查阅。

## 脚本索引

| 脚本 | 描述文档 | 用途 |
|------|----------|------|
| `scripts/pr-merge-cleanup.py` | [`references/pr-merge-cleanup.md`](./pr-merge-cleanup.md) | PR 合并后确认状态、同步 main、删除本地特性分支 |
