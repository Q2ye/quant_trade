# quant_server/scripts/ —— 长期资产目录

> **这里的脚本不是临时产物，全部纳入 git 管理**（`_` 前缀与 `_bak/` 除外，见下）。
> 一次性诊断脚本**不要提交**：放 `scripts/_diag/`，用完即弃。
> 交付流程见 `docs/06-标准规范/00_交付流程总纲.md`。

## 1. 目录清单（`quality/` `backtest/` `data/` `ops/` 共 40 个 `.py`，2026-11-08 实测）

| 目录 | 数量 | 内容 | 常用入口 |
|:---|--:|:---|:---|
| `quality/` | 5 | **质量门与巡检**（收工必跑） | `check_all.py` · `check_delivery.py` · `audit_strategy.py` · `sync_strategy_code.py` · `permutation_test.py` |
| `backtest/` | 6 | 回测与冒烟 | `backtest_high_vol_momentum.py` · `backtest_cross_market_momentum.py` · `rolling_start_analysis.py` |
| `data/` | 21 | 数据回填与播种 | `backfill_*.py`（15）· `seed_*.py`（3）· `cleanup_stale_quality_checks.py` · `sync_margin_hsgt.py` · `sync_numeric_precision_to_ddl.py` |
| `ops/` | 8 | 运维杂项 | `archive_logs.py`（已挂日终）· `merge_accounts.py` · `password_utils.py` |

> ⚠️ `backtest/backtest_etf_bottom.py` 与 `backtest_small_cap.py` **不加载策略类**（独立重实现）。
> 改 `etf/bottom_strategy.py` / `microcap/microcap_strategy.py` 后跑它们，**全绿也验证不了策略代码** —— 用 pytest 对应测试文件。

## 2. 命名与保留规则

| 规则 | 说明 |
|:---|:---|
| `_` 前缀 | 一次性诊断脚本（`_diag/` `_probe_*` `_verify_*` 等），**不提交** |
| `_bak/` | 同步前的自动备份（已忽略），可随时删；保留最新快照即可 |
| `_diag/` | 一次性诊断脚本目录（已忽略、不提交）；保留/归档规则见 §5 |
| `quality/` 下的入口脚本 | **受保护，勿删**：被 hook / 文档 / `check_all` 调用（见 §3） |
| `__init__.py` | 仅让 `scripts` 可被 `-c` 导入做测试，不承载逻辑 |

## 3. 受保护脚本（改动前先查引用）

| 脚本 | 作用 | 引用位置（改了要同步） |
|:---|:---|:---|
| `quality/check_all.py` | 收工检查：⓿ 交付预检 + 三道门（质量 / 回归 / 范围） | `AGENTS.md`「开发流程」、`CLAUDE.md`、`04/05/06` 标准 |
| `quality/check_delivery.py` | 交付流程状态机（S1–S5）：`new / next / status / check / scope / use` | `AGENTS.md`、`00_交付流程总纲.md` §五、`docs/09-交付记录/INDEX.md`、`check_all.py` |
| `quality/audit_strategy.py` | 策略准入 G1 机检（未来函数 / 凭证 / 除零 / 参数越界） | `check_all.py`、`.claude/settings.json` hook |
| `quality/sync_strategy_code.py` | 磁盘 ↔ DB `strategies.code` 一致性巡检 / 同步 | `CLAUDE.md`「策略开发」 |

## 4. 常用命令（CWD = `quant_server/`）

```bash
# 交付流程：我在哪一步 / 开新单 / 校验产物
.venv/Scripts/python.exe scripts/quality/check_delivery.py next
.venv/Scripts/python.exe scripts/quality/check_delivery.py new market-temp --tier T1
.venv/Scripts/python.exe scripts/quality/check_delivery.py check

# 收工：声明范围 → 跑门
.venv/Scripts/python.exe scripts/quality/check_delivery.py scope --apply
.venv/Scripts/python.exe scripts/quality/check_all.py

# 回归
.venv/Scripts/python.exe -m pytest -q
```

## 5. 一次性脚本清理记录（2026-11-08）

| 对象 | 处理 | 取回方式 |
|:---|:---|:---|
| `_diag/` 98 个临时探针（`_probe_*` / `_diag_*` / `_check_*` / `_verify_*` / `_live_*` / `_sop_*` / `_replay_*` 等） | 打包后删除 | 解压 `_diag/_archive_20261108.zip` |
| `_diag/` 保留 79 个 | 45 个被 `docs/**/*.md` 或其他 `_diag` 脚本引用 + 34 个研究复现脚本（`_ir_*` / `_ne_*` / `_r0~r4_*` 等） | — |
| `_bak/` 23 个旧快照 | 打包后删除 | 解压 `_bak/_archive_20261108.zip` |
| `_bak/` 保留 | 最新一次同步快照 `*_20261028_225617_db_before.py` | — |

> `scripts/_diag/` 已加入 `.gitignore`（与 `_bak/` 同处理），`git status` 不再变脏。
> `_diag/` 里的研究脚本是该结论的可复现证据，**不要因为"没用"批量删除**；删除前先跑本文件 §2 的引用检查。
