### 合并到 main 的 Squash Merge 规范

- Pull Request 的目标分支为 `main` 时，最终合并必须使用 **Squash Merge**。不得使用普通 merge commit 或 rebase merge 把该 PR 开发过程中的多个 commits 逐个带入 `main`。
- 目标结果是：一个 PR 在 `main` 历史中只产生一个代表该 PR 整体改动的 commit。PR 分支内部允许存在多个开发过程 commits；是否为了审查体验而提前整理 PR 的 Commits 页面属于可选维护，不是本规则的前置要求。
- 合并前仍必须完成现有核验：确认目标仓库和 PR 编号正确、base 为 `main`、PR 处于可合并状态，并确认项目要求的 CI / checks 已通过。Squash Merge 不替代这些检查。
- 使用 GitHub CLI 时，明确执行 `gh pr merge <PR编号> --squash`；若仓库要求显式标题或正文，可同时提供对应参数，但不得改用 `--merge` 或 `--rebase`。
- 使用已授权 GitHub Connector / GitHub App 集成层时，必须调用其等效的 squash merge 能力，并显式设置 merge method 为 `squash`；若集成层无法选择 squash merge，则报告能力阻塞，不得退化为普通 merge。
- 合并完成后核验 PR 已 merged，并检查 `main` 的结果提交：该 PR 的改动应以单一提交进入 `main`，而不是把 PR 分支的多个开发 commits 原样展开到主分支历史。
- 若仓库设置禁止 Squash Merge，视为与本 Skill 规则冲突。除非用户明确授权调整仓库策略或明确覆盖本规则，否则不要使用其他 merge method 代替。
