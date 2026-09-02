# dev-workflow-standards

通用开发工作流规范 Skill，适用于各类 Code Agent 环境。为任何需要严格开发纪律的项目提供标准化的 Git 工作流、提交规范和 GitHub 协作流程。

## 功能概览

本 Skill 涵盖以下核心规范：

- **Git 分支命名规范** — ASCII 字符、小写英文、类别前缀（`feat/`、`fix/`、`docs/`、`refactor/`、`agent/` 等）
- **Push 前分支名检查** — 通过标准 Git `pre-push` hook 和正则表达式拦截特定产品名称
- **提交规范** — 以可独立验证的功能模块为提交边界，提交信息使用中文，测试通过后方可提交
- **提交署名约束** — 禁止在提交信息、PR 描述等位置声明 Code Agent 署名（如 `Generated with`、`Co-Authored-By`）
- **GitHub 操作流程** — 所有 GitHub 操作通过 `gh` CLI 执行，禁止浏览器操作
- **Issue 与 PR 流程** — 功能/修复须先创建 Issue，通过 PR 合并并关联 Issue
- **PR 合并后清理** — 标准化分支清理与 main 同步流程
- **网络与认证排查** — `GH_TOKEN` 安全处理、代理环境下的认证排查顺序
- **项目管理约定** — 以项目看板为唯一事实来源，禁止提前关闭 Issue 或更新状态
- **禁止独占功能** — 禁用特定 Code Agent 的 Hooks 等专有功能，统一使用可移植的 Shell/Python 脚本实现自动化
- **自动化案例** — 提供 PR 合并后清理等可移植 Python 脚本，附完整文档与集成说明

## 安装与使用

### 作为 Code Agent Skill 使用

本 Skill 通常位于 `~/.agents/skills/dev-workflow-standards/`，由 Code Agent 自动加载。项目的 `AGENTS.md` 或 `CLAUDE.md` 可引用本 Skill 并补充项目特有约定。

### 快速检查清单

详细检查清单（包括开始新功能前、提交前、发起 PR 前、PR 合并后的各项检查项）请参阅 [SKILL.md](./SKILL.md) 中的附录部分。

## 项目结构

```
dev-workflow-standards/
├── SKILL.md                    # Skill 定义与完整规范文档
├── README.md                   # 本文件
├── .githooks/
│   └── pre-push                # 调用分支名检查器的标准 Git hook
├── scripts/
│   ├── check-branch-name.py     # Push 前分支名检查脚本
│   └── pr-merge-cleanup.py     # PR 合并后清理脚本
├── references/
│   ├── check-branch-name.md     # Push 前分支名检查使用说明
│   └── pr-merge-cleanup.md     # PR 合并后清理脚本使用说明
├── tests/
│   └── test_check_branch_name.py # 分支名检查测试
└── .gitignore
```

## 自动化脚本

本 Skill 提供独立的、可移植的自动化脚本，遵循「清晰文档 + 通用脚本」模式（详见 SKILL.md 中「自动化案例」章节）。各脚本的完整使用说明存放于 `references/` 目录：

- **`scripts/pr-merge-cleanup.py`** — PR 合并后自动清理：确认合并状态、同步 main、删除本地特性分支。用法：`python3 scripts/pr-merge-cleanup.py <PR编号>`（详见 [`references/pr-merge-cleanup.md`](./references/pr-merge-cleanup.md)）

### Push 前分支名检查

- **`scripts/check-branch-name.py`** — 使用不区分大小写的正则表达式拦截特定产品名称。启用 hook：`git config core.hooksPath .githooks`；详见 [`references/check-branch-name.md`](./references/check-branch-name.md)。

## 规范要点速览

### 分支命名

```
agent/docs-branch-naming   ✅ 合规
fix/batch-result-validation ✅ 合规
feat/async-batch-submit    ✅ 合规
agent/更新-git-规则         ❌ 含非 ASCII 字符
feat/codex-integration      ❌ 含禁止的产品名称
fix/CURSOR-timeout          ❌ 含禁止的产品名称（大小写不敏感）
```

### 提交信息

```
feat: 添加批量请求校验                    ✅ 中文、单一模块
feat: 批量处理、文档优化与代码清理         ❌ 混入多个不相关变更
```

### PR 合并后流程

```bash
gh pr view <PR编号> --json state,mergedAt  # 确认已合并
git checkout main                           # 切换到 main
git pull origin main                        # 拉取更新
git branch -d <分支名称>                     # 删除本地分支
```

## 许可

本项目为内部开发规范，供团队内部使用。
