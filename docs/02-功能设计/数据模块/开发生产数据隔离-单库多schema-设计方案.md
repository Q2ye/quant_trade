# 开发/生产数据隔离 · 单库多 schema 设计方案

> **版本**：v1 ｜ **日期**：2026-11-08
> **定位**：解决"dev 与 prod 各存一份行情、结论不可迁移、账户数据可能被误写"的问题。
> **结论**：一个数据库 + `public` / `dev` 两个 schema + 两个非超管角色（`quant_prod` / `quant_dev`，可选只读 `quant_ro`）。不拆微服务。
> **状态**：2026-11-08 已实施（REQ-20261108-db-env-isolation，S1–S5 全绿）；实测 dev 74 表 / 85 FK / 25 触发器 / 5 超表。

---

## §0 一句话方案

```
quant_signals（唯一数据库）
├─ public  ← 行情/财务/因子/元数据（共享，dev 只读）
│           + 生产应用状态（账户/策略/订单/持仓，仅 prod 可写）
└─ dev     ← 开发应用状态（策略/回测/交易/账户副本，仅 dev 可写）
```

- **一份行情数据**：dev 与 prod 读同一份 `public` 行情。
- **应用状态隔离**：dev 写 `dev.strategies` / `dev.orders` / `dev.accounts`，prod 写 `public.*`。
- **不影响生产账户的前提**：dev 必须用非超管角色 `quant_dev`，且对 `public` 无写权限。

---

## §1 现状与问题（实测）

| 项 | dev | prod | 问题 |
|:---|:---|:---|:---|
| 数据库大小 | 50 GB | 28 GB | 两份全量 |
| `stock_daily` 最新 | 2026-09-18 | 2026-11-06 | dev 停更 7 周 |
| `factor_data` | 4,805 万行 / 102 因子 | 2.9 万行 / 42 因子 | dev 有历史，prod 几乎为空 |
| `stock_limit_list` | 有 | **无** | schema 漂移 |
| 连接角色 | `postgres` 超管 | `postgres` 超管 | **无权限隔离** |

账户类脚本硬编码超管凭证（违反安全红线）：

| 文件 | 行 | 内容 |
|:---|:---|:---|
| `scripts/ops/merge_accounts.py` | 20-21 | `user="postgres", password="123456", database="quant_signals_dev"` |
| `scripts/ops/setup_composite.py` | 19-22 | 同上 |
| `scripts/ops/add_strategy_to_composite.py` | 23-25 | 同上 |

**这三项不先修，"不影响生产账户"只是口头承诺。**

---

## §2 设计原则

1. **一份数据**：行情/财务/因子只有一份，在 `public`。
2. **状态隔离**：应用状态按环境隔离，dev 不碰 `public` 的应用表。
3. **默认拒绝**：`quant_dev` 对 `public` 只有 SELECT，只能写 `dev`；`quant_prod` 拥有 `public` 完整写权限（含日终同步）。
4. **零代码分层改动**：模型没有 `schema=`、无 `create_all`，用 `search_path` 即可。
5. **可回滚**：`DROP SCHEMA dev CASCADE` 不影响 `public`；Phase 0 只改配置，不改数据。
6. **账户优先**：账户域整组克隆，FK 闭环，启动断言。

---

## §3 目标架构

```
   prod 进程 ────────▶ quant_prod     public: 读写（含日终同步 + 账户）
   (uvicorn + 日终)                       │
                                          ▼
                          ┌───────────────────────────────┐
                          │  quant_signals（唯一数据库）  │
                          │  ├─ public（行情 + 生产状态） │
                          │  └─ dev（开发状态）           │
                          └───────────────▲───────────────┘
                                          │
   dev 进程 ─────────▶ quant_dev      public: 只读；dev: 读写
   (uvicorn/脚本)

   （可选）研究/看板 ▶ quant_ro      public: 只读，事务只读
   测试 ──────────────▶ quant_signals_test（DDL + fixtures）
```

### 连接矩阵

| 角色 | `search_path` | `public` | `dev` | 用途 |
|:---|:---|:---|:---|:---|
| `quant_prod` | `public` | **读写**（含日终同步、账户、策略、交易） | 无权限 | 生产服务 |
| `quant_dev` | `dev, public` | **只读** | 读写 | 开发服务/策略开发 |
| `quant_ro`（可选） | `public` | 只读（事务只读） | 无权限 | 研究/看板/外部工具 |
| `postgres` | — | 仅 DDL/运维 | 仅 DDL/运维 | **不进应用 DSN** |

---

## §4 数据域划分

### 4.1 市场数据域（`public`，dev 只读）

> 61 张（prod 现存 60 张；`stock_limit_list` 缺失属另一 REQ）。完整清单落 `data_contracts.py` 的 `MARKET_TABLES`。

```
stock_basic stock_company stock_daily stock_weekly stock_monthly
stock_adj_factor stock_adjusted_prices stock_daily_basic stock_daily_limit
stock_suspend_info stock_limit_list stock_moneyflow stock_moneyflow_hsgt
stock_st_list stock_st_risk stock_hsgt stock_minutes
stock_top10_holders stock_top10_float_holders stock_stk_holdernumber
stock_stk_holdertrade stock_pledge_stat stock_share_float stock_dividends
stock_forecasts stock_expresses stock_audit_opinions stock_business_incomes
stock_fina_indicators stock_forecast_pro stock_factor_daily stock_factor_pro_daily
etf_basic etf_daily etf_index etf_minute etf_shares fund_adj_factor
index_basic index_daily index_weekly index_weight index_dailybasic
index_sw_classify index_sw_member index_sw_daily index_factor_pro_daily
macro_cpi macro_ppi macro_gdp
margin factor_data market_state_daily panic_index trade_calendar
stk_managers stk_rewards financial_income financial_balance
financial_cashflow financial_disclosure_dates
```

### 4.2 应用状态域（`dev` 可写，`public` 仅 prod 可写）

> 其余 74 张，包含账户、策略、回测、交易、风控、分析、系统配置。

| 子域 | 表 |
|:---|:---|
| **账户** | `accounts` `account_transactions` `account_statements` `account_daily_performance` `cash_flows` `account_audit_logs` |
| **策略** | `strategies` `strategy_parameters` `strategy_versions` `strategy_runs` `strategy_templates` `strategy_daily_performance` `portfolio_strategies` |
| **交易** | `signals` `orders` `trades` `positions` `trade_instructions` `order_templates` `position_adjustments` `position_snapshots` `baskets` `basket_items` |
| **组合** | `composite_groups` `composite_account_snapshots` |
| **回测** | `backtest_tasks` `backtest_trades` `backtest_positions` `backtest_parameters` `backtest_scenarios` `backtest_comparisons` `backtest_equity_curves` `backtest_resource_usage` |
| **风控** | `risk_rules` `risk_events` |
| **分析/研究** | `analysis_reports` `analysis_tasks` `analysis_templates` `analysis_benchmarks` `report_generation_logs` `factor_research` `feature_sets` `model_trainings` `factor_definitions` |
| **监控/工作流** | `monitor_alerts` `monitor_tasks` `monitor_thresholds` `alert_templates` `alert_delivery_logs` `workflow_tasks` `workflow_logs` |
| **系统/身份** | `sys_users` `sys_roles` `sys_user_roles` `sys_permissions` `sys_scheduled_tasks` `scheduled_tasks` `system_configs` `system_health_metrics` `user_preferences` `blacklists` `license_keys` `file_attachments` `trade_fees` |
| **数据运维** | `data_sync_tasks` `data_quality_checks` `data_quality_issues` `data_fix_records` |
| **日志/审计** | `audit_logs` `sys_audit_logs` `sys_operation_logs` `system_logs` `api_usage_logs` `sys_notifications` |

### 4.3 例外规则

| 表 | 规则 |
|:---|:---|
| `factor_data`（4,805 万行） | **不克隆**；dev 只读 `public.factor_data`。新因子写 `dev.factor_data_staging`，验证后再提升 |
| `signals` / `account_daily_performance` / `backtest_equity_curves` / `risk_events` / `strategy_daily_performance` | 是 TimescaleDB 超表；克隆结构后必须 `create_hypertable` 重建 |
| `trade_fees` | 放应用域；dev 可改（已确认），不做只读 |
| `stock_basic` / `etf_basic` | 市场域只读；`dev.basket_items` 的 FK 指向 `public.stock_basic` 是允许的 |

---

## §5 角色与权限

> 由 `postgres`（DDL owner）执行；应用 DSN 永不使用 `postgres`。

```sql
-- 0) 公共 schema 收紧
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- 1) 生产应用（含日终同步、账户、策略、交易）
--    生产本来就要跑同步，所以 public 全量读写；核心边界是 dev 不能写 public
CREATE ROLE quant_prod LOGIN PASSWORD :'prod_pw';
ALTER ROLE quant_prod SET search_path = public;
GRANT CONNECT ON DATABASE quant_signals TO quant_prod;
GRANT USAGE ON SCHEMA public TO quant_prod;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO quant_prod;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO quant_prod;

-- 2) 开发应用：dev 可写，public 只读
CREATE ROLE quant_dev LOGIN PASSWORD :'dev_pw';
ALTER ROLE quant_dev SET search_path = dev, public;
GRANT CONNECT ON DATABASE quant_signals TO quant_dev;
GRANT USAGE ON SCHEMA dev, public TO quant_dev;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO quant_dev;             -- 只读
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dev TO quant_dev;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dev TO quant_dev;

-- 3) 研究/看板（可选角色；不需要外部只读入口时可以省略）
CREATE ROLE quant_ro LOGIN PASSWORD :'ro_pw';
ALTER ROLE quant_ro SET search_path = public;
ALTER ROLE quant_ro SET default_transaction_read_only = on;
GRANT CONNECT ON DATABASE quant_signals TO quant_ro;
GRANT USAGE ON SCHEMA public TO quant_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO quant_ro;

-- 4) 未来表自动授权（DDL 由 postgres 执行）
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO quant_prod;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT ON TABLES TO quant_dev, quant_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA dev
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO quant_dev;
```

**禁止**：
- `GRANT ... ON SCHEMA public TO quant_dev` 带写权限；
- `quant_dev` 成为 `postgres` 成员或表 owner；
- 应用 DSN 出现 `postgres`。

---

## §6 dev schema 初始化

### 6.1 脚本

新增 `scripts/ops/init_dev_schema.py`：

```
python scripts/ops/init_dev_schema.py --dry-run     # 打印将执行的 DDL
python scripts/ops/init_dev_schema.py --apply       # 建 schema + 表 + 触发器 + 种子
python scripts/ops/init_dev_schema.py --apply --recreate   # 先 DROP SCHEMA dev CASCADE
```

### 6.2 建表规则

1. `CREATE SCHEMA IF NOT EXISTS dev;`
2. 取 `DEV_APP_TABLES = 全部表 - MARKET_TABLES`（74 张）。
3. **按 FK 依赖拓扑排序**（`sys_users`/`sys_roles` → `accounts` → `strategies` → `orders`/`positions` → `backtest_*`）。
4. 每张表：
   ```sql
   SET search_path = dev, public;
   CREATE TABLE dev.<t> (LIKE public.<t> INCLUDING ALL);
   ```
5. **触发器重建**（`LIKE` 不复制触发器）：
   ```sql
   CREATE TRIGGER update_<t>_modtime BEFORE UPDATE ON dev.<t>
   FOR EACH ROW EXECUTE FUNCTION public.update_modified_column();
   ```
   仅对原表有触发器的表执行（见 `create_table.sql:4001-4025`）。
6. **超表重建**（时间列已实测，写死前请以 `timescaledb_information.dimensions` 为准）：

   | 表 | 时间列 |
   |:---|:---|
   | `signals` | `signal_time` |
   | `account_daily_performance` | `trade_date` |
   | `backtest_equity_curves` | `trade_date` |
   | `risk_events` | `created_at` |
   | `strategy_daily_performance` | `trade_date` |

   ```sql
   SELECT create_hypertable('dev.signals', 'signal_time', if_not_exists => TRUE);
   SELECT create_hypertable('dev.risk_events', 'created_at', if_not_exists => TRUE);
   ```
7. **FK 闭环校验**：
   ```sql
   -- 期望为空：dev 的 FK 不应指向 public 的应用表
   SELECT conrelid::regclass AS child, confrelid::regclass AS parent
   FROM pg_constraint
   WHERE contype = 'f'
     AND connamespace = 'dev'::regnamespace
     AND confrelid::regclass::text IN (
       'public.accounts','public.strategies','public.orders',
       'public.positions','public.trades','public.signals','public.sys_users');
   ```

### 6.3 种子数据（不复制生产业务数据）

| 表 | 种子 |
|:---|:---|
| `dev.sys_users` | 1 个 dev 用户（独立口令） |
| `dev.sys_roles` / `sys_user_roles` | 1 个 admin 角色 |
| `dev.accounts` | 1 个 dev 账户（独立 UUID，余额自定） |
| `dev.trade_fees` | 从 `public.trade_fees` 复制（22 行） |
| `dev.risk_rules` | 从 `public.risk_rules` 复制 |
| `dev.factor_definitions` | 从 `public.factor_definitions` 复制，允许 dev 新增 |
| `dev.strategy_templates` | 从 `public.strategy_templates` 复制 |
| `dev.system_configs` | 从 `public.system_configs` 复制 |
| **不复制** | `strategies` / `signals` / `orders` / `trades` / `positions` / `accounts` 的业务数据 |

> 如需用生产策略做实验：用 `promote_strategy.py` 的 `--copy-from public --strategy-id X`，复制成 dev 副本，不直接改生产。

---

## §7 schema 漂移同步

### 7.1 版本表

```sql
CREATE TABLE IF NOT EXISTS schema_versions (
    version     VARCHAR(32) PRIMARY KEY,
    applied_at  TIMESTAMPTZ DEFAULT now(),
    checksum    VARCHAR(64),
    note        TEXT
);
```

### 7.2 同步脚本

`scripts/ops/sync_dev_schema.py`：

1. 比对 `information_schema.columns`（`public.x` vs `dev.x`）：
   - 缺表 → 提示 `init_dev_schema.py`；
   - 缺列 → `ALTER TABLE dev.x ADD COLUMN ...`；
   - 类型/默认值差异 → 输出 diff，人工确认；
2. 默认 dry-run；`--apply` 才执行；
3. 同步后校验 `schema_versions` 与 `create_table.sql` 的 checksum。

### 7.3 启动检查

服务启动时（dev 与 prod 都做）：

```sql
SELECT current_user,
       current_setting('search_path'),
       has_table_privilege(current_user, 'public.accounts', 'INSERT');
```

| 环境 | 期望 |
|:---|:---|
| dev | `quant_dev`, `dev, public`, `false` |
| prod | `quant_prod`, `public`, `true` |

任一不符 → **拒绝启动**并打印期望值。

---

## §8 应用配置改造

### 8.1 `.env`

```env
# 生产（唯一写 public 的角色）
PROD_DB_HOST=localhost
PROD_DB_PORT=5432
PROD_DB_USER=quant_prod
PROD_DB_PASSWORD=...
PROD_DB_NAME=quant_signals

# 开发（同库，dev schema 可写）
DB_DEV_HOST=localhost
DB_DEV_PORT=5432
DB_DEV_USER=quant_dev
DB_DEV_PASSWORD=...
DB_DEV_NAME=quant_signals

# 研究/看板（只读）
DB_RO_HOST=localhost
DB_RO_PORT=5432
DB_RO_USER=quant_ro
DB_RO_PASSWORD=...
DB_RO_NAME=quant_signals
```

> 现状 `DB_USER=postgres` / `PROD_DB_USER=postgres` 必须移除。

### 8.2 配置读取

`shared/config/config_manager.py` 已支持：
- development → `DB_DEV_*`（当前 `.env` 没定义，回退到 `DB_*`）；
- production → `PROD_DB_*`。

改造点：
1. 新增 `DB_RO_*` 与只读 session 工厂；
2. 启动时执行 §7.3 检查；
3. 日志打印 `current_user` + `search_path`（不打印口令）。

### 8.3 psycopg2 路径

`bottom_strategy._pg_conn_cfg()` 已走 `settings.DATABASE`（`bottom_strategy.py:28-47`），会继承 `ENVIRONMENT` 的配置；**不要新增任何硬编码 DSN**。

### 8.4 只读研究入口

研究/看板/回测分析用 `quant_ro`：
- `default_transaction_read_only = on`，从数据库层阻断写；
- 适合 notebook、临时 SQL、前端只读接口。

### 8.5 同步任务归属

日终同步继续跑在 prod 进程里，使用 `quant_prod`（它有 `public` 全量写权限）：

- `modules/data/__init__.py` 的 `_task_sync_daily` 不变；
- `scripts/data/backfill_*.py` 用 `quant_prod`，且默认 `--dry-run`；
- **dev 不注册 data 模块的行情同步/派生任务**（`sync_daily`/`coverage_validate`/`market_state_update`/`etf_factor` 只在 prod 进程执行）；account/strategy/system 的日终任务可在 dev 运行（写 dev schema，属开发工作流）。

> 如果未来把同步拆成独立 worker，再单独引入 `quant_ingest`；本期不做，避免多一个角色和 session 工厂。

---

## §9 账户数据专项安全

### 9.1 克隆清单（必须整组）

`accounts` `account_transactions` `account_statements` `account_daily_performance`
`cash_flows` `account_audit_logs` `position_adjustments` `position_snapshots`
`positions` `orders` `trades` `signals` `trade_instructions` `order_templates`
`baskets` `basket_items` `composite_groups` `composite_account_snapshots`
`portfolio_strategies` `risk_rules` `risk_events` `strategy_daily_performance`
`backtest_*`

### 9.2 四道账户专用锁

| 锁 | 做法 |
|:---|:---|
| 权限锁 | `quant_dev` 对 `public.accounts`/`public.positions`/`public.orders`/`public.trades` 无 INSERT/UPDATE/DELETE |
| FK 锁 | 账户域整组克隆，FK 闭环；校验查询见 §6.2 |
| 启动锁 | §7.3 断言 `has_table_privilege('public.accounts','INSERT') = false` |
| 脚本锁 | 账户变更脚本（`merge_accounts`/`setup_composite`/`add_strategy_to_composite`）改为读配置 + `--env` 确认 + `current_user != 'postgres'` 断言 |

### 9.3 级联方向

- `public.accounts` 删除会级联 `public.account_transactions`/`cash_flows` 等（生产内部行为，不变）；
- dev 子表 FK 指向 `dev.accounts` 后，生产删除不会影响 dev；
- 校验：dev 中不存在指向 `public.accounts` 的 FK。

---

## §10 硬编码脚本治理

### 10.1 三个必须改的脚本

| 文件 | 改法 |
|:---|:---|
| `scripts/ops/merge_accounts.py` | 删除 `DB=dict(...)`；改 `settings.DATABASE`；加 `--env` + 确认串；加 `current_user` 断言 |
| `scripts/ops/setup_composite.py` | 同上；同时移除硬编码 `strategy_id`（改为参数） |
| `scripts/ops/add_strategy_to_composite.py` | 同上 |

### 10.2 统一模板

```python
# 伪代码
from shared.config.config_manager import config
assert config.settings.ENVIRONMENT.value == args.env, "环境不匹配"
db = config.settings.DATABASE
assert db.USER != "postgres", "禁止用超管运行应用脚本"
conn = psycopg2.connect(host=db.HOST, port=db.PORT, user=db.USER,
                        password=db.PASSWORD, database=db.NAME)
```

### 10.3 守卫

- `.claude/settings.json` 的 PostToolUse 凭证扫描扩展到 `scripts/**`；
- 新增检查：`grep -rn 'password\s*=\s*["\']' scripts/` 必须为空；
- 账户变更类脚本在 `prod` 下要求交互确认（或 `--yes-i-mean-prod`）。

---

## §11 工作流：策略开发 → 回测验证 → 生产执行

### 11.1 五个阶段

| 阶段 | 环境/角色 | 写 | 读 | 门 |
|:---|:---|:---|:---|:---|
| S1 开发 | dev / `quant_dev` | `dev.strategies` `dev.strategy_parameters` | `public` 行情 | 代码可编译 |
| S2 回测 | dev / `quant_dev` | `dev.backtest_*` | `public` 行情/因子 | **数据新鲜度门** |
| S3 验证 | dev / `quant_dev` | `dev.analysis_*` `dev.factor_research` | `dev.backtest_*` | 过拟合/滚动起始日/审计 |
| S4 提升 | ops / `quant_prod` | `public.strategies` `strategy_versions` `strategy_promotions` | dev 回测证据 | 审计 + 人工确认 |
| S5 实盘 | prod / `quant_prod` | `public.signals/orders/trades/positions/accounts` | `public` 行情 | 人工确认成交 |

### 11.2 S1 开发

- 磁盘改代码 → `scripts/quality/sync_strategy_code.py --env dev` → 写 `dev.strategies.code`；
- 策略状态 `draft`；
- 新策略生成新 UUID；**从生产复制的策略保留同 ID**，便于后续提升时更新同一逻辑策略。

### 11.3 S2 回测（含数据新鲜度门）

- 读 `public.stock_daily` / `public.etf_daily` / `public.factor_data`；
- 写 `dev.backtest_tasks/trades/positions/equity_curves`；
- **门 1：数据新鲜度**（必须，否则拒绝出结论）：
  - `public.stock_daily.max(trade_date)` 与交易日历差 ≤1 个交易日；
  - 回测涉及的表（`factor_data`、`stock_daily_basic`、`stock_moneyflow` 等）覆盖度达标；
  - 把 `data_as_of` 写入 `backtest_tasks.parameters`，结论必须能追溯到数据版本；
- **门 2：回测只写 dev**；prod 不跑回测。

> 这条门直接针对当前问题：dev 库停在 2026-09-18，而 prod 已到 2026-11-06；没有这道门，dev 回测会拿 7 周前的数据得出结论。

### 11.4 S3 验证

- 过拟合检验（`docs/06-标准规范/05`）、滚动起始日（`04`）、策略审计（`strategy-auditor`）；
- 产出：`backtest_task_id` + 指标 + 结论；
- 结论落 `dev.analysis_reports` / `dev.factor_research`，随提升一起带过去。

### 11.5 S4 提升

```bash
scripts/ops/promote_strategy.py --strategy-id X --from dev --to public [--dry-run]
```

职责：
1. 校验策略代码可编译（`py_compile` / `exec`）；
2. 校验 `dev.backtest_tasks` 有通过的验证记录（可配置强制）；
3. 复制 `strategies` / `strategy_parameters`；
4. **新增** `strategy_versions`（不覆盖旧版本，保留回滚能力）；
5. 写 `public.strategy_promotions` 审计；
6. **状态保持 `draft`/`stopped`，绝不自动 `running`**；
7. **不复制账户/持仓/资金/组合配置**——资金分配在 prod 人工设置。

### 11.6 S5 实盘

- 人工在 prod 前端把策略置 `running`（或走 G0–G5 准入流程）；
- prod strategy_manager 读 `public.strategies` → 写 `public.signals`；
- 半自动：人工券商下单 → 系统确认成交 → 写 `public.orders`/`trades`/`positions`；
- 日终结算写 `public.accounts`；
- 回滚：从 `strategy_versions` 恢复上一版本，`strategy_promotions` 保留审计。

### 11.7 提升审计表（本方案新增 1 张）

```sql
CREATE TABLE strategy_promotions (
    id                  VARCHAR(36) PRIMARY KEY,
    dev_strategy_id     VARCHAR(36) NOT NULL,
    prod_strategy_id    VARCHAR(36) NOT NULL,
    strategy_version_id VARCHAR(36),
    backtest_task_id    VARCHAR(36),
    metrics             JSONB,            -- 收益/回撤/夏普/滚动起始日分布
    operator            VARCHAR(64),
    git_commit          VARCHAR(64),
    promoted_at         TIMESTAMPTZ DEFAULT now(),
    note                TEXT
);
```

> 若后续新增本表，应用域从 74 张变为 **75 张**。

### 11.8 从生产复制策略到 dev（已确认需要）

```bash
scripts/ops/promote_strategy.py --copy-from public --strategy-id X --to dev
```

- 复制 `strategies` / `strategy_parameters` / `strategy_versions` 到 dev；
- **保留同 ID**（后续提升时更新同一逻辑策略）；
- 不复制账户/持仓/信号；
- dev 副本状态强制 `draft`。

### 11.9 账户与资金

| 阶段 | 账户数据 |
|:---|:---|
| S1–S3 | 用 `dev.accounts`（模拟资金），可自由改 |
| S4 | **不提升账户数据** |
| S5 | 才动 `public.accounts`，必须 `quant_prod` + 业务 API/脚本 |
| 资金分配 | Composite / CapitalAllocator 在 prod 人工配置，不从 dev 复制 |

---

## §12 迁移步骤

### Phase 0：角色与配置（不碰数据，1 天）

1. 创建 `quant_prod` / `quant_dev`（`quant_ro` 可选）；
2. 改 `.env`（移除 `postgres` 应用 DSN）；
3. 改 3 个硬编码脚本；
4. 加启动检查（§7.3）；
5. 加同机资源限制：
   ```sql
   ALTER ROLE quant_prod CONNECTION LIMIT 50;
   ALTER ROLE quant_dev  CONNECTION LIMIT 20;
   -- dev 回测重查询限时，避免拖垮 prod
   ALTER ROLE quant_dev SET statement_timeout = '300s';
   ```
6. 验证：prod 用 `quant_prod` 正常启动且日终同步成功；dev 用 `quant_dev` 只能读 public。

**回滚**：DSN 改回原值即可，数据未动。

### Phase 1：dev schema（1 天）

1. `init_dev_schema.py --apply`；
2. dev 切换到 `DB_DEV_*`；
3. 停用 dev 的日终任务（`register_daily_task` 只在 prod 注册）；
4. 迁移/演练在 `dev` schema 内完成；
5. 验证：dev 写策略只落 `dev.strategies`；prod 的 `public.strategies` 行数不变。

**回滚**：`DROP SCHEMA dev CASCADE`；dev DSN 切回 prod 只读。

### Phase 2：退役 `quant_signals_dev`（已确认可直接退役，但必须先迁移因子历史）

> ⚠️ **直接 DROP 会丢数据**：dev 的 `factor_data` 有 **4,805 万行 / 102 个因子 / 2005 起**，
> prod 只有 **2.9 万行 / 42 个因子 / 2026-09-21 起**。必须先迁移。

1. **因子历史迁移（前置）**：
   - 对比 `dev.factor_data` 与 `public.factor_data` 的 `factor_code` 集合；
   - 把 prod 缺失的因子码 + 历史区间，用 `COPY (SELECT ...)` 迁到 `public.factor_data`
     （不要用 `pg_dump -n public`，超表会导出空数据且不报错）；
   - 校验：每个迁移因子的 `min/max(trade_date)` 与 dev 一致，行数对照；
   - 迁移完成前**不 DROP**。
2. 导出 dev 独有的实验结果：`pg_dump --schema=dev`（备份 `strategies`/`backtest_*`/`analysis_*`）；
3. 清理 `signals_backup_20260825` 等历史备份表；
4. 确认无代码/脚本引用 `quant_signals_dev` 后 `DROP DATABASE`。

**验收**：`public.factor_data` 的因子数、历史起点、行数与迁移前 dev 对照一致。

### Phase 3：物理隔离（可选）

- 需要跨机：加物理 standby，`quant_ro` 连备库；
- 需要危险迁移演练：`COPY (SELECT ...)` 恢复 `sandbox` 库，用完 drop。

> ⚠️ 超表克隆/备份不能用 `pg_dump -n public`（会导出空数据且不报错）；用 `COPY (SELECT ...)`。

---

## §13 验收清单

### 13.1 SQL 断言

```sql
-- dev 连接下必须全部通过
SELECT current_user = 'quant_dev';
SELECT current_setting('search_path') LIKE 'dev%';
SELECT NOT has_table_privilege('quant_dev', 'public.accounts', 'INSERT');
SELECT NOT has_table_privilege('quant_dev', 'public.positions', 'UPDATE');
SELECT NOT has_table_privilege('quant_dev', 'public.orders', 'DELETE');

-- dev schema 存在且应用表齐全
SELECT count(*) >= 70 FROM pg_tables WHERE schemaname = 'dev';

-- dev FK 不指向 public 应用表（期望 0 行）
SELECT conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'dev'::regnamespace
  AND confrelid::regclass::text LIKE 'public.%'
  AND confrelid::regclass::text NOT IN ('public.stock_basic','public.etf_basic');

-- prod 连接下必须通过：账户和行情都能写（生产要跑同步）
SELECT current_user = 'quant_prod';
SELECT has_table_privilege('quant_prod', 'public.accounts', 'UPDATE');    -- true
SELECT has_table_privilege('quant_prod', 'public.orders', 'INSERT');      -- true
SELECT has_table_privilege('quant_prod', 'public.stock_daily', 'INSERT'); -- true
```

### 13.2 行为测试

| 测试 | 期望 |
|:---|:---|
| dev 插入一条 `strategies` | 只出现在 `dev.strategies` |
| 同一条 SQL 在 prod 查 `strategies` | 看不到 dev 行 |
| dev 尝试 `INSERT INTO public.orders` | `permission denied` |
| dev 尝试 `UPDATE public.accounts` | `permission denied` |
| dev 跑回测 | 读 public 行情成功，写 dev 回测表成功 |
| dev 读取 `public.factor_data` | 成功（只读） |
| dev 执行 `INSERT INTO public.factor_data` | `permission denied` |
| **prod 通过 API/脚本改 `public.accounts`** | 成功（`quant_prod`） |
| **prod 日终同步写 `public.stock_daily`** | 成功（`quant_prod`） |
| **提升策略 dev → prod** | `public.strategies` 增加；`strategy_promotions` 有记录；状态为 `draft`/`stopped`，不是 `running` |
| **从 prod 复制策略到 dev** | dev 有副本，`public.strategies` 不变 |
| **回测新鲜度门：把 `stock_daily` 最新日改到 30 天前** | 回测拒绝出结论 |

### 13.3 脚本测试

- 3 个账户脚本在 dev 下运行 → 只改 `dev.accounts`；
- 带 `--env prod` 运行 → 要求确认，且 `current_user = quant_prod`；
- 用 `postgres` 运行 → 直接拒绝。

---

## §14 风险与不做的事

### 风险

| 风险 | 缓解 |
|:---|:---|
| `search_path` 被会话覆盖 | 启动断言 + 不给 public 写权限（双保险） |
| 误用 prod DSN | 启动断言 `current_user`；`.env` 键名分离 |
| FK 指向 public 应用表 | 整组克隆 + §6.2 校验 |
| `LIKE` 不复制触发器 | 脚本显式重建 |
| 超表克隆成普通表 | `create_hypertable` 重建 |
| dev 回测压垮 prod | 只读查询可接受；压力大时加 standby |
| 账户脚本误跑 | `--env` + 确认 + 非超管断言 |
| **退役 dev 丢因子历史** | Phase 2 前置：先迁 dev 独有因子到 prod，再 DROP |

### 不做

- 不拆数据微服务（见上一轮结论：224 个文件直连仓储，收益不抵成本）；
- 不用 `env` 列 / RLS（要改 50+ 表、所有查询加过滤）；
- 不把 `factor_data` 克隆到 dev（4,805 万行）；但退役前要把 dev 独有因子**迁移到 prod**（§12 Phase 2）；
- 不让 dev 跑同步/回填；
- 不让应用使用 `postgres` 超管。

---

## §15 已确认决策与剩余项

### 15.1 已确认（2026-11-08）

| # | 决策 | 落地 |
|:--|:---|:---|
| 1 | dev 与 prod **同机** | 走本方案；暂不加物理 standby |
| 2 | **需要**从生产复制策略到 dev | `promote_strategy.py --copy-from public`，保留同 ID，状态强制 `draft` |
| 3 | **允许** dev 新增 `factor_definitions` | 放应用域，dev 可写；新因子值写 `dev.factor_data_staging` |
| 4 | **允许** dev 改 `trade_fees` | 从市场域移到应用域，dev 可写 |
| 5 | `quant_signals_dev` **可直接退役** | **前置：先迁移 dev 独有的 4,805 万行因子历史到 prod**（§12 Phase 2） |

### 15.2 仍需确认

1. **因子历史迁移范围**：全部 102 个因子，还是只迁当前策略用到的子集？（建议全部，起点不可逆）
2. **提升时是否强制要求回测证据**：`promote_strategy.py` 是否必须有通过的 `backtest_task_id`？
3. **前端环境标识**：dev 前端是否加显式 "DEV" 横幅并禁用生产操作入口？
4. **prod 是否允许跑回测**：建议禁止；如允许，需单独的资源限制。
