# 暂存区检查

## 功能描述

`scripts/check-staged-changes.py` 检查暂存区是否存在 Git 空白错误，并可按项目需要执行一个测试命令。测试命令使用参数列表执行，不经过 shell。

## 触发时机

- 推荐作为标准 Git `pre-commit` hook，在创建 commit 前触发。
- 项目也可以手动传入测试命令，执行提交前验证。

## 手动执行

```bash
# 只检查暂存区空白错误
python3 scripts/check-staged-changes.py

# 检查暂存区并运行测试
python3 scripts/check-staged-changes.py \
  --test-command 'python3 -m unittest discover -s tests -p "test_*.py"'
```

## 集成方式

仓库的 `.githooks/pre-commit` 已调用基础检查。启用版本化 hooks：

```bash
git config core.hooksPath .githooks
```

由于不同项目的测试命令不同，默认 hook 不擅自运行测试；项目可将 `--test-command` 加入自己的 hook。Skill 要求的“测试通过后提交”仍需由项目配置或人工流程保证。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 暂存区检查和可选测试通过 |
| 1 | 空白检查或测试失败 |
| 2 | 参数错误或 Git 命令执行失败 |
