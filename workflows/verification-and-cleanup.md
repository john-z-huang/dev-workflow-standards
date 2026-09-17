# 验证与清理工作流

测试通过不等于范围、GitHub 策略或合并后状态通过。按队列只执行适用步骤。

## 队列

| 步骤 |
|---|
| 分类 |
| 环境 |
| 本地验证 |
| Hook 检查（如适用） |
| PR 策略（如适用） |
| 提交门禁（如适用） |
| 合并后清理（如适用） |

## 1. 分类

| 变更 | 最小验证 |
|---|---|
| 文档/机械 | Markdown、链接、引用路径 |
| 行为/修复 | 有意义的测试；按风险增加构建、lint、类型、集成/回归 |
| 脚本/Hook | 成功、失败、参数错误、退出码、副作用 |
| GitHub | Issue/PR 状态、关联、base/head、label、assignee、策略 |

## 2. 环境

- 只读 Git 检查先用普通权限；`.git` 写操作可能需要受控提升。权限细节见 [`environment.md`](../references/environment.md)。
- 用户授权后，先检查状态/分支/范围，再申请准确的 `add/commit/rebase/...` 写权限；拒绝就停止，不换路径绕过。

## 3. 本地与 Hook 检查

按需运行：

```bash
python3 scripts/check-branch-name.py --pre-commit
python3 scripts/check-commit-message.py --message 'docs: 更新工作流'
python3 scripts/check-staged-changes.py
git diff --cached --check
```

分支、提交标题和暂存区规则分别见 [`check-branch-name.md`](../references/check-branch-name.md)、[`check-commit-message.md`](../references/check-commit-message.md) 和 [`check-staged-changes.md`](../references/check-staged-changes.md)。Hook 接入见 [`hooks.md`](../references/hooks.md)；`--no-verify` 可绕过本地 Hook，但不能代替等效检查。

代码变更可按 [`code-understanding.md`](../references/code-understanding.md) 使用 Serena 的诊断、引用和实现关系进行辅助检查，但不能替代测试、构建、lint、类型检查或集成验证。

## 4. PR 策略

创建 PR/请求审核前按 [`check-pr-policy.md`](../references/check-pr-policy.md) 运行 `scripts/check-pr-policy.py`，确认 Issue/PR 开放、base/head 正确和正文关联 Issue。

## 5. 合并后清理

非 worktree 清理按 [`merge-cleanup.md`](../references/merge-cleanup.md) 或 [`pr-merge-cleanup.md`](../references/pr-merge-cleanup.md) 执行；采用 worktree 时按 [`worktree-development.md`](worktree-development.md) 的合并后规则处理。
