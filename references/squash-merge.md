# 合并到 main 的 Squash Merge

Pull Request 的目标分支为 `main` 时，最终合并必须使用 squash merge。这样每个 PR 在 `main` 历史中只产生一个代表整体改动的提交；PR 分支内部仍可保留多个开发提交。

合并前确认目标仓库、PR 编号、base/head、PR 状态、审核决定和项目要求的 checks。已知 PR 编号时，用 `audit_issue_pr_policy(repo_path, repo, pr_number, expected_base="main", expected_head=...)` 检查策略；再调用 `merge_github_pull_request(repo_path, repo, pr_number, merge_method="squash")`。该工具会核验 PR 为 OPEN/MERGEABLE、required checks 通过、没有 changes-requested review，且 `main` 只允许 squash。若仓库禁止 squash、核验失败或工具执行失败，停止并报告，不要换成其他合并方法。

工具成功合并后会回读确认 PR 状态，并返回合并前读取的 `pre_merge_head_oid`。若用户明确授权合并后清理本地分支，保存此 SHA，并按 [`merge-cleanup.md`](merge-cleanup.md) 将它作为 `merged_head_oid` 传给 `cleanup_merged_pr_local_branch`。合并成功但回读验证失败时，先根据响应核实 GitHub 状态；响应中仍会带上合并前 SHA。
