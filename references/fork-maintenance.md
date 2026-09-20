# 个人 Fork 的上游同步与长期维护

本文规定个人 Fork 的固定分支拓扑。只有在 GitHub API 返回非空 `parent`、确认当前仓库是从其他仓库 Fork 出来时才启用本文。独立开发仓库必须跳过本文，继续使用项目自己的默认分支、开发分支和保护规则。

## 拓扑约定

```text
upstream/main  ───────► origin/main
                         │
                         └──► personal-<project>
                               └──► feat/...、fix/...、docs/... 等需求分支
```

- `upstream`：原始项目仓库，只读同步来源。
- `origin`：个人 Fork，包含两个长期维护分支：`main` 和个人维护分支。
- `main`：只镜像上游默认分支，不承载个人需求提交。
- 个人维护分支：推荐命名为 `personal-<project>`；需要层级命名时可使用 `personal/<project>`。当前项目已有其他合法名称时，以已核验的项目约定为准。
- 需求分支：从个人维护分支创建，PR 的 base 默认是个人维护分支。不得把个人需求 PR 直接发往 `main`。

## 首次设置

先完成 Fork 判定；不要仅凭 `origin` 地址、仓库名称或是否存在 remote 推断仓库类型：

```bash
gh repo view --json parent,defaultBranchRef
```

只有 `parent` 非空时继续执行本文。若 `parent` 为空，停止本文并回到普通开发或 GitHub 交付工作流，不添加 `upstream`，不创建 `personal-<project>`，也不修改独立仓库原有分支保护策略。

先确认仓库、remote 和默认分支，不猜测上游地址：

```bash
git remote -v
gh repo view --json nameWithOwner,defaultBranchRef,parent
```

如果 `origin` 是个人 Fork，且没有 `upstream`，添加原始项目地址：

```bash
git remote add upstream <上游仓库 URL>
git fetch upstream main
git branch --set-upstream-to=upstream/main main
```

将本地 `main` 对齐到上游时，优先使用不会丢失提交的 fast-forward 流程：

```bash
git switch main
git merge --ff-only upstream/main
git push origin main
```

从刚同步的 `main` 创建个人维护分支：

```bash
git switch -c personal-<project> main
git push --set-upstream origin personal-<project>
```

如果个人维护分支已经存在，先核对它的用途、远端追踪关系和提交差异，不得覆盖或静默重置。

## 日常开发队列

每个需求开始前：

1. 检查工作区干净、当前 remote 和当前分支。
2. 从 `upstream/main` fast-forward 更新本地 `main`，再 fast-forward 更新 `origin/main`。
3. 将最新 `main` 带入个人维护分支。个人维护分支受保护时，通过从 `main` 到个人维护分支的同步 PR 完成；不要直接绕过保护规则推送。
4. 从最新个人维护分支创建 `agent/<issue>-<topic>`、`feat/<topic>` 或其他合规需求分支。
5. 只在需求分支上提交和验证；PR 明确使用 `--base <personal-branch>`。
6. PR 合并到个人维护分支后，再开始下一项依赖其结果的工作。

推荐的同步命令如下；如果个人维护分支已有自己的提交，不能强行使用 `--ff-only`，应按第 3 步创建同步 PR：

```bash
git fetch upstream main
git switch main
git merge --ff-only upstream/main
git push origin main
```

## GitHub 保护规则

使用 `gh` CLI 或已授权 GitHub 集成层创建并回读 Ruleset。至少为两个长期分支分别配置规则：

### `main`

- 目标分支：`refs/heads/main`
- 启用规则：禁止删除、禁止 non-fast-forward（禁止强制推送）
- 可选启用线性历史
- 不要求个人需求 PR；否则会阻断从上游进行 fast-forward 同步

### 个人维护分支

- 目标分支：个人维护分支的完整 ref
- 启用规则：禁止删除、禁止 non-fast-forward、要求通过 PR
- 审批数和状态检查按项目能力设置；没有可靠 CI 检查时不要凭空添加必需检查
- 若需要通过普通 merge PR 将 `main` 同步进个人分支，不要同时启用会拒绝 merge commit 的线性历史规则；若已启用，应改用项目明确支持的 squash/rebase 同步流程

规则创建后必须回读并确认目标分支、active 状态和实际生效规则：

```bash
gh api repos/<owner>/<repo>/rulesets --paginate
gh api 'repos/<owner>/<repo>/rules/branches/main?includes_parents=true'
gh api 'repos/<owner>/<repo>/rules/branches/<personal-branch>?includes_parents=true'
```

创建 Ruleset 时将完整 JSON 保存在本地文件，再通过 `--input` 提交，避免把规则正文内联到命令参数中。下面是最小保护模板；项目已有规则时先读取并合并，不要覆盖未知规则：

```json
{
  "name": "protect-main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
  "rules": [
    {"type": "deletion"},
    {"type": "non_fast_forward"}
  ]
}
```

```bash
gh api --method POST repos/<owner>/<repo>/rulesets --input main-ruleset.json
```

个人维护分支的规则使用相同结构，把 `name` 和 `ref_name.include` 换成目标分支，并增加以下规则：

```json
{
  "type": "pull_request",
  "parameters": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": false,
    "require_code_owner_review": false,
    "require_last_push_approval": false,
    "required_review_thread_resolution": true
  }
}
```

`main` 不应增加 `pull_request` 规则，否则会阻断上游 fast-forward 同步；个人维护分支是否增加 `required_linear_history`，要与同步 PR 的 merge/squash/rebase 策略一致。

## 防止误推送到 `main`

- 开始需求前运行 `git branch --show-current`，确认不在 `main`。
- 创建 PR 时显式指定 `--base <personal-branch>`，不要依赖仓库默认 base。
- 推送需求分支时显式指定分支名，例如 `git push origin HEAD`；不要执行面向 `main` 的通配推送。
- 发现需求分支错误地以 `main` 为 base 或已经向 `main` 推送个人提交时，停止后续交付，先按恢复流程核对并报告；不得擅自重写受保护分支历史。

## 同步冲突与分支漂移

- `git merge --ff-only upstream/main` 失败时，说明本地 `main` 已产生分叉或上游不是当前预期分支；保留现场并先确认差异。
- `origin/main` 含有个人提交时，不能把它继续当作同步镜像；先确认这些提交是否应撤回、迁移到个人分支或按用户明确授权执行受控历史修复。
- 个人维护分支已有未合并需求时，先确认 PR base/head，再同步上游；不要直接 rebase 已公开分支或使用裸 `--force`。
- 任何需要 force-with-lease、修改 Ruleset、关闭保护或改变默认分支的动作，都必须得到用户明确授权，并在动作前后回读远端状态。
