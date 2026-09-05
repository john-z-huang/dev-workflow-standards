---
name: dev-workflow-standards
description: >-
  通用开发工作流规范：Git 分支命名与提交约定、禁止 Code Agent 署名、
  GitHub Issue/PR 流程、堆叠 PR 的 base/head 分支管理、gh CLI 与 GitHub 集成层操作规范、GH_TOKEN 安全处理、网络与认证排查、
  禁止特定 Code Agent 独占功能、中文文档与提交语言要求。适用于任何需要严格开发纪律的项目。
---

# 通用开发规范

## 始终适用

- 文档和提交使用中文；提交标题为 `<type>: 中文说明`，type 使用 feat/fix/docs/refactor/test/chore/perf/build/ci。
- 不在提交、PR、文档或注释中添加 Code Agent 署名或生成声明。
- 工作分支使用 ASCII 小写字母、数字、连字符和斜杠，前缀为 agent/feat/fix/docs/refactor，不含 Code Agent 产品名；精确规则见 scripts/check-branch-name.py。
- 修改前检查现有差异，保留用户改动。提交只暂存本任务相关文件或 hunk；运行差异检查与相关验证，以可独立审查、回滚的逻辑单元提交。新增行为和缺陷修复补充有意义的测试；纯文档或机械修改不强制增加测试代码。
- Skill 不自动授权提交、推送、外部消息或合并。依据当前用户任务已有授权执行。
- GitHub 推送须关联开放 Issue，变更通过 PR 合并并关联 Issue；本地工作可以先完成。精确核对仓库、base/head 与写入结果。
- 令牌不输出、不记录、不放入命令文本；使用既有授权连接。
- 自动化使用可移植 Shell/Python 和标准 Git Hook，不使用 Code Agent 专有 Hooks。已有项目约束继续遵守。

## 按当前操作加载

| 操作 | 参考 |
|---|---|
| 接入或修复 Git Hook | [Hook 接入](references/hooks.md)，仅在接入任务或项目明确要求时安装；否则运行等效检查 |
| 创建依赖未合并分支的 PR | [堆叠 PR](references/stacked-pr.md) |
| Git 沙箱、uv 检查工具问题 | [环境](references/environment.md)，按实际权限处理，不机械预先提权 |
| GitHub Issue/PR、认证和网络故障 | [GitHub](references/github.md)；优先 gh，已授权集成可替代，禁止浏览器自动化 |
| 已合并 PR 的分支清理 | [合并清理](references/merge-cleanup.md) |
| 新增可移植自动化脚本 | [自动化索引](references/automation-index.md)，补充用途、调用与退出码说明 |

专项历史重写仅在用户明确要求时查阅 [天气项目历史维护](references/rewrite-weather-commit-subjects.md)，不作为日常开发步骤。
