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

## 边界

脚本只检查暂存区和可选测试命令，不安装 Git Hook，不判断分支名、提交信息或文件是否属于当前需求。

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 暂存区检查和可选测试通过 |
| 1 | 空白检查或测试失败 |
| 2 | 参数错误或 Git 命令执行失败 |
