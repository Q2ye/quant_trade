# 备份说明（不入 git）

本次迁移前的 dev 三表备份（`dev_strategies_*.csv` 等）已移出 git：

- 原因：含完整策略源码与用户 UUID，体积约 1.5 万行，评审 F9 指出仓库膨胀与外泄风险。
- 现状：备份文件已删除；回滚依赖 `ALTER TABLE dev.<x>_devbak_20261122 RENAME TO <x>`（表本身仍在 dev schema，数据未丢）。
