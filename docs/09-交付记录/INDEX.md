# 交付记录索引（REQ 台账）

> 每次 **T1–T3** 变更一个目录，T0 不建（commit 带 `[T0]`）。流程见 `docs/06-标准规范/00_交付流程总纲.md`。
> 机器读 `.active`（单行 REQ 编号）；人读下表。**已交付的 REQ 不删**，作为可复现的验收底稿。

| 编号 | 标题 | 档 | 阶段 | 开始 | 交付 | 主要 commit |
|:---|:---|:--:|:--:|:---|:---|:---|
| REQ-20261108-db-env-isolation | 开发/生产数据隔离（单库多 schema） | T2 | 已交付 | 2026-11-08 | 2026-11-08 | 57028b8 |
| REQ-20261108-script-dsn-unification | 脚本数据库连接统一（去除硬编码 DSN） | T1 | 已交付 | 2026-11-08 | 2026-11-08 | 0449ee9 |
| REQ-20261108-daily-sync-time-config | 日终流水线触发时间可配置 | T2 | 已交付 | 2026-11-08 | 2026-11-08 | daa9dba |
| REQ-20261108-daily-data-base | 日频数据底座补全（56 张表） | T2 | 已交付 | 2026-11-08 | 2026-11-08 | 9151a09…0adc22c |
| REQ-20261114-etf-premium-gate | ETF 折溢价门（跨市场避险） | T3 | **已关闭（前提证伪）** | 2026-11-14 | — | — |
| REQ-20261112-whipsaw | 震荡市反复鞭打：出场均线去抖 | T3 | **已关闭（判决实验未通过）** | 2026-11-12 | — | — |
| REQ-20261114-regime-debounce | 走弱期 regime 去抖（跨市场避险） | T3 | S1 待审批 | 2026-11-14 | — | — |
| REQ-20261114-highvol-moneyflow-select | 高波动选股：资金流因子 | T3 | S3 待审批 | 2026-11-14 | — | — |
| REQ-20261122-dev-list-prod-strategies | dev 环境只读展示生产策略 | T1 | **已关闭（前提不成立）** | 2026-11-22 | — | — |

## 用法

```bash
cd quant_server

# 1) 开新单（复制 5 份模板并设为当前）
.venv/Scripts/python.exe scripts/quality/check_delivery.py new market-temp --tier T1 --title 市场页温度计改版

# 2) 每次开工先问我在哪一步
.venv/Scripts/python.exe scripts/quality/check_delivery.py next

# 3) 机检（占位未清 / 缺章节 / AC 缺→ / 路径不存在 → FAIL）
.venv/Scripts/python.exe scripts/quality/check_delivery.py check

# 4) 机检通过后：出复核包 → 你审批（不审批不能进下一段）
.venv/Scripts/python.exe scripts/quality/check_delivery.py review
.venv/Scripts/python.exe scripts/quality/check_delivery.py approve S1 --yes --note "看过，OK"

# 5) 由 03-任务.md 推出范围白名单并发给 check_all
.venv/Scripts/python.exe scripts/quality/check_delivery.py scope --apply

# 6) 切换当前单 / 看全部
.venv/Scripts/python.exe scripts/quality/check_delivery.py use REQ-20261108-market-temp
.venv/Scripts/python.exe scripts/quality/check_delivery.py status
```

## 阶段与文件对应

> 每阶段两步：**机检 PASS** → **`approve <Sx>` 审批**；审批记录写在 `meta.json.approvals`，缺审批停在本段。
> 只能顺序审批（S2 未批不能批 S3）；机检不过不许审批；`approve` 必须带 `--yes`。

| 阶段 | 文件 | 缺失含义 |
|:--:|:---|:---|
| S1 需求澄清 | `01-需求.md` | 还没想清验收 |
| S2 设计 | `02-设计.md` | 还没定结构 |
| S3 任务拆分 | `03-任务.md` | 还没拆成可交付单元（**未声明范围不得改代码**） |
| S4 功能测试验证 | `04-验证.md` | 还没对照 AC 实测 |
| S5 代码评审 | `05-评审.md` | 还没独立复核（作者不自审） |
