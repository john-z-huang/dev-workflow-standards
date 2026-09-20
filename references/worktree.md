# Git worktree 开发与交付

## 适用条件与边界

仅当用户在当前指令中明确要求使用或创建 worktree 时，才启用本文。默认不创建 worktree；当前目录属于 Git 仓库、仓库配置了 remote、任务需要 GitHub 交付、需要分支或存在并行工作项，都不会单独触发本文。未明确要求时，直接在当前工作区按其他适用工作流执行。

启用本文后，确认仓库实际使用的 remote 和默认主分支；普通仓库示例使用 `origin` 和 `main`，个人 Fork 还必须按 [`fork-maintenance.md`](fork-maintenance.md) 使用 `upstream` 同步 `main`，再从个人维护分支创建需求 worktree。项目使用其他名称时以实际配置为准。若没有 Git 仓库或没有配置 remote，仍不能凭本文强制创建 worktree；按用户明确要求和项目已有流程处理，并在缺少同步前提时停止或报告。

在已选定 worktree 模式后，每个完整需求在一个独立 worktree 中实现、验证和提交，并使用该需求自己的工作分支。只有需求确实要并行拆分成多个可独立审查的工作项时，才为各工作项分别创建 worktree 和分支。无论并行 worktree 来自同一需求的拆分，还是来自多个独立需求，只要它们最终都要集成到同一基线分支，就必须按本文队列逐个推送、合并、同步基线、rebase 下一个工作项并重新验证；普通仓库基线通常是 `main`，个人 Fork 基线通常是个人维护分支。

在已选定 worktree 模式后，原始工作区（最初打开的仓库目录）只负责同步远端主分支，以及创建、查看和清理 worktree。需求涉及的代码、测试、配置和文档修改，暂存与提交都必须在对应需求 worktree 中完成。不得在原始工作区直接实现需求或提交需求改动。原始工作区已有的用户改动必须保留，不得为切换或同步而擅自丢弃、覆盖或移动。原始工作区存在未跟踪文件时，按下述规则处理，不得因为创建 worktree 而静默丢失这些内容。

worktree 只负责隔离工作目录和分支，不处理 Git 写权限、GitHub 交付或提交内容检查。

## 空远端仓库初始化

当用户已明确选择 worktree 模式，且目标远端仓库已确认为空、没有默认分支或没有可用的 PR base 分支时，普通 worktree 流程缺少可同步和分支起点。此时允许执行一次受限的 bootstrap：

1. 先确认远端仓库、权限和空状态；不要用过期的 remote-tracking 引用或其他仓库内容代替空远端的事实。
2. 创建只包含项目名称和初始化状态的最小 `README.md`，作为 bootstrap 提交推送到远端 `main`。该提交不得包含本次需求的代码、测试、配置、规划文档或其他无关文件。
3. 远端 `main` 建立后，在原始工作区执行普通同步门禁：普通仓库切换到 `main` 并成功运行 `git pull --ff-only origin main`；个人 Fork 按 [`fork-maintenance.md`](fork-maintenance.md) 同步 `upstream/main` 和 `origin/main`；然后从正确的最新基线创建本次需求的 `agent/...` 分支和独立 worktree。
4. bootstrap 完成后回到普通 worktree 创建流程；bootstrap README 不属于本次需求的验收成果。

bootstrap 只解决“没有 base 分支”这一 worktree 前置条件，不包含需求内容。若初始化需要偏离普通 worktree 的物理顺序，偏离范围必须限于 README bootstrap，并记录该偏离。

## 原始工作区存在未跟踪文件时

Git worktree 默认只复制已提交的版本，不会自动携带原始工作区的未跟踪文件。为保留用户内容并让需求 worktree 能够访问这些文件，执行以下有序流程：

1. 在原始工作区执行 `git status --short`，建立未跟踪文件清单；清单至少记录每个相对路径、初始内容指纹和是否为本次需求范围。默认只纳入未被 `.gitignore` 排除的未跟踪文件；需要携带被忽略文件时，必须显式记录并按同样的冲突规则处理。清单应随本次 worktree 生命周期保留，不能只依赖稍后重新运行 `git status` 推断初始状态。
2. 不要用 `git clean`、`git reset`、普通 `git stash`/`git stash -u`、删除或覆盖操作处理这些文件。原始工作区保留未跟踪内容，继续执行本节要求的主分支同步。`git pull --ff-only` 若报告未跟踪文件将被覆盖、某个清单路径与远端新增或修改文件冲突，或同步结果无法安全保留该内容，必须立即停止：保留现场，不创建需求 worktree，不自行改名、移动、删除或覆盖冲突文件，并向用户报告冲突路径和 pull 错误。
3. 只有初始同步门禁成功后，才能按下一节创建需求 worktree。worktree 建立后，将清单中的未跟踪文件按原始相对路径复制到 worktree，并校验内容指纹；原始工作区副本继续保留，作为恢复校验源。复制动作不得把未跟踪文件自动加入暂存区或提交。若复制时目标路径已由同步后的基线分支提供，视为冲突，停止并报告，不得覆盖目标。
4. 在需求开始前，将清单中的文件分类为“涉及本次需求”和“不涉及本次需求”；无法确定时按“涉及”处理，不自动恢复。涉及需求的文件是否纳入提交由上层工作流决定；不涉及需求的文件不得被需求改动，也不得进入需求提交。
5. 对不涉及本次需求的文件，只有在该 worktree 已完成交付、原始工作区已同步到目标主分支，且该路径仍未被主分支跟踪或占用时，才能从需求 worktree 按清单恢复到原始工作区。恢复前校验原始工作区路径未被用户后续修改、需求 worktree 中的文件与“不涉及需求”的范围一致；任一校验失败都必须停止并报告，禁止无条件覆盖。恢复后重新运行状态和内容指纹检查。

并行 worktree 共享同一份未跟踪文件时，必须为每个 worktree 保留清单和初始指纹；在仍有未交付 worktree 需要这些文件时不得提前恢复。所有携带该文件的相关 worktree 完成各自交付或明确释放后，才按上述合并后条件恢复。

## 在明确选择 worktree 后开始一个需求

1. 每创建一个完整需求对应的 worktree 前，都必须在原始工作区完成以下同步门禁。确认仓库 remote 和实际主分支；确认原始工作区没有会妨碍安全切换或拉取的已跟踪未提交改动，并处于该主分支。未跟踪文件不因其自身存在而自动阻塞，但必须先按“原始工作区存在未跟踪文件时”一节建立清单并保留；若未跟踪内容与初始 pull 冲突，则按该节停止。若当前不在主分支，只能在不覆盖或移动用户改动的前提下安全切换；随后执行一次快进拉取：

   普通仓库执行：

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

   个人 Fork 执行：

   ```bash
   git fetch upstream main
   git switch main
   git merge --ff-only upstream/main
   git push origin main
   git switch <personal-branch>
   ```

   只有上述同步门禁成功后，才能继续创建 worktree；即使没有新提交而显示已是最新，也算成功。若已跟踪未提交改动、当前分支状态、网络、认证、非 fast-forward、未跟踪文件冲突或其他原因使切换或同步不能安全成功，必须保留现有改动并停止创建 worktree，先按授权处理同步阻塞。此必需顺序本身不授予网络访问或 Git 状态变更权限；若当前任务没有相应授权，或运行环境不具备执行 `git switch`、`git pull`、`git worktree add` 所需权限，应停止创建并请求或等待所需授权/运行权限。权限具备后重新完成本同步门禁，成功前不得继续。不得以 fetch 后直接使用 remote-tracking 引用、commit SHA 或可能过期的本地分支绕过此门禁。

2. 仅在步骤 1 的拉取成功后，为需求创建唯一分支，并在原始工作区之外创建专用 worktree。分支名称和起点由上层流程确定；普通需求必须以刚刚同步的本地主分支作为起点；若存在未跟踪文件，worktree 建立后还必须按上一节将其安全复制并校验到对应相对路径：

   普通仓库从 `main` 创建；个人 Fork 从已同步的个人维护分支创建：

   ```bash
   git worktree add ../project-agent-issue-42-change -b agent/feat-issue-42-change <base-branch>
   ```

   如使用依赖分支，起点必须由上层工作流明确；该例外只改变同步门禁之后选择的 worktree 起点，不免除步骤 1 的 main 同步，也不得用过期本地分支、任意 remote-tracking 引用或 SHA 绕过门禁。未获明确批准时，始终从刚同步的本地主分支创建。若分支已存在，先确认它是否属于当前需求的既有 worktree；不得以未核实的旧分支基点替代已批准的起点。不要让两个 worktree 同时检出同一个分支。

3. 在该 worktree 中完成需求相关的文件修改；不得把这些文件带回原始工作区修改或提交。

4. worktree 创建、隔离、同步和串行交付完成后，是否提交、推送或清理由上层工作流决定；本文件不增加这些操作的授权。

## 多 worktree 并行开发的串行交付

可以同时在多个独立 worktree 中开发已经明确拆分的工作项，但凡这些并行 worktree 需要依次集成到同一主分支，就不得同时把各分支依赖的远端主分支视为最新。按以下队列一次处理一个工作项：

1. 选定第一个已完成并通过相关验证的 worktree，将它标记为待交付；交付完成并确认集成后，不对其本地分支执行 checkout、pull、merge、rebase 或删除，也不移除该 worktree。
2. 集成确认后，只回到原始工作区，将实际 base 分支快进同步到 remote 的最新状态。仅在原始工作区状态允许安全切换时执行，例如：

   普通仓库：

   ```bash
   git switch main
   git pull --ff-only origin main
   ```

   个人 Fork：按 [`fork-maintenance.md`](fork-maintenance.md) 先同步 `upstream/main` 与 `origin/main`，再确认个人维护分支的最新状态。

3. 在下一个尚未交付的需求 worktree 中，将该工作分支 rebase 到刚同步的实际 base 分支。普通仓库通常是 `main`，个人 Fork 通常是个人维护分支。rebase 在需求 worktree 中执行，不在原始工作区执行：

   ```bash
   git rebase <base-branch>
   ```

   若发生冲突，只按已批准的需求语义解决，并在该 worktree 中重新运行受影响的检查和必要测试。冲突需要新的产品行为或架构决定时，先暂停并取得相应决定，不自行扩大需求。

4. rebase 和验证通过后，将该 worktree 标记为下一个待交付项；对已完成集成的 worktree 不做后续分支处理。重复直到所有工作项均已处理。

## 合并后的处理与清理

在本 worktree 工作流中，某 worktree 完成集成后，只在原始工作区同步 remote 主分支。不得对该 worktree 的本地分支执行 checkout、pull、merge、rebase、delete 等操作，也不得把清理该分支或移除该 worktree 作为继续流程的前置条件。若仍有其他待交付 worktree，只将队列中的下一个 worktree rebase 到刚同步的最新主分支，在该 worktree 解决允许范围内的冲突并重新验证；已完成集成的 worktree 保持原状。

本流程不自动删除已合并需求的 worktree 或本地分支。若该需求 worktree 携带了“不涉及本次需求”的未跟踪文件，普通仓库必须先在原始工作区将 `main` 从远端同步成功；个人 Fork 必须先按 [`fork-maintenance.md`](fork-maintenance.md) 同步 `upstream/main` 和 `origin/main`，再按“原始工作区存在未跟踪文件时”一节的清单和冲突校验从 worktree 恢复这些文件；恢复完成后仍保留 worktree，除非用户另行要求清理。只有用户另行明确要求清理时，才按其指定范围处理，并遵守现有 Git 授权。
