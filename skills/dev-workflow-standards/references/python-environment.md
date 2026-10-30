# Python 环境与执行

适用于 Python 解释器和依赖环境选择，以及脚本、模块、一次性命令的执行。仅在相关开发任务中读取；Shell 脚本规则见 [`shell-environment.md`](shell-environment.md)。

## 先确认显式要求

- 项目或用户明确指定 Python 版本、解释器或虚拟环境时，遵循该要求；版本指定也包括 uv 可发现的 `.python-version` 文件。
- 项目存在 `pyproject.toml` 时，按下节识别项目根目录并优先创建或复用项目虚拟环境；用户或项目明确指定其他虚拟环境与依赖管理方式时，遵循其配置。判断时检查当前任务所属项目及 uv 可发现的父目录项目，不能只根据当前目录没有文件就认定无项目。
- PEP 723 inline metadata 中的 `requires-python` 和依赖声明也必须满足。默认版本不能覆盖已声明的版本约束；有冲突时报告具体要求，不静默改用其他环境或修改约束。
- 下文的 `--managed-python` 只适用于采用默认 uv 托管环境的情况；明确要求系统解释器或已有虚拟环境时，不用该选项覆盖要求。只有版本要求、没有其他环境要求时，可继续使用 uv 托管解释器，但必须选择要求的版本。
- 不向全局解释器安装依赖。

## 已有 `pyproject.toml` 的项目

### 确定项目或 workspace 根目录

先确认当前任务所属项目，而不是遇到一个 `pyproject.toml` 就在其目录创建环境：

- 单项目使用该项目根 `pyproject.toml` 所在目录；Git 仓库根目录不一定是 Python 项目根目录。
- uv 多模块 workspace 使用声明 `[tool.uv.workspace]` 的根 `pyproject.toml` 所在目录，并核对 `members`、`exclude` 与当前包的成员关系。从成员或更深目录开始工作时，也要先回溯到这个 workspace 根目录。
- 同一个 workspace 只在根目录创建、复用一份项目环境，成员目录不另建 `.venv`。成员各自的 `pyproject.toml` 不是环境创建位置；按需用 `uv run --package <成员包名>` 选择目标成员。
- 同一仓库有多个 `pyproject.toml` 不代表它们属于同一 workspace。被排除的目录或独立项目按其实际项目根与配置处理；不要仅凭目录嵌套、文件数量或最外层文件合并环境。根目录或成员关系不能确认时，先澄清再创建。

### 创建并持续使用项目环境

未明确指定其他环境或依赖管理方式时，优先在已确认的根目录使用 `uv venv .venv` 创建虚拟环境。创建所选 Python 必须满足用户要求、`.python-version`、项目 `requires-python`，以及 workspace 全体成员的兼容约束；不能把无项目场景的默认 3.14 强加到已有项目。

只在环境缺失时执行创建命令。已有兼容的 `.venv` 时直接复用，不重复运行 `uv venv`，避免已有环境被重建；路径被非环境内容占用，或已有解释器不兼容时，报告并按任务范围处理，不自动清空、删除或覆盖。

例如，先确认项目根与版本约束，且根目录 `.venv` 不存在后：

```bash
cd /path/to/project-root
uv venv .venv
uv run -- python -c 'import sys; print(sys.executable)'
```

后续项目运行、测试及开发工具均使用这份环境的 Python，通过项目上下文中的 `uv run` 执行，或在需要解释器路径的工具中指定根目录的 `.venv/bin/python`（Windows 为 `.venv\Scripts\python.exe`），不使用全局解释器。检查 `sys.prefix`、`sys.executable` 和环境位置确认实际选择，不能仅凭终端中显示已激活环境认定正确。

workspace 成员命令也从已确认的 workspace 根目录执行，例如：

```bash
uv run --package member-name -- python -c 'import sys; print(sys.executable)'
```

`uv venv` 只负责创建环境，不代表依赖已经安装。依赖按项目配置通过 `uv sync` 或 `uv run` 同步；项目已有锁文件及锁定策略时遵循该策略。

用户或项目显式指定已有虚拟环境、自定义环境路径（例如通过 `UV_PROJECT_ENVIRONMENT`）或其他管理方式时，保持原有优先级。若当前激活环境或继承的环境变量指向其他项目，先核实其归属，不直接将其作为本项目环境；不通过 `--active`、`--no-project` 或 `--isolated` 意外绕过根环境。用户明确要求独立运行的 PEP 723 脚本仍按元数据隔离，不强制并入项目共享环境。

## 无项目时的默认环境

没有适用的 `pyproject.toml`，且没有用户或项目指定 Python 环境时，默认使用 uv 管理的 CPython 3.14。不要将 Miniconda `base`、Conda 或 Homebrew Python 作为默认解释器。确认版本约束兼容后，使用 `uv run --managed-python --python 3.14`；普通独立脚本再加 `--no-project`，完整示例见下节。

`--python 3.14` 是缺省版本选择，不是覆盖 `.python-version`、用户指定版本或脚本约束的强制参数。脚本约束排除 3.14 时，按其声明选择兼容版本，不附加默认的 `--python 3.14`。不要为了采用缺省值而提高现有项目的最低 Python 版本。

uv 默认会在所需版本缺失时自动下载，除非配置或 `--no-python-downloads` 禁止，因此通常不需要预先安装 Python。若默认无项目场景需要提前安装，使用 `uv python install 3.14`；有明确版本或 `.python-version` 请求时，按其请求安装。

通用命令 `uv python install` 在没有明确版本、也没有 `.python-version` 请求时默认安装最新版本；这不等于本 Skill 无项目执行默认值会随最新版本变化。默认执行仍选择 3.14。

## 无 `pyproject.toml` 时的执行方式

没有 `pyproject.toml` 的项目或独立脚本也必须通过 `uv run` 执行，不直接调用 `python`、`python3` 或 `pip`；用户或项目明确指定其他执行与依赖管理方式时，遵循其要求。

以下示例均假定没有更高优先级的环境或版本要求，且脚本约束兼容 3.14。示例中的文件名、包名和参数按实际任务替换。存在显式要求时先按上节选择参数，不能原样套用默认值。

### 无额外依赖的脚本

```bash
uv run --no-project --managed-python --python 3.14 -- script.py arg1
```

### 含 PEP 723 元数据的脚本

```bash
uv run --managed-python --python 3.14 -- script.py arg1
```

uv 按脚本元数据准备隔离环境并忽略项目依赖，因此不必加 `--no-project`。脚本已声明其他版本要求时遵循该要求；例如其约束排除 3.14 时，不附加默认版本参数：

```bash
uv run --managed-python -- script.py arg1
```

### 未在脚本声明的临时依赖

```bash
uv run --no-project --managed-python --python 3.14 --with rich -- script.py arg1
uv run --no-project --managed-python --python 3.14 --with rich --with httpx -- script.py arg1
uv run --no-project --managed-python --python 3.14 --with-requirements requirements.txt -- script.py arg1
```

多个依赖可重复 `--with`，也可用 `--with-requirements requirements.txt`。需要重复使用的脚本优先在 PEP 723 元数据或项目配置中声明依赖。此处 `--no-project` 避免把当前项目依赖一并加入；它不保证忽略已激活或在当前、父目录发现的虚拟环境，仍须先核实所选环境符合任务要求。

### 模块或一次性命令

```bash
uv run --no-project --managed-python --python 3.14 -- python -m module_name arg1
uv run --no-project --managed-python --python 3.14 -- python -c 'print("ok")'
```

此处的 `python` 是 `uv run` 的命令参数，不是直接调用全局解释器。

## 选择案例

| 已观察事实 | 处理 |
|---|---|
| 无项目、无明确环境要求、脚本兼容 3.14 | 默认 uv 管理的 CPython 3.14，按上述四类选择命令。 |
| 无项目，但 uv 可发现的 `.python-version` 指定 3.12 | 遵循 3.12，不附加默认的 `--python 3.14`。 |
| 用户明确要求系统解释器或已有虚拟环境 | 遵循指定环境，不用 `--managed-python` 覆盖。 |
| 单项目根目录有 `pyproject.toml`，未另定管理方式 | 在根目录用 `uv venv .venv` 创建缺失环境；已有兼容环境则复用，后续使用项目解释器。 |
| uv workspace 根与两个成员均有 `pyproject.toml` | 根据根声明及成员关系定位根目录，仅根 `.venv` 供各成员共享，不在成员目录创建环境。 |
| 从 workspace 成员的更深目录启动任务 | 先回溯并确认 workspace 根，再在根目录创建或复用环境。 |
| 仓库中有互不属于同一 workspace 的 Python 项目 | 分别按实际项目根和配置处理，不强行共享仓库根环境。 |
| 已有兼容 `.venv`，或项目明确指定其他管理方式 | 前者复用不重建；后者遵循项目配置，不套用无项目默认值。 |
| PEP 723 声明 `requires-python = ">=3.12,<3.14"` | 使用兼容其声明的解释器；不附加默认 3.14，不强行修改声明。 |

## 依据

本规则迁自本机全局 `AGENTS.md` 的 Python 章节，并纳入 [Issue #64](https://github.com/john-z-huang/dev-workflow-standards/issues/64) 的 [Python 3.14 补充要求](https://github.com/john-z-huang/dev-workflow-standards/issues/64#issuecomment-6418815123) 及项目根虚拟环境要求。uv 参数和环境行为参见 [脚本指南](https://docs.astral.sh/uv/guides/scripts/)、[Python 版本](https://docs.astral.sh/uv/concepts/python-versions/)、[项目环境](https://docs.astral.sh/uv/concepts/projects/layout/#the-project-environment)、[workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) 和 [命令参考](https://docs.astral.sh/uv/reference/cli/#uv-venv)。
