### Git 元数据写权限（Codex 沙箱）

- 在 Codex 的 `workspace-write` 沙箱中，工作区源码通常可写，但 `.git` 目录可能保持只读；`git add`、`git commit`、`git reset`、`git merge`、`git rebase`、`git tag` 等会改变 Git 状态或历史的命令因此可能需要提升权限。`git status`、`git diff`、`git log` 等只读检查应先在普通沙箱中执行。
- 当用户明确要求暂存、提交或其他 Git 写操作时，先用普通权限完成 `git status`、当前分支和差异范围检查，确定准确的文件边界；确认需要写入 `.git` 后，直接为后续 Git 写命令申请受控的提升权限，不要先无权限尝试 `git add` 或 `git commit`，避免产生可预见的 `index.lock` 权限失败。
- 提升权限获准后，只暂存已确认的文件，执行 `git diff --cached --check` 和必要测试，再执行提交；提交后用 `git show`、`git status` 核对结果。权限申请被拒绝时停止 Git 写操作并说明原因，不用绕过沙箱或改写仓库位置。

### uv 管理的 Python 项目中的静态检查

- 对使用 uv 管理的 Python 项目（例如存在 `pyproject.toml`、`uv.lock` 或项目虚拟环境的项目），不要默认使用 `uv run ruff ...` 或 `uv run ty ...`。
- `uv run` 可能访问项目目录之外的用户级 uv 缓存；在受限沙箱中，即使使用 `--no-sync`，也可能因缓存目录不可读而出现 `Operation not permitted`。这属于环境权限问题，不代表 Ruff 或 Ty 检查本身失败。
- 优先调用项目 Python 虚拟环境中的可执行文件：
  - POSIX：`<project>/.venv/bin/ruff ...`、`<project>/.venv/bin/ty ...`
  - Windows：`<project>/.venv/Scripts/ruff.exe ...`、`<project>/.venv/Scripts/ty.exe ...`
- 运行前确认虚拟环境中的工具存在并使用其版本；如果缺少 Ruff 或 Ty，应使用项目已有的环境安装/恢复流程，或明确报告依赖缺失和权限阻塞，不要静默改用全局工具或 `uv run`。
