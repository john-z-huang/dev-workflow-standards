# Shell 环境与脚本

适用于 Shell 脚本的生成、执行和兼容性验证。先确认脚本实际运行环境；交互终端的默认 Shell 不决定新脚本使用的 Shell。Python 执行规则见 [`python-environment.md`](python-environment.md)。

## 本机 macOS 环境事实

本机交互 Shell 默认为 Zsh 5.9，Bash 和 sh 的版本为 `3.2.57(1)-release`。这些是本机事实，不是所有 macOS、容器或远端环境的通用版本保证；在其他环境中按实际可用 Shell 和版本判断。

## 本地新生成脚本

- 默认生成 Bash 脚本，不生成 Zsh 脚本；不要因为当前终端默认为 Zsh 就改变脚本选择。
- Bash 脚本文件第一行必须使用 `#!/bin/bash` 或 `#!/usr/bin/env bash` 声明运行环境，避免被默认 Zsh 按不兼容语法执行。
- 为本机生成的 Bash 脚本必须兼容 Bash `3.2.57(1)-release`，不使用超过该版本的特性。例如不要使用关联数组、`mapfile` 或 `readarray`。
- 按 shebang 执行可执行脚本，或显式使用适用的 Bash；不要用 `zsh script.sh` 或 `sh script.sh` 验证 Bash 脚本的运行行为。

## 已有脚本

运行已有 Zsh 脚本时，确认所用特性不超出本机 Zsh 5.9。超过该版本时，按当前任务的修改范围处理兼容性，不擅自升级 Shell 或重写脚本。

默认生成规则不要求把已有的 `sh`、Bash 或 Zsh 脚本统一改写。先尊重已有 shebang、项目要求和目标环境；需要修复兼容性时，只修改任务涉及的部分。

## Docker 与远端云环境

在 Docker 容器或远端云环境中，默认优先选择 `sh` 作为预期运行脚本的 Shell。确认目标环境中存在 Bash 或 Zsh 等其他 Shell 后，再按任务需要选择。不要将本机的 Shell 路径或版本当作远端可用性的证据。

## 选择与验证案例

| 场景 | 处理 |
|---|---|
| 本机默认终端是 Zsh，需要新建本地脚本 | 生成带 Bash shebang 的 Bash 3.2 兼容脚本。 |
| 本地已有 Zsh 脚本 | 检查 Zsh 5.9 兼容性，按已有 shebang 或显式 Zsh 执行。 |
| 容器或远端尚未确认 Bash/Zsh 可用 | 优先编写可由 `sh` 执行的脚本，不使用 Bash 专属语法。 |
| 已确认目标环境存在 Bash，任务需要其特性 | 可以选择 Bash，并按目标实际版本检查兼容性。 |

语法检查使用目标 Shell 的 `-n`；它只能证明语法可解析，不能单独证明特性兼容或运行行为正确。验证本机 Bash 时核对执行的解释器确为兼容基线，不能仅凭较新 Bash 的语法检查宣称通过 Bash 3.2 验收。

## 依据

本规则迁自本机全局 `AGENTS.md` 的 Shell 章节，迁移范围与验收要求见 [Issue #64](https://github.com/john-z-huang/dev-workflow-standards/issues/64)。
