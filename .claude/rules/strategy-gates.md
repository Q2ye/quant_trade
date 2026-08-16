---
paths: "quant_server/modules/strategy/**/*.py"
---

# 策略开发质量门

> 通用检查见 `audit.md`，后端深度检查见 `audit-backend.md`，**策略全流程深度审计见 `audit-strategy.md`**（六大维度 + 四大模块拆分 + 边界全覆盖 + 交付六步结构）。
> 本规则仅在策略文件变更时加载，作为快速检查清单。完整审计请执行 `audit-strategy.md`。

## 每次变更必须检查

- [ ] 策略代码变更后，DB `strategies.code` 是否同步更新？（策略运行时从 DB 加载代码）
- [ ] 新增参数是否在 `DEFAULT_PARAMS` 中声明？
- [ ] 新增因子是否已在 `factor_metadata` 表注册？
- [ ] 3 个月冒烟回测是否通过？（至少 1 笔交易、无 NaN、收益率 ∈ [-95%, +500%]）

## 禁止项（策略特定）

- **严禁** `shift(-1)`、`.iloc[i+1]`、`df[col].shift(-N)` — 未来数据泄露
- **严禁** 硬编码 Tushare Token、DB 密码、API key 等凭证
- **严禁** 在 `generate_signals()` 中执行网络请求 — 数据应预先存入 DB
- **严禁** 修改 `DEFAULT_PARAMS` 结构而不更新对应策略的 DB `params` 列

## 数据泄露检查（ML 策略）

- [ ] 训练集/验证集/测试集在时间轴上是否严格分离？（先 train → 后 val → 最后 test）
- [ ] 特征计算是否仅使用 `t` 时刻及之前的信息？
- [ ] 是否使用了未来基本面数据（财报实际发布日期 vs 报告期）？
