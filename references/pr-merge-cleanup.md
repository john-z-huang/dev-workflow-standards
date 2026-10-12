# PR 合并后清理脚本

## 功能描述

在获得用户明确授权后，确认 PR 的 base/head，使用 fast-forward-only 模式同步 base 分支，并清理本地 head 分支。脚本先使用 `git branch -d` 保留普通 ancestry 检查；Squash merge 因 ancestry 不匹配而拒绝普通删除时，只有调用者提供合并前记录的 PR head SHA，且它与本地 head SHA 完全一致时，脚本才使用 `git branch -D`。

PR 合并后查询到的 `headRefOid` 是 PR 关联 head ref 的 OID，不保证是合并时的历史快照。不要把合并后读取的 `headRefOid` 当作 `--merged-head-oid` 的值。

## 触发时机

- PR 在 GitHub 上完成审核并合并后
- 用户明确授权执行 base 同步和本地 head 清理后，由 Code Agent 或开发者手动调用

PR 已合并本身不构成执行同步或删除本地分支的授权。

## 脚本

`scripts/pr-merge-cleanup.py` — Python 3 脚本，仅依赖标准库、`git` 和 `gh` CLI。脚本不会自动删除远端 head 分支。

## 手动执行

对于 `git branch -d` 能识别为已合并的分支，可直接调用：

```bash
python3 scripts/pr-merge-cleanup.py 42
```

对于 Squash merge，应在合并前记录 `headRefOid`：

```bash
gh pr view 42 --json headRefOid --jq .headRefOid
```

得到的 SHA 必须保留到合并后的清理步骤。获得用户明确授权后，将该 SHA 传给脚本：

```bash
python3 scripts/pr-merge-cleanup.py 42 --merged-head-oid <合并前记录的SHA>
```

也可手动指定本地分支及仓库：

```bash
python3 scripts/pr-merge-cleanup.py 42 feat/add-validation --merged-head-oid <合并前记录的SHA> --repo owner/repo
```

## 边界

脚本只清理本地已合并 head 分支，不合并 PR、不删除远端分支，也不处理未合并分支。PR 合并本身不授权 Git 写操作；只有用户明确授权后才调用脚本。

脚本先执行 `git branch -d`。Squash merge（以及其他会重写 commit ancestry 的合并方式）可能导致普通删除失败。此时若没有 `--merged-head-oid`，脚本停止，不会强制删除。若提供了该参数，脚本仍只在 PR 明确为 `MERGED`、base 已通过 `pull --ff-only` 成功同步、工作区干净、当前不在 head 分支，且 `git rev-parse` 得到的本地 head SHA 与合并前记录的 SHA 完全一致时才执行 `git branch -D`。SHA 缺失或不匹配时停止；这可拦截合并后新增的本地提交。不要使用合并后查询到的 `headRefOid` 充当历史记录。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 清理成功 |
| 1 | 参数错误或前置条件不满足（如工作区不干净） |
| 2 | PR 尚未合并 |
| 3 | Git、gh 命令或删除本地分支失败 |
