# 交付记录索引（REQ 台账）

> 每次 **T1–T3** 变更一个目录，T0 不建（commit 带 `[T0]`）。流程见 `docs/06-标准规范/00_交付流程总纲.md`。
> 机器读 `.active`（单行 REQ 编号）；人读下表。**已交付的 REQ 不删**，作为可复现的验收底稿。

| 编号 | 标题 | 档 | 阶段 | 开始 | 交付 | 主要 commit |
|:---|:---|:--:|:--:|:---|:---|:---|
| REQ-20261108-db-env-isolation | 开发/生产数据隔离（单库多 schema） | T2 | 已交付 | 2026-11-08 | 2026-11-08 | |
| REQ-20261108-script-dsn-unification | 脚本数据库连接统一（去除硬编码 DSN） | T1 | 已交付 | 2026-11-08 | 2026-11-08 | |

## 用法

```bash
cd quant_server

# 1) 开新单（复制 5 份模板并设为当前）
.venv/Scripts/python.exe scripts/quality/check_delivery.py new market-temp --tier T1 --title 市场页温度计改版

# 2) 每次开工先问我在哪一步
.venv/Scripts/python.exe scripts/quality/check_delivery.py next

# 3) 结构校验（占位未清 / 缺章节 → FAIL）
.venv/Scripts/python.exe scripts/quality/check_delivery.py check

# 4) 由 03-任务.md 推出范围白名单并发给 check_all
.venv/Scripts/python.exe scripts/quality/check_delivery.py scope --apply

# 5) 切换当前单 / 看全部
.venv/Scripts/python.exe scripts/quality/check_delivery.py use REQ-20261108-market-temp
.venv/Scripts/python.exe scripts/quality/check_delivery.py status
```

## 阶段与文件对应

| 阶段 | 文件 | 缺失含义 |
|:--:|:---|:---|
| S1 需求澄清 | `01-需求.md` | 还没想清验收 |
| S2 设计 | `02-设计.md` | 还没定结构 |
| S3 任务拆分 | `03-任务.md` | 还没拆成可交付单元（**未声明范围不得改代码**） |
| S4 功能测试验证 | `04-验证.md` | 还没对照 AC 实测 |
| S5 代码评审 | `05-评审.md` | 还没独立复核（作者不自审） |
