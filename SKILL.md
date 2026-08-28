---
name: dev-workflow-standards
description: >-
  通用开发工作流规范：Git 分支命名与提交约定、禁止 Code Agent 署名、
  GitHub Issue/PR 流程、堆叠 PR 的 base/head 分支管理、gh CLI 与 GitHub 集成层操作规范、GH_TOKEN 安全处理、网络与认证排查、
  禁止特定 Code Agent 独占功能、中文文档与提交语言要求。适用于任何需要严格开发纪律的项目。
---

# 通用开发工作流规范

本 Skill 定义了跨项目通用的开发工作流规范。各项目的 `AGENTS.md` 或 `CLAUDE.md` 可引用本 Skill，并补充项目特有的约定。

---

## 文档与提交语言

- 项目文档使用中文；如确有必要保留英文术语，应同时提供清晰的中文说明。
- Git 提交信息使用中文，简明说明变更目的和范围。

---

## Git 规范

### 分支命名

- Git 分支名称必须只使用 ASCII 字符，不得包含中文或其他非 ASCII 字符，以避免终端、脚本、CI、URL 编码及跨平台协作中的兼容性问题。
- 分支名称中的单词使用小写英文字母、数字和连字符（`-`）表示；需要表达层级时，仅可使用斜杠（`/`）分隔层级。
- 分支名称应以清晰的类别前缀开始，例如 `agent/`、`feat/`、`fix/`、`docs/` 或 `refactor/`，并使用简短的英文描述说明变更内容。

**合规示例**：`agent/docs-branch-naming`、`fix/batch-result-validation`、`feat/async-batch-submit`。

**不合规示例**（含中文或非 ASCII 字符）：`agent/更新-git-规则`、`修复/批处理校验`；**不合规示例**（前缀不明确）：`feature/分支命名`、`update-docs`。

### 堆叠 PR（Stacked PR）

当一个功能依赖尚未合并的 Issue 分支，或用户明确要求以已有功能分支作为 PR 目标时，使用堆叠 PR，不要默认将目标分支设为 `main`。

典型拓扑如下：

```text
main
└── agent/issue-7-session       # 基础 PR / 当前 Issue 分支
    └── agent/issue-8-runtime   # 新功能分支，PR base 为 issue-7 分支
```

标准流程：

1. 确认基础分支、远端分支和已有 PR：`git branch -vv`、`gh pr list`、`gh pr view`。
2. 从基础分支的最新远端状态创建新分支，例如 `git switch -c agent/issue-8-runtime`。
3. 只在新分支提交当前 Issue 的代码和测试；已有基础分支的改动不重复提交。
4. 推送新分支：`git push -u origin <head-branch>`。
5. 创建 PR 时显式指定 base 和 head，例如：

   ```bash
   gh pr create --draft --base <base-branch> --head <head-branch> \
     --title "<title>" --body-file <pr-body-file>
   ```

6. PR 正文说明依赖的基础分支或基础 PR，并使用 `Closes #<issue>` 关联当前 Issue。
7. 创建后核验目标没有意外变成 `main`：

   ```bash
   gh pr view <pr-number> --json baseRefName,headRefName,state,url
   git diff <base-branch>...<head-branch> --stat
   ```

如果已经错误地从基础分支向 `main` 发起了 PR，且该 PR 尚未合并：

- 按用户授权关闭错误 PR，并保留 Issue 开放状态；
- 已推送到基础分支的错误提交使用 `git revert <commit>` 撤回，不改写共享分支历史；
- 推送撤回提交后，从更新后的基础分支创建新的 Issue 分支；
- 使用 `git cherry-pick <original-commit>` 或重新实现，将已验证的功能提交到新分支；
- 新 PR 显式设置 `--base <base-branch>`，而不是依赖 CLI 默认目标分支。

基础 PR 合并后，再根据仓库协作约定将堆叠 PR 的 base 更新到 `main` 或其他新的基础分支；更新前先确认差异范围，并避免未经授权的强制推送。

### 提交规范

- 以可独立验证的功能模块为提交边界；每完成一个功能模块，都必须同时补充或更新相应测试代码。
- 只有在该模块相关测试通过后，才可提交该模块的 Git 改动；提交前应记录实际执行的验证命令及结果。
- 不得将多个互不独立的功能模块、重构或文档变更混入同一个提交。应按可审查、可回滚的最小逻辑单元拆分提交。

  **正确做法**：一个提交只包含一个功能的实现及其测试 → `feat: 添加批量请求校验`。

  **错误做法**：一个提交同时包含新功能实现、文档更新和不相关的重构 → `feat: 批量处理、文档优化与代码清理`。

- 一个 Issue 涉及多个改动点时，须先规划每个改动点的职责与文件边界。每个改动点完成实现及对应测试后，先运行该改动点的针对性测试和必要的回归测试；仅在测试通过后，才提交该改动点。不得将复杂需求的全部实现堆入一次提交。
- 提交信息保持中文、简明，并准确描述该提交所包含的模块变更。

### 提交内容署名约束

Code Agent 是辅助开发工具，不是真实的开发人员。Code Agent 不能对最终代码改动承担责任，只有对代码改动负责的工程师才拥有署名权。因此：

- Git 提交信息中不得包含 `Generated with`、`Co-Authored-By` 等任何 Code Agent 使用声明。
- 不得在任何位置（提交信息、Pull Request 描述、文档、代码注释等）声明本次改动所使用的特定 Code Agent 产品。
- 代码改动的署名权完全归属于工程师；Code Agent 不拥有署名权，也不承担代码改动引发的责任。
- 提交信息仅反映工程师的变更意图与内容，保持简洁、中文、可追溯。

---

## 需求与变更流程

### GitHub 操作规范

- 涉及 GitHub（包括 Issue、Pull Request、Actions、仓库信息或评论）前，必须先查阅当前 Code Agent 提供的 GitHub Skill，并遵循其中与当前任务相关的建议。
- GitHub 操作优先通过 GitHub CLI（`gh`）执行。若开发环境是云端容器且未安装 `gh` CLI，可改用当前 Code Agent 已授权的 GitHub Connector 或 GitHub App 集成层执行等效操作；不得因为缺少 `gh` CLI 而改用浏览器或浏览器自动化工具。
- 使用 GitHub Connector 或 GitHub App 集成层时，必须确认该集成已获得目标仓库及当前操作所需的授权，并遵循其工具接口的参数、确认和返回值约定；不得要求用户在对话中粘贴访问令牌，也不得自行猜测或伪造授权信息。
- 无论使用 `gh` CLI 还是已授权集成层，都必须显式核对仓库、Issue、PR、base/head 分支及操作结果；集成层应提供与下述 `gh` 示例等价的查询、创建、更新、评论、合并和核验能力。

  **正确做法**：使用 `gh issue create --title "..." --body "..."`，或调用已授权 GitHub Connector / GitHub App 的等效 Issue 创建操作；使用 `gh pr create --title "..." --body "..."`，或调用其等效 PR 创建操作。

  **错误做法**：在浏览器中打开 `github.com` 手动创建 Issue/PR、使用 Playwright/Selenium 等浏览器自动化工具操作 GitHub 页面。

- 执行 `gh` 命令时，必须使用能够进行受限网络访问的沙箱环境，不得在完全禁止网络访问的沙箱中运行 `gh`。`gh` 需要与 GitHub API 通信，完全断网的沙箱会导致命令不可用，应使用允许出站 HTTPS 请求但施加其他合理限制的沙箱配置。已授权 GitHub Connector / GitHub App 集成层的网络访问由集成运行环境负责，但调用仍必须通过其正式接口完成。

### 网络与认证

- 在受限或配置代理的网络环境中使用 `gh` 前，先确认请求将通过可访问的 HTTP Proxy；不得因代理或 GitHub API 不可达而直接判定 `GH_TOKEN` 或本地登录凭据失效。使用已授权 GitHub Connector / GitHub App 集成层时，遵循其连接状态和授权检查，不将 CLI 的代理或 `GH_TOKEN` 排查要求强加于集成层。

  **使用 `gh` CLI 时的认证排查顺序**：
  1. 先检查代理与 GitHub API 连通性（如 `gh api /zen 2>&1` 或 `curl -I https://api.github.com`）。
  2. 确认网络连通后，再检查 `GH_TOKEN` 是否已设置和凭据是否有效。

- 使用 `gh` CLI 时，确认网络连通后若仍需重新认证：先确认环境变量 `GH_TOKEN` 已设置，再仅通过标准输入将其传递给 `gh auth login --with-token` 完成认证；`GH_TOKEN` 未设置时应报告认证阻塞，不得猜测、伪造或要求用户在对话中粘贴令牌。
- 若云端容器没有 `gh` CLI 且使用已授权 GitHub Connector / GitHub App 集成层：仅使用当前已建立的授权连接；若集成未连接、授权不足或无法访问目标仓库，应报告认证或权限阻塞，不得要求用户粘贴令牌，也不得绕过集成层改用浏览器操作。
- `GH_TOKEN` 是敏感信息：严禁打印、回显、插值展示、记录或写入其值。

  **禁止的行为（非穷举）**：
  - 终端与工具输出（如 `echo $GH_TOKEN`、`printenv GH_TOKEN`）
  - 日志文件、源代码、配置文件
  - 提交信息、Issue、Pull Request、评论和错误报告
  - 调试输出（如 `set -x` 后执行含令牌的命令）

### Issue 与 PR 流程

- 新增功能或修复新发现的问题前，必须先在本项目的 GitHub Issues 中创建对应的开放 Issue。
- Issue 必须清晰、详细地说明以下内容：
  - 功能需求或缺陷表现
  - 影响范围
  - 预期行为与验收标准
  - 必要时补充：复现步骤、技术约束、前置依赖
- 实现改动必须通过 Pull Request 合并，并在 PR 描述中通过 `Closes #<Issue 编号>`（或等效关键字）关联对应的开放 Issue。
- 未关联任何开放 Issue 时，禁止将本地改动推送到 GitHub。

### PR 合并后流程

当用户在 GitHub 上完成 PR 合并后，须先根据 PR 的 base/head 分支执行清理。不要假设所有 PR 都以 `main` 为目标分支。

1. **确认 PR 合并状态和分支关系**：使用以下命令确认该 PR 在 GitHub 上的状态为已合并（`MERGED`），并读取 `baseRefName` 与 `headRefName`：

   ```bash
   gh pr view <PR 编号> --json state,mergedAt,baseRefName,headRefName
   ```

   若 PR 尚未合并或状态异常，应终止后续步骤并报告原因。若工作区有未提交的变更，应先处理（提交或暂存）再切换分支。

2. **按 base 分支选择清理目标**：

   - **普通 PR（base 为 `main`、`master` 或仓库默认分支）**：切换到该 base 分支，并拉取对应远端更新。

     ```bash
     git switch main
     git pull --ff-only origin main
     ```

   - **堆叠 PR（base 为其他未合并的功能/Issue 分支）**：切换到该 base 分支，并只拉取该分支；不要因为 PR 已合并就切换到 `main`。

     ```bash
     git switch <base-branch>
     git pull --ff-only origin <base-branch>
     ```

     base 分支是后续 PR 的依赖，必须保留，不得作为本次清理对象。

3. **删除已合并 PR 的 head 分支**：在已同步的 base 分支上执行：

   ```bash
   git branch -d <head-branch>
   ```

   只删除已合并 PR 的 head 分支，不删除堆叠 PR 的 base 分支。若 `git branch -d` 报告分支未完全合并，先检查 PR 的实际合并方式和本地差异；未经用户明确授权，不得使用 `git branch -D`。远端 head 分支是否删除按仓库策略或用户明确要求处理。

4. **继续清理上层堆叠分支**：当 base 分支后续也合并到 `main` 时，再对那个 PR 重复本流程；此时才切换到 `main`、拉取 `origin/main`，并删除该层已合并的 head 分支。

**合并后命令示例**：

```bash
# 1. 确认 PR 已合并并读取 base/head
gh pr view <PR编号> --json state,mergedAt,baseRefName,headRefName

# 2. 如果是堆叠 PR，切换到它的基础分支
git switch <base-branch>

# 3. 拉取基础分支
git pull --ff-only origin <base-branch>

# 4. 删除已合并 PR 的本地 head 分支
git branch -d <head-branch>
```

## 禁止使用特定 Code Agent 独占功能

不同的 Code Agent 产品提供了各自独有的扩展机制。这些功能仅在该特定产品下生效，其他 Code Agent 无法识别或执行，会破坏 Skill 的可移植性和通用性。

### 禁止使用 Claude Code Hooks

本 Skill 及引用本 Skill 的所有项目中：

- **禁止**使用任何特定 Code Agent 的独占功能来实现自动化逻辑。
- 若 Skill 中需要实现自动化脚本或事件触发功能，必须采用以下可移植方案：
  1. **脚本实现**：在 `scripts/` 目录下创建独立的脚本文件（Shell 或 Python），具备清晰的入口、参数说明和错误处理，可在任何标准环境中运行。
  2. **功能描述文档**：在 `references/` 目录下创建对应的描述文档（如 `references/<脚本名>.md`），完整说明功能目的、触发时机、用法示例、集成方式和退出码。
  3. **Skill 文档引用**：在 `references/automation-index.md` 的脚本索引表格中新增一行，引用对应描述文档。
- 选择脚本语言时优先考虑可移植性：Shell 脚本（`bash`/`sh`）适合简单的文件操作和命令编排；Python 脚本适合需要更复杂逻辑、数据处理或跨平台一致性的场景。

- **禁止**使用 Claude Code 的 Hooks（事件钩子）、特定产品专有的配置文件格式、仅特定 Code Agent 可解析的工具绑定声明。

**合规示例**：在 `scripts/pre-commit-check.sh` 中实现代码格式化检查逻辑，在 `references/pre-commit-check.md` 中说明用法和集成方式，并在 `references/automation-index.md` 脚本索引表格中引用该文档。

**不合规示例**：在 Claude Code 的 Hooks 配置文件中声明提交前自动触发脚本，该配置仅对 Claude Code 生效，其他 Code Agent 无法感知或执行。

#### 自动化功能索引

所有自动化脚本的索引及其描述文档参见 [`references/automation-index.md`](./references/automation-index.md)。新增脚本时，在该文档的脚本索引表格中添加对应条目。

---

## 附录：快速检查清单

以下为通用检查项；各项目应在此基础上补充项目特有的检查项。

### 开始新功能前

- [ ] 已在 GitHub 创建对应的开放 Issue（含清晰的标题、描述和验收标准）
- [ ] 已阅读与该功能相关的源码、测试和文档（不批量载入无关内容）

### 新增自动化功能前

- [ ] 已确认所选方案不依赖任何特定 Code Agent 的独占功能（如 Hooks、专有配置格式等）
- [ ] 脚本已创建于 `scripts/` 目录，具备清晰的入口、参数说明和错误处理
- [ ] 功能描述文档已创建于 `references/` 目录，包含目的、触发时机、用法示例、集成方式和退出码
- [ ] `references/automation-index.md` 脚本索引表格已新增对应条目，引用对应描述文档
- [ ] 脚本可在任何标准环境中运行，不依赖特定 Code Agent 的运行时或插件

### 提交前

- [ ] 该提交仅包含一个可独立验证的功能模块（不混入无关变更）
- [ ] 对应的测试代码已补充或更新，且测试通过
- [ ] 已记录实际执行的验证命令及结果
- [ ] 提交信息使用中文，简明描述模块变更
- [ ] 提交信息及任何产物中不含 `Generated with`、`Co-Authored-By` 等 Code Agent 使用声明

### 发起 PR 前

- [ ] 分支名称符合规范（ASCII、小写、类别前缀）
- [ ] 如使用堆叠 PR，已明确核对 base 分支、head 分支及基础 PR，未意外指向 `main`
- [ ] PR 描述中包含 `Closes #<Issue 编号>`（或等效关键字）
- [ ] 已确认关联的 Issue 处于开放状态
- [ ] 所有 GitHub 操作均通过 `gh` CLI，或在云端容器缺少 `gh` CLI 时通过已授权的 GitHub Connector / GitHub App 集成层执行（非浏览器或浏览器自动化）
- [ ] 使用 `gh` CLI 时，命令在受限网络沙箱（允许出站 HTTPS）中运行；使用集成层时，已确认其授权连接和目标仓库权限有效
- [ ] PR 在 GitHub 上完成审核并合并后，通知 Code Agent 执行 PR 后清理流程

### PR 合并后

- [ ] 通过 `gh pr view` / `gh pr status` 或已授权 GitHub Connector / GitHub App 的等效查询确认 PR 在 GitHub 上为已合并状态
- [ ] 已核对 PR 的 `baseRefName` 和 `headRefName`
- [ ] 普通 PR 已切换并同步 base 分支；堆叠 PR 已切换并同步对应的中间 base 分支，而不是默认切换到 `main`
- [ ] 只删除了已合并 PR 的本地 head 分支，保留堆叠 PR 仍依赖的 base 分支
- [ ] 仅在 base 分支本身也已合并到 `main` 后，才执行 `main` 分支清理
