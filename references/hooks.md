# 版本化校验脚本与 Git Hook

Skill 不会自动把 `.githooks` 文件或脚本复制到目标项目。获得用户授权后，调用 MCP 工具 `configure_project_hooks_path` 并传入 `repo_path`；它只在目标仓库已有 `.githooks/pre-commit` 和 `.githooks/commit-msg`，且现有配置未指向其他路径时，设置该仓库本地的 `core.hooksPath`，不会复制或安装 Hook 资产。

如目标项目尚无这些文件，当前 MCP 服务不提供资产复制工具。不要通过 Skill 内的通用终端流程代做；说明缺少能力，由用户决定如何提供项目 Hook 文件。配置工具会拒绝覆盖指向其他路径的现有设置。

Hook 脚本应通过目标项目内的相对路径调用版本化校验脚本，不依赖开发者机器上的 Skill 绝对路径。提交到 Git 的 Hook 可以随仓库共享；`core.hooksPath` 配置保存在本地 Git 配置中，新克隆或新开发者需要再次配置。`git commit --no-verify` 可以绕过本地 Hook；如需强制执行，还需仓库托管平台上的服务端检查。

交互式流程可直接调用 `check_branch_names`、`check_commit_message` 和 `check_staged_changes`。Hook 中可保留脚本作为轻量本地校验入口。
