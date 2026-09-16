### Git 元数据写权限（Codex 沙箱）

- 在 Codex 的 `workspace-write` 沙箱中，工作区源码通常可写，但 `.git` 目录可能保持只读；`git add`、`git commit`、`git reset`、`git merge`、`git rebase`、`git tag` 等会改变 Git 状态或历史的命令因此可能需要提升权限。`git status`、`git diff`、`git log` 等只读检查应先在普通沙箱中执行。
- 当用户明确要求暂存、提交或其他 Git 写操作时，先用普通权限完成 `git status`、当前分支和差异范围检查，确定准确的文件边界；确认需要写入 `.git` 后，直接为后续 Git 写命令申请受控的提升权限，不要先无权限尝试 `git add` 或 `git commit`，避免产生可预见的 `index.lock` 权限失败。
- 提升权限获准后，只暂存已确认的文件，执行 `git diff --cached --check` 和必要测试，再执行提交；提交后用 `git show`、`git status` 核对结果。权限申请被拒绝时停止 Git 写操作并说明原因，不用绕过沙箱或改写仓库位置。
