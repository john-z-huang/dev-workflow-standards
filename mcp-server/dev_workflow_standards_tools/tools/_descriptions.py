"""Discovery metadata for the local MCP tools; descriptions follow service behavior."""

from __future__ import annotations


SERVER_DESCRIPTION = (
    "本地开发工作流 MCP 服务：提供固定范围的 Git、GitHub 与 worktree 操作，及用于路由、检查和起草的只读辅助工具。"
    "辅助结果不构成执行授权；写操作和外部操作仍须遵循用户授权及具体工具的副作用边界。"
)


SERVER_INSTRUCTIONS = """
本地开发工作流 MCP 工具按以下组选择，不是通用 shell、任意 Git 命令或授权来源。所有 `repo_path` 均须显式给出目标仓库的绝对根路径；不要把子目录、另一个 worktree 或相邻仓库混作目标。先用只读检查和状态审计确认范围，写操作只有在用户明确授权并由 Codex writes approval 放行后才能调用。

**选择与顺序**

**只读查询的覆盖边界**

优先使用已可用且覆盖所需查询的 MCP 工具或已授权 Connector。若它们没有覆盖当前只读查询，可在当前任务和目标仓库范围内使用受限的 `git`/`gh` CLI 读取；无需为每次这类只读查询重复询问业务授权。各工作流指定的审计和检查门禁仍须在规定步骤完成；补充查询可收集后续门禁所需事实，但不能替代门禁或把失败门禁判为通过。缺少覆盖与工具不可用、权限/认证/网络/仓库状态/参数校验失败是不同情况；失败时不得改走 CLI 绕过门禁或失败原因。只读查询仍受适用的宿主 approval、sandbox 和更高优先级约束；这些约束不因只读性质豁免。

只读必须按完整子命令、参数、配置和副作用判断，不得按 `git`/`gh` 前缀推定。`--no-pager` 是 Git 全局选项，须放在子命令前；`git status` 使用 `--no-optional-locks`；`diff`、`log`、`show` 子命令使用 `--no-ext-diff --no-textconv` 并限制输出范围/长度；branch、tag 仅用 `--list`，remote 用 `git remote` 列举。`git fetch` 会写本地 remote refs，不属于只读豁免。`gh issue/pr view` 与受支持的 issue/pr list 查询须显式指定 `--repo owner/repo`；`gh repo view` 使用位置参数 `owner/repo`，不可将 `--repo` 当作该命令的选项。`gh api` REST 不使用 `--repo` 选项；请求必须显式 `--method GET`，在已知查询 endpoint 中指定仓库（例如 `/repos/owner/repo/...`），并核实 endpoint 确为只读；`-f`/`-F` 等参数可能隐式选择 POST，不能将其视为 GET。GraphQL 仅限明确审阅过的 query；mutation 或动态/未知操作不在范围内。环境 helper、pager、alias 或 lazy fetch 可能产生副作用；无法确认完整行为时停止该查询。凭据读取、文件输出、下载、复合命令及其全部副作用需分别评估；本规则不授权这些操作，也不提供任意命令执行器。写入仍需用户对该写入的意图授权及适用的 Codex approval；既有授权仅在其范围内持续有效。

合成命令形状（执行前将仓库路径、文件范围及编号替换为目标值并核验）：
- `git --no-pager --no-optional-locks -C /workspace/repo status --short`
- `git --no-pager --no-optional-locks -C /workspace/repo diff --no-ext-diff --no-textconv -- src/`
- `gh api --method GET repos/example/project/issues/65 --jq '{number,title,state}'`

1. `audit_repository_state` 核对指定仓库的本地状态和 remote 名称；随后按需使用 `list_repository_worktrees`、`check_branch_names`、`capture_untracked_file_manifest`、`check_staged_changes`。审计的 `ok=true` 仅表示本地 Git status/remotes 读取成功；`github` 仍可能为 null 且同时有 `github_error`，不能当作 GitHub 核验成功。
2. 只有用户明确要求使用或创建 worktree 时才使用 worktree 流程：先 `create_repository_worktree`，然后如确需保留源仓库未跟踪文件，再 `capture_untracked_file_manifest` 并 `copy_untracked_files_to_worktree`。复制后检查结果再继续；失败返回也可能已部分复制，`copied` 只列确认完成项，工具不回滚，先检查目标，禁止盲目重跑覆盖。
3. 修改本地分支前核对状态；同步 upstream 时先 `fetch_upstream_branch`，再按需要调用 `merge_upstream_branch_fast_forward`。`pull_origin_branch_fast_forward` 和 `fetch_upstream_branch` 会访问 remote 网络。`rebase_repository_branch` 改写本地历史；remove 会删除 worktree 目录；这些操作都要求对应授权。
4. 提交前先 `check_branch_names`、`check_commit_message`，再精确 `stage_repository_paths`；暂存后、提交前调用 `check_staged_changes` 并核验 staged paths，才考虑 `commit_repository_changes`。commit 会运行正常 Git hooks（可能执行仓库配置的检查）；工具不绕过 hooks。
5. GitHub 流程可先 `list_github_issue_labels` 与 `audit_issue_pr_policy`，再按授权创建 Issue、推送分支、创建 PR、合并。创建工具若返回 `created=true, ok=false`，资源可能已创建但回读未确认；先人工/只读回读，不要盲目重试。合并后可用 `cleanup_merged_pr_local_branch`；它会联网核验 PR 并同步 base，只有合并前记录的 head OID 与本地分支 OID 精确相同才允许 `git branch -D`，否则不强制删除。
6. Codex session fact helpers 只处理调用方提供的元数据和文本：先由宿主读取、核实原会话，再排序或准备摘要 payload。它们不读取宿主 history，不调用 Serena，不写 Memory；`prepare_codex_session_memory` 的 payload 不是授权。
7. 六个可联网 OpenAI 入口分两组：`check_branch_names`、`check_commit_message`、`audit_issue_pr_policy` 在本地硬检查通过后调用 Decisions；`decide_skill_workflow`、`decide_codex_session_action` 调用 Decisions；`generate_skill_content` 调用 Responses.parse。三个检查工具的 `decision` 仅为 `compliant`、`requires_fix`、`insufficient_evidence`；前三个只能把已检查事实交给模型作补充判断；后三个分别给出路由建议、历史动作建议、候选文本。生成支持 issue、pr、commit_message、plan、handoff、session_summary 六种 kind。只有进程环境中的 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL` 会在每次请求时读取，工具参数不能指定凭据、端点或模型，固定模型为 `gpt-6-luna`。缺配置、服务拒绝、refusal、结构无效或输出不完整均是失败/需复核，不是通过；候选和建议都要 Agent 审查，不会授予 Git 或 Memory 权限。

所有响应按各工具说明的采用条件处理：`ok`/`passed`/`created`/`committed`/`merged` 有不同含义，不能只看其中一个字段；部分动作失败后先读回状态，再决定下一步。错误边界、网络访问和副作用以具体工具描述为准。
""".strip()


TOOL_DESCRIPTIONS: dict[str, str] = {
    "check_branch_names": (
        "检查显式分支名，或在未给 branch_names 时读取 repo_path 当前分支；适合工作流开始或创建分支前验证项目命名规则。"
        "不能据此推断分支已存在、已推送或适合合并。repo_path 必须为目标仓库绝对根目录；同时提供 branch_names 与 repo_path 时只检查所列名字。"
        "逐项看 checks[].passed/errors；本地结果字段 local_passed=true 才表示本地硬规则通过。通过后还会联网调用 Decisions，结果可能有 decision/ai_status/error_code，顶层 passed 是本地与 AI 合并结果。"
        "只读 Git；本地失败会跳过 API，不改分支。最小示例：{\"branch_names\":[\"feat/synthetic\"]}。"
    ),
    "check_commit_message": (
        "检查完整提交信息的主题格式、中文说明和禁止署名；适合提交前验证，不用于解释 Git 状态。message 是完整 message，可含正文；空行及左侧去空格后以 # 开头的注释行会在本地检查时忽略。"
        "先看 local_passed/errors；只有 local_passed=true 才表示本地硬检查通过，之后才联网请求 Decisions，且模型仍可返回 requires_fix/insufficient_evidence。顶层 passed 是本地与 AI 合并结果，只有 passed=true 可采用为检查通过。"
        "不读写仓库；本地失败不联网。示例：{\"message\":\"docs: 更新合成说明\"}。"
    ),
    "check_staged_changes": (
        "对 repo_path 的暂存区运行固定 `git diff --cached --check`，检查空白错误；适用于 stage 后、commit 前。只读暂存内容，不运行测试或用户命令。"
        "repo_path 必须是绝对仓库根目录。passed=true 表示该 Git 检查成功；否则检查 diagnostics/error/exit_code，再修复并重跑。无网络、无写入。额外只读查询按共享规则执行，不替代本工具，也不能将本工具失败或不可用当作 CLI 绕过理由。"
    ),
    "stage_repository_paths": (
        "仅将 paths 明列的普通仓库相对文件路径加入 Git index，适用于确认最终 diff 后的精确暂存。先检查 repo_path 与 paths，并确认用户授权；不会自动加入其他文件。"
        "paths 必须非空、唯一、无绝对路径或穿越路径；允许精确 tracked deletion。已有暂存内容会拒绝。仅当 ok=true 且 staged_paths 与请求完全一致时继续提交。"
        "会修改本地 index，需要明确用户授权和 Codex writes approval；不联网。示例：{\"repo_path\":\"/workspace/repo\",\"paths\":[\"src/example.py\"]}。"
    ),
    "commit_repository_changes": (
        "提交已暂存的精确文件集合；仅适用于用户明确授权 commit 且 staged diff 已审查、检查通过之后。expected_paths 必须精确等于当前 staged paths；message 是完整提交信息，并须通过既有本地策略及 cached diff check。"
        "成功需看 ok=true、committed=true 及回读的 commit_oid/message/paths/status。若 committed=true 但 ok=false，提交已发生而后续回读不全，先查仓库，不要重试。"
        "会运行 `git commit` 和正常 hooks（hooks 可能执行项目检查或其他副作用），可能创建提交；不绕过 hooks。固定 Git 操作本身不主动访问网络；仓库配置的 hooks 可能有额外效果。需用户授权与 Codex writes approval。示例：{\"repo_path\":\"/workspace/repo\",\"message\":\"docs: 更新合成说明\",\"expected_paths\":[\"README.md\"]}。"
    ),
    "list_repository_worktrees": (
        "只读列出 repo_path 仓库的 worktree 路径、HEAD、分支以及 detached/locked 状态，适合创建/删除 worktree 前核对拓扑。repo_path 为绝对仓库根目录。"
        "仅在 ok=true 时采用 worktrees 列表；失败看 error。无写入、无网络。"
    ),
    "switch_repository_branch": (
        "在同一 worktree 切换到已存在的本地 branch_name；用于用户明确要求切换且目标状态已核实的场景，不会自动创建或跟踪 remote 分支。"
        "repo_path 为绝对仓库根目录；仅允许当前仓库策略认可的本地名字，且已跟踪暂存/未暂存更改会拒绝（未跟踪文件可以保留）。ok=true 表示切换成功。"
        "会改变本地 worktree 检出分支，不联网；需用户明确授权和 Codex writes approval。"
    ),
    "pull_origin_branch_fast_forward": (
        "将当前已检出的同名分支通过 `git pull --ff-only origin branch_name` 快进同步；适合明确要求从 origin 更新，不能用于非快进合并或其他分支。"
        "要求 repo_path 是绝对根路径、branch_name 有效且等于当前分支，跟踪文件无暂存/未暂存更改；未跟踪文件可保留。ok=true 才表示同步成功；失败不尝试非快进替代。"
        "会访问 origin 网络并更新本地分支/文件，需要用户授权与 Codex writes approval。"
    ),
    "fetch_upstream_branch": (
        "从已配置的 upstream 获取指定 branch_name，更新 remote-tracking 信息；适合随后检查或快进合并前，不会合并、推送或创建 remote。"
        "repo_path 为绝对仓库根目录；upstream 必须已存在，branch_name 格式有效。ok=true 表示 fetch 成功。会联网，不改工作区文件但更新本地 Git remote refs；这是本地写入，不属于只读 CLI 覆盖，需对应用户授权和 Codex writes approval。"
    ),
    "merge_upstream_branch_fast_forward": (
        "把已 fetch 的 `upstream/branch_name` 快进合入当前同名本地分支；只有明确授权同步且确认基点适合时使用。不会自行 fetch 或创建 merge commit。"
        "要求 branch_name 与当前分支一致、工作区完全干净、upstream 已配置且对应 remote ref 已存在；先单独调用 fetch_upstream_branch。ok=true 才表示本地快进完成。"
        "会改变本地分支和工作区；使用本地已取回 ref，不额外联网；需授权和 Codex writes approval。"
    ),
    "rebase_repository_branch": (
        "将当前 branch_name rebase 到已存在的本地 base_branch；仅在明确授权改写历史时使用，不适合共享分支或未确认冲突处理方案的场景。"
        "要求两个本地分支均有效且存在、当前分支匹配 branch_name、两分支不同、工作区完全干净。ok=true 表示 rebase 完成；失败/冲突时保留现场，不自动 continue/abort/reset。"
        "改写本地提交历史，不联网；需明确授权及 Codex writes approval。示例：{\"repo_path\":\"/workspace/repo\",\"branch_name\":\"feat/synthetic\",\"base_branch\":\"main\"}。"
    ),
    "remove_repository_worktree": (
        "移除指定的同仓库本地 worktree 目录；仅适用于用户明确要求删除该 worktree 且确认其中无须保留内容。不会删除本地或远端分支，不使用 force。"
        "repo_path 是绝对仓库根目录；target_worktree_path 必须是绝对路径且属于同仓库，branch_name 必须匹配目标检出的分支，目标工作区须干净且不能是 repo_path 本身。ok=true 才表示目录移除。"
        "删除本地 worktree 目录，需明确用户授权与 Codex writes approval；不联网。"
    ),
    "create_repository_worktree": (
        "从已存在的本地 base_branch 新建本地 branch_name 和 worktree 目录；仅适合用户明确要求使用或创建 worktree 时使用。不会同步 upstream、复制未跟踪文件或开始实现。"
        "repo_path 为绝对仓库根目录；target_worktree_path 必须是不存在、位于源仓库目录之外的绝对路径；目标分支须符合项目策略且不存在，不能已被其他 worktree 检出，base_branch 须存在。ok=true 才表示二者创建成功。"
        "新增本地分支与目录，需要明确授权和 Codex writes approval；不联网。示例：{\"repo_path\":\"/workspace/repo\",\"target_worktree_path\":\"/workspace/repo-feature\",\"branch_name\":\"feat/synthetic\",\"base_branch\":\"main\"}。"
    ),
    "capture_untracked_file_manifest": (
        "为 repo_path 生成未忽略、未跟踪普通文件清单，包含仓库根相对 POSIX path、SHA-256 和字节数；供后续 copy 工具校验使用。不是备份，也不包含 ignored 文件。"
        "ok=false 时检查 unsupported_paths；符号链接、特殊文件或无法哈希项不会纳入 entries。只读本地状态与文件内容，无网络/写入。"
    ),
    "copy_untracked_files_to_worktree": (
        "按先前 capture_untracked_file_manifest 返回值，将符合 SHA-256/size 的普通未跟踪文件复制到同仓库目标 worktree；用于明确希望把未跟踪输入带入新 worktree 的场景。"
        "manifest 每项含仓库相对 POSIX path、64位小写十六进制 sha256、非负字节 size；源文件仍须未跟踪、未忽略且指纹一致。target_worktree_path 须为已存在同仓库 worktree 的绝对路径。目标存在文件、symlink、路径穿越均拒绝，绝不覆盖。"
        "仅 ok=true 且 copied 含所有期望路径才完整采用；ok=false 仍可能部分复制，copied仅列已复制项，无自动 rollback。失败先检查 target，再由用户决定是否补做，禁止盲目重跑。会写目标文件但不暂存、不联网；需授权与 Codex writes approval。结构示例：{\"repo_path\":\"/workspace/repo\",\"target_worktree_path\":\"/workspace/repo-feature\",\"manifest\":[{\"path\":\"notes/input.md\",\"sha256\":\"0000000000000000000000000000000000000000000000000000000000000000\",\"size\":123}]}；示例摘要和大小仅为占位，实际值必须原样取自 capture_untracked_file_manifest。"
    ),
    "configure_project_hooks_path": (
        "将目标仓库本地 `core.hooksPath` 固定设为 `.githooks`；仅当本仓库 `.githooks/pre-commit` 和 `commit-msg` wrappers 已存在且用户明确要求启用时使用。不会复制、安装或联网获取 hook。"
        "repo_path 为绝对仓库根目录；若当前配置指向其他位置会拒绝覆盖。ok=true 表示仓库本地配置已设定。修改 `.git/config`，需明确授权与 Codex writes approval。"
    ),
    "audit_issue_pr_policy": (
        "联网只读检查用户指定的 GitHub Issue/PR 状态及可选 PR base/head、Issue 关闭引用；适合创建 PR 前按请求范围核验。至少给 issue_number 或 pr_number；expected_base/head 仅可与 pr_number 一起使用。Issue-only 与 PR-only 均有效。"
        "只读审计本身会联网查询 GitHub；local_passed=true 表示审计符合本地策略并允许继续调用 OpenAI Decisions，local_passed=false 只阻止 OpenAI 请求，不表示此前没有查询 GitHub。顶层 passed 表示本地审计与 AI 决策均通过；同时检查 decision/ai_status/error_code。只查开放状态、显式期望的 base/head，并仅在同时给 issue_number 与 pr_number 时查 Closes/Fixes/Resolves 引用；不查 CI、labels、mergeability。只读，不修改 GitHub。若需额外只读查询且本工具未覆盖，可按共享规则使用受限 gh CLI；REST `gh api` 须显式 `--method GET`，在已知 endpoint 路径中指明 owner/repo（不是 `--repo` 选项）；GraphQL 限已审阅 query。参数、副作用不明或写入操作不适用。"
    ),
    "cleanup_merged_pr_local_branch": (
        "PR 已合并后，将本地仓库切到 PR base、快进同步 origin/base，再删除本地 PR head；只用于用户明确授权的合并后清理，不会合并 PR 或删除远端分支。"
        "联网读取 PR 并要求 MERGED、工作区干净；repo_path 为绝对仓库根路径。branch_name 可省略（使用 PR head），若给出必须匹配；merged_head_oid 应为合并前记录的 OID。先尝试安全 `-d`；仅普通删除失败且所给 OID 与当前本地分支 OID 完全相同才用 `-D`。"
        "completed=true 表示清理完成；失败时查看 actions，因为可能已切换/拉取 base。操作会联网 pull 并改变本地分支/删除本地分支，需明确授权和 Codex writes approval。示例：{\"repo_path\":\"/workspace/repo\",\"pr_number\":12,\"repo\":\"owner/repo\",\"branch_name\":\"feat/synthetic\",\"merged_head_oid\":\"0000000000000000000000000000000000000000\"}；SHA 仅为格式示例，实际值可取自已授权 merge 工具返回的 pre_merge_head_oid。"
    ),
    "audit_repository_state": (
        "审计指定仓库的本地根路径、当前分支、status 行和 remote 名称，并尝试读取 GitHub 仓库身份/Fork/default branch；适合工作流开始时确认目标。repo_path 必须是绝对仓库根目录。"
        "ok=true 只表示本地 `git status` 与 `git remote` 成功；GitHub 数据单独看 github/github_error，可能出现 ok=true 且 github=null、github_error 非空，不能据此声称 GitHub 已核验。remote URL 不返回。只读；会尝试联网 `gh repo view`，无写入。若其他只读查询未被 MCP/已授权 Connector 覆盖，可在当前仓库范围执行受限只读 CLI；先核实范围并遵循共享只读边界。此工具失败、认证/网络问题或状态异常不构成绕过门禁的理由。"
    ),
    "list_github_issue_labels": (
        "联网只读列出指定 GitHub 仓库最多 100 个 Issue label，适合创建 Issue 前核对可用 label。repo_path 是用于认证/上下文的绝对仓库根目录；repo 可显式指定 owner/repo，否则按本地仓库解析。"
        "仅当 ok=true 且 labels 内容已核对时采用；结果最多100项，不代表其余标签不存在。不会创建或修改 labels/GitHub 资源。"
    ),
    "create_github_issue": (
        "在明确用户授权后联网创建 GitHub Issue；适用于内容、目标仓库和至少一个现存工作类型 label 均已确认时。body 是完整 Markdown 正文，工具用临时 body-file 传递并默认指派当前 gh 用户。"
        "repo_path 为绝对仓库根目录，repo 为 owner/repo；title/body 非空，labels 至少一项且须存在于最多读取的前100个 label 中。ok=true 表示创建后回读开放状态、labels、当前用户 assignee 均通过。created=true 且 ok=false 表示可能已创建但回读未确认，先回读，不可盲目重试。"
        "会联网创建 Issue，属于外部写入；需明确用户授权和 Codex writes approval。示例：{\"repo_path\":\"/workspace/repo\",\"repo\":\"owner/repo\",\"title\":\"docs: 合成示例\",\"body\":\"合成说明\",\"labels\":[\"<先从 list_github_issue_labels 核对的精确名称>\"]}；label 占位值须替换为查询结果中的真实名称。"
    ),
    "push_issue_branch_to_origin": (
        "验证指定 Issue 开放、有 label 且指派给当前 gh 用户后，将当前本地非主分支推到 origin；仅适用于用户明确授权推送并确认关联 Issue。不会 force push。"
        "repo_path 绝对仓库根目录；repo 为 owner/repo，issue_number 为正整数，branch_name 必须是当前检出的非 main/master 分支；工作区须完全干净。ok=true 表示 push 命令成功，不代表 PR 已创建。"
        "会联网读取 GitHub Issue 并推送远端分支，需明确授权与 Codex writes approval。"
    ),
    "create_github_pull_request": (
        "为显式 head/base 创建并回读关联开放 PR；适合本地验证完成且分支已推送之后。body 是完整 Markdown，必须含指定 Issue 的 Closes/Fixes/Resolves #N 关联；默认指派当前 gh 用户。"
        "repo_path 绝对仓库根目录；repo 为 owner/repo；base/head 不同且有效，Issue 必须开放，本地 head 分支须存在。ok=true 表示回读的 OPEN/base/head/Issue关联/@me assignee 均核验成功。created=true 且 ok=false 表示已可能创建但回读未确认，先回读，不得盲重试。"
        "会联网创建 PR，属于外部写入；需明确用户授权与 Codex writes approval。示例：{\"repo_path\":\"/workspace/repo\",\"repo\":\"owner/repo\",\"base_branch\":\"main\",\"head_branch\":\"feat/synthetic\",\"issue_number\":12,\"title\":\"feat: 增加合成能力\",\"body\":\"Closes #12\\n\\n变更说明。\"}。"
    ),
    "merge_github_pull_request": (
        "在明确授权后合并 GitHub PR；仅用于已审查且允许合并的目标，不会使用 admin/auto 或删远端分支。先联网核验 PR OPEN/MERGEABLE、reviewDecision、required checks。base 为 main 时只允许 squash。"
        "repo_path 为绝对仓库根目录，repo 为 owner/repo，pr_number 正数；merge_method 只能 squash/merge/rebase。ok=true 且 merged=true 表示命令后回读 MERGED 和 base 成功；失败检查 error/checks。成功响应提供合并前 pre_merge_head_oid，供本地清理时精确比对。"
        "会联网并改变远端 GitHub 状态、关闭 PR；需明确用户授权和 Codex writes approval。"
    ),
    "push_fork_main_fast_forward": (
        "把已确认 GitHub Fork 的本地 main 快进推送到 origin/main；仅用于用户明确要求同步 Fork 镜像，不用于普通功能分支发布。"
        "repo_path 为绝对仓库根目录，repo 为 owner/repo；必须是 Fork、GitHub 默认分支为 main、当前检出 main、工作区完全干净，upstream/main 已是本地 main 祖先，且 origin/upstream remotes 预先存在。ok=true 表示 push 成功，不 force。"
        "会联网读取 Fork 信息并更新远端 main，风险高，需明确授权与 Codex writes approval。"
    ),
    "get_codex_session_summary_guidance": (
        "返回包内 Codex 会话摘要默认问题/模板，或校验并返回用户自定义问题/模板；可在读取原会话前用于准备阅读清单或摘要结构。它不读会话、验证来源内容或写 Memory。"
        "custom_questions 若提供须至少含一个非空问题（无数量上限）；custom_template 若提供须非空。ok=true 时采用 questions/template 与 constraints；next_steps 是调用方流程提示，不代表工具已执行。无网络及副作用。"
    ),
    "order_codex_session_sources": (
        "按调用方提供且格式通过的 created_at 对 CodexSessionSource 去重、分组并从新到旧排序；适合存在多个候选历史会话时确定优先阅读组。不会读取或核验真实会话。"
        "sources 是调用方从多个可读原会话收集的元数据列表，使用 source_link/thread_id/title/created_at/ended_at；同一 thread 元数据冲突会报错。ready=true 表示无时间歧义；priority_groups 是按 created_at 降序排列的来源组，missing_created_at 列出缺时间的来源；相同 created_at 或缺 created_at 会在 ambiguities 中明确保留，不用 UUID、updatedAt 或入参顺序猜先后。metadata_verified 始终 false。纯本地，无网络/写入。示例仅使用合成 UUID：{\"sources\":[{\"source_link\":\"codex://threads/00000000-0000-4000-8000-000000000011\",\"created_at\":\"2026-01-01T00:00:00Z\",\"title\":\"合成会话\"}]}。"
    ),
    "prepare_codex_session_memory": (
        "依据已核对的原会话摘要和引用，生成供调用方审阅的 Serena write_memory payload；不是 Memory 写入工具。只有用户允许持久化、原会话已回读并完成溯源后，调用方才可另行授权调用 Serena。"
        "repo_path 为目标项目绝对根目录，单独返回并写入 metadata.memory_project_root；source 需含 thread 来源及 created_at/title（source_link 足以推导 thread_id；ended_at 未知时省略/null）；summary 非空，evidence_refs 至少一个原消息/轮次引用。persistence_allowed=false 时返回 status=skipped 且 payload=null；true 时 ok=true/status=prepared 也不代表授权或来源已核验。payload 仅含 memory_name 和 content。先读回既有同 thread Memory，绝不自动写入。无网络、不调用 Serena、不写文件或 Memory。示例：{\"repo_path\":\"/workspace/project\",\"source\":{\"source_link\":\"codex://threads/00000000-0000-4000-8000-000000000011\",\"created_at\":\"2026-01-01T00:00:00Z\",\"title\":\"合成会话\"},\"summary\":\"经原会话核对的合成摘要\",\"evidence_refs\":[\"turn:2\"]}；UUID、时间、标题和引用均为合成值，实际调用须使用已核验来源。"
    ),
    "decide_skill_workflow": (
        "按固定优先级 blocked > explicit_worktree > github_delivery > special_operations > verification_only > standard-development 给出路由建议；可选workflow为 standard-development、worktree-development、github-delivery、special-operations、verification-and-cleanup、recovery-and-exceptions、clarify。只有 worktree-development 且 github_delivery=true 时 follow_up_workflow 才为 github-delivery，否则为 null。request.user_request 描述请求，五个布尔值由调用方预先分类且是真正路由依据；无 repo_path 本身不是澄清理由。"
        "查看 ok/workflow/follow_up_workflow；ok=true 仍是待 Agent 审查的建议，不执行步骤或授予授权。缺 API 配置、拒绝或无效响应看 error_code 并失败关闭。会联网调用 Decisions；不会 Git/Memory 写入。示例：{\"request\":{\"user_request\":\"实现功能\",\"blocked\":false,\"explicit_worktree\":false,\"github_delivery\":false,\"special_operations\":false,\"verification_only\":false}}。"
    ),
    "decide_codex_session_action": (
        "依据调用方已知的来源可用性/读取程度/相关性和持久化许可，分别建议 lookup_action 与 persistence_action；适合宿主决定先读历史、查项目、澄清、阻塞或等待证据。它不读取 history，也不写 Memory。"
        "request 的 relevant_facts_found=null 表示未知，false 表示已核实无相关事实；new_fact_origin 区分原会话、当前会话、无来源。lookup_action 枚举为 read_history/query_project/clarify/blocked：来源无关或已读且无事实时 query_project；来源不可读时 blocked；未读完或已找到相关事实时 read_history（可依据已读证据继续，无需重复读取）；已读但相关性未知时 clarify。persistence_action 为 create_summary/update_summary/skip_persistence/await_source_evidence：原会话证据完整且相关、允许持久化时按既有摘要选择创建或更新；当前会话/无来源、未许可或无相关事实时跳过；许可下来源不可读/未读完/相关性未知时等待证据。ok=true 且两项动作符合 facts 才可作为建议，仍需 Agent 审查。通过 Decisions 联网；无会话/Git/Memory副作用。示例：{\"request\":{\"user_request\":\"查背景\",\"has_relevant_sources\":false,\"history_accessible\":false,\"history_fully_read\":false,\"relevant_facts_found\":null,\"persistence_allowed\":false,\"existing_summary\":false,\"new_fact_origin\":\"none\"}}。"
    ),
    "generate_skill_content": (
        "为 issue、pr、commit_message、plan、handoff 或 session_summary 生成结构化候选文本，适合已有明确证据、需要起草而非执行时。request.evidence 必须非空；每项 origin 标明来源，ref 唯一。session_summary 必须提供 source.created_at 与 source.title；source.thread_id 可从 source_link 推导；只接受对应 thread 的 provided_session 证据。"
        "user_request 定目标，focus_questions/output_format 可自定义重点/结构；它们不增加事实。仅当 ok=true 才有 candidate；candidate.title 是标题，candidate.content 是正文（commit_message 的正文可为空）。candidate.used_evidence_refs 仅列实际支持文本的输入引用；candidate.missing_facts 列完成请求所需但证据缺失的事实；candidate.review_notes 列需 Agent 核对的要点。拒绝/截断/坏引用/本地 commit 格式失败均看 error_code。Responses.parse 联网；不会写文件、Memory、Git/GitHub 或执行候选动作。示例：{\"request\":{\"kind\":\"plan\",\"user_request\":\"基于证据列计划\",\"evidence\":[{\"reference_id\":\"turn:2\",\"content\":\"用户提出合成目标\",\"origin\":\"user_provided\"}]}}。"
    ),
}


PARAMETER_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "check_branch_names": {
        "branch_names": "可选的分支名列表；每项按项目硬规则独立检查。null/省略时改为读取 repo_path 当前分支；空列表无效。",
        "repo_path": "目标仓库绝对根路径。仅 branch_names 为 null 时必须提供；提供名称列表时不会从该仓库读取分支。",
    },
    "check_commit_message": {"message": "完整提交标题与可选正文；本地检查会跳过空行和左trim后以 # 开头的注释行。"},
    "check_staged_changes": {"repo_path": "目标 Git 仓库的绝对根路径。"},
    "stage_repository_paths": {
        "repo_path": "目标 Git 仓库的绝对根路径。",
        "paths": "需要精确暂存的仓库根相对 POSIX 文件路径列表；不得为空、重复、绝对路径、目录或含路径穿越。tracked deletion 可列入。",
    },
    "commit_repository_changes": {
        "repo_path": "目标 Git 仓库的绝对根路径。",
        "message": "完整提交信息，主题须通过既有本地规则；commit 会正常触发仓库 hooks。",
        "expected_paths": "用户审查并授权提交的精确仓库根相对路径集合；必须与当前 staged paths 完全相等。",
    },
    "list_repository_worktrees": {"repo_path": "拥有待列举 worktrees 的 Git 仓库绝对根路径。"},
    "switch_repository_branch": {
        "repo_path": "要切换分支的 worktree 仓库绝对根路径。",
        "branch_name": "已存在且已核实的本地目标分支名；工具不会自动创建或跟踪远端分支。",
    },
    "pull_origin_branch_fast_forward": {
        "repo_path": "当前待同步 worktree 的绝对仓库根路径。",
        "branch_name": "必须与当前检出的分支同名；固定从 origin 拉取且只允许快进。",
    },
    "fetch_upstream_branch": {
        "repo_path": "已配置 upstream remote 的仓库绝对根路径。",
        "branch_name": "要从 upstream 获取的远端分支名；只更新 remote-tracking 信息，不合并。",
    },
    "merge_upstream_branch_fast_forward": {
        "repo_path": "待快进同步的本地 worktree 绝对仓库根路径。",
        "branch_name": "必须与当前检出分支同名，且 upstream/<branch_name> 已由单独 fetch 获取。",
    },
    "rebase_repository_branch": {
        "repo_path": "待 rebase 的 worktree 仓库绝对根路径。",
        "branch_name": "必须是当前检出的本地源分支；工具会拒绝目标相同的 base。",
        "base_branch": "已存在的本地目标基分支；不接受未验证的 remote ref。",
    },
    "remove_repository_worktree": {
        "repo_path": "拥有目标 worktree 的源仓库绝对根路径。",
        "target_worktree_path": "待移除 worktree 的绝对路径；必须是同一 Git common-dir 下、非源仓库本身且干净。",
        "branch_name": "目标 worktree 当前必须检出的分支名，用于防止删除错目录。",
    },
    "create_repository_worktree": {
        "repo_path": "源 Git 仓库绝对根路径。",
        "target_worktree_path": "新 worktree 目标绝对路径；必须不存在且位于源仓库目录之外。",
        "branch_name": "要新建的本地工作分支名；须符合项目分支规则且当前不存在。",
        "base_branch": "已存在的本地基分支；不会自动 fetch 或取用 remote ref。",
    },
    "capture_untracked_file_manifest": {"repo_path": "读取未忽略未跟踪文件的 Git 仓库绝对根路径。"},
    "copy_untracked_files_to_worktree": {
        "repo_path": "包含 manifest 源文件的 Git 仓库绝对根路径。",
        "target_worktree_path": "已存在且与源仓库同属一个 Git common-dir 的 worktree 绝对路径。",
        "manifest": "先前清单中的条目；每项 path 为仓库根相对 POSIX 路径，sha256 为64位小写十六进制，size 为非负字节数。复制前会重新校验源状态与指纹。",
    },
    "configure_project_hooks_path": {"repo_path": "要修改其本地 core.hooksPath 配置的仓库绝对根路径。"},
    "audit_issue_pr_policy": {
        "repo_path": "用于解析仓库和 GitHub CLI 上下文的绝对仓库根路径。",
        "repo": "可选 owner/repo；省略时从 repo_path 仓库解析。",
        "issue_number": "可选正数 Issue 编号；提供时只检查该 Issue 的开放状态。Issue-only 请求有效。",
        "pr_number": "可选正数 PR 编号；提供时检查开放状态及可选 base/head。与 issue_number 同时提供时还检查 PR 正文关闭引用。",
        "expected_base": "可选期望 base 名；仅与 pr_number 一起使用并进行精确比较。",
        "expected_head": "可选期望 head 名；仅与 pr_number 一起使用并进行精确比较。",
    },
    "cleanup_merged_pr_local_branch": {
        "repo_path": "需要做合并后本地清理的仓库绝对根路径；工作区必须干净。",
        "pr_number": "已合并的正数 PR 编号；工具会联网回读 MERGED 状态与实际 base/head。",
        "repo": "可选 owner/repo，省略时按 repo_path 解析。",
        "branch_name": "可选本地 head 分支名；如提供必须与 PR head 一致。",
        "merged_head_oid": "可选合并前记录的40/64位 hex head OID；仅当 -d 失败且本地OID精确匹配时允许 -D。",
    },
    "audit_repository_state": {"repo_path": "目标 Git/GitHub 仓库绝对根路径；GitHub 查询基于该目录的 gh 上下文。"},
    "list_github_issue_labels": {
        "repo_path": "目标仓库绝对根路径，用于校验仓库并提供 gh 上下文。",
        "repo": "可选 owner/repo；省略时从 repo_path 推断目标 GitHub 仓库。",
    },
    "create_github_issue": {
        "repo_path": "作为 gh 上下文的目标仓库绝对根路径。",
        "repo": "Issue 目标仓库，精确 owner/repo。",
        "title": "完整 Issue 标题，不含工具自动补充内容。",
        "body": "完整 Markdown 正文；安全地经临时 body-file 交给 gh。",
        "labels": "至少一个精确存在的 label 名称；会从仓库前100项中核对。",
    },
    "push_issue_branch_to_origin": {
        "repo_path": "当前分支所在的本地仓库绝对根路径。",
        "repo": "Issue 所在 GitHub 仓库，精确 owner/repo。",
        "branch_name": "要推送的分支；必须是当前检出的非 main/master 分支且工作区干净。",
        "issue_number": "须为正数且对应开放、有 label、指派给当前 gh 用户的 Issue。",
    },
    "create_github_pull_request": {
        "repo_path": "包含本地 head branch 的仓库绝对根路径。",
        "repo": "PR 目标 GitHub 仓库，精确 owner/repo。",
        "title": "完整 PR 标题。",
        "body": "完整 Markdown 正文，必须以 Closes/Fixes/Resolves #<issue_number> 形式关联指定开放 Issue。",
        "base_branch": "PR 目标分支。",
        "head_branch": "PR 来源分支；本地必须存在且与 base 不同，通常需已推送。",
        "issue_number": "关联的正数且开放的 GitHub Issue 编号。",
    },
    "merge_github_pull_request": {
        "repo_path": "用于 gh 调用的仓库绝对根路径。",
        "repo": "PR 所属 GitHub 仓库，精确 owner/repo。",
        "pr_number": "待合并正数 PR 编号；必须 OPEN、MERGEABLE 且 required checks 均通过。",
        "merge_method": "合并方式：squash、merge 或 rebase；base 为 main 时只能 squash。",
    },
    "push_fork_main_fast_forward": {
        "repo_path": "已确认 Fork 的本地仓库绝对根路径；必须检出干净 main。",
        "repo": "目标 GitHub Fork，精确 owner/repo；其 parent/default branch 会联网核验。",
    },
    "get_codex_session_summary_guidance": {
        "custom_questions": "可选摘要问题列表；提供时至少含一个非空字符串，无数量上限，替换包内默认问题。",
        "custom_template": "可选非空摘要模板；提供时替换包内默认模板。",
    },
    "order_codex_session_sources": {
        "sources": "调用方从同一可读会话来源收集的元数据列表；时间相同/缺失会标注歧义，不以其他字段猜排序。",
    },
    "prepare_codex_session_memory": {
        "repo_path": "目标 Serena 项目的绝对仓库根路径；先本地校验，单独返回，并写入 metadata.memory_project_root，不属于 payload。",
        "source": "调用方提供的原会话元数据；source_link须用 codex://threads/<小写标准UUID>，时间须带时区；本模型验证格式，不核验宿主真相。",
        "summary": "待审的完整摘要文本；工具在允许准备时原样放入 payload.content。",
        "evidence_refs": "至少一个能回查原会话消息/轮次的引用；仅记录供调用方核对，不验证引用内容。",
        "topic": "Memory相对主题路径；允许多段字母/数字/下划线/连字符并用 / 分隔，各段至多100 UTF-8字节；禁止首段global、空段、.、..、反斜杠、冒号及其他字符。默认 codex-sessions。",
        "persistence_allowed": "调用方传入的当前用户持久化许可；false 时 payload=null 并返回 skipped。工具不自行核实授权。",
        "existing_memory_name": "可选既有 Memory 名称；必须位于 topic/ 下、为单个安全条目、逻辑条目不超过252 UTF-8字节，且以该 source.thread_id 结尾（不带.md）；同会话更新时使用，调用方须先读回核对。",
    },
    "decide_skill_workflow": {
        "request": "严格结构化工作流请求；user_request为1–12000字符非空文本，其余五个字段为必填布尔flags且决定优先级。",
    },
    "decide_codex_session_action": {
        "request": "严格结构化历史查找/持久化状态。必填 flags 为布尔值；relevant_facts_found 的 null 表示未知，false 表示已知未发现；origin 区分 original_session/current_session/none。",
    },
    "generate_skill_content": {
        "request": "严格结构化候选请求；kind限定六种类型，evidence需1–100项且引用唯一，文本有长度上限。session_summary必须含 source 且所有证据同属该thread。custom focus/format不会改变事实边界。",
    },
}


assert len(TOOL_DESCRIPTIONS) == 31
assert set(TOOL_DESCRIPTIONS) == set(PARAMETER_DESCRIPTIONS)


_OPENAI_BOUNDARIES = {
    "check_branch_names": "接口边界：本地 Git 规则通过后才调用 OpenAI Decisions；本地失败不访问 OpenAI。本工具不读取宿主会话或写入 Memory。",
    "check_commit_message": "接口边界：本地提交信息规则通过后才调用 OpenAI Decisions；本地失败不访问 OpenAI。本工具不读取宿主会话或写入 Memory。",
    "audit_issue_pr_policy": "接口边界：只读 GitHub 审计会访问外部网络；仅审计通过后调用 OpenAI Decisions，审计失败只阻止 OpenAI 请求。本工具不读取宿主会话或写入 Memory。",
    "decide_skill_workflow": "接口边界：调用 OpenAI Decisions 提供路由建议；不读取宿主会话、不调用 Git/GitHub，也不读写 Memory。",
    "decide_codex_session_action": "接口边界：调用 OpenAI Decisions 提供历史动作建议，但不读取宿主会话、不调用 Git/GitHub，也不读写 Memory。",
    "generate_skill_content": "接口边界：调用 OpenAI Responses.parse 生成候选文本；不读取宿主会话、不调用 Git/GitHub，也不读写 Memory。",
}

_SESSION_FACT_BOUNDARIES = {
    "get_codex_session_summary_guidance": "接口边界：不调用 OpenAI、不读取宿主会话或 Serena Memory；只返回包内指导资源和调用方问题/模板，不写入 Memory。",
    "order_codex_session_sources": "接口边界：不调用 OpenAI、不读取宿主会话或 Serena Memory；只处理调用方给出的多个来源元数据，不写入 Memory。",
    "prepare_codex_session_memory": "接口边界：不调用 OpenAI、不读取宿主会话或 Serena Memory；只校验调用方来源和目标 repo_path、准备待审 payload，不写文件或 Memory。",
}

for _tool_name in TOOL_DESCRIPTIONS:
    if _tool_name in _OPENAI_BOUNDARIES:
        TOOL_DESCRIPTIONS[_tool_name] += _OPENAI_BOUNDARIES[_tool_name]
    elif _tool_name in _SESSION_FACT_BOUNDARIES:
        TOOL_DESCRIPTIONS[_tool_name] += _SESSION_FACT_BOUNDARIES[_tool_name]
    else:
        TOOL_DESCRIPTIONS[_tool_name] += "接口边界：本工具不调用 OpenAI、不读取宿主会话或 Serena Memory，也不写入 Serena Memory。"
