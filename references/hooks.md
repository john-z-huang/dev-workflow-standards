### 版本化校验脚本与 Hook

本 Skill 中的 Git 校验脚本和 `.githooks` 文件只是可复用资源，不会因为 Skill 被加载
就自动注入或启用到目标项目。要让校验在目标项目的 `git commit` 流程中生效，必须将
相关脚本复制到目标项目的 `scripts/` 目录，将 `commit-msg` 和 `pre-commit` wrapper
复制到目标项目的 `.githooks/` 目录，并在目标项目中执行：

```bash
git config core.hooksPath .githooks
```

推荐将复制后的脚本和 Hook 纳入目标项目版本控制；Hook 中应通过目标项目自己的
`scripts/` 路径调用脚本，不要依赖开发者机器上的 Skill 绝对路径。新克隆项目或新
开发者首次使用时，需要重新执行上述 `git config`（该配置保存在本地 Git 配置中，
不会随提交自动共享）。`git commit --no-verify` 可以绕过本地 Hook；若必须强制执行，
还需要在代码托管平台配置服务端检查。
