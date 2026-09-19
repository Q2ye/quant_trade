---
paths: "quant_server/modules/strategy/**/*.py"
---

# 策略开发质量门

> 通用检查见 `audit.md`，后端深度检查见 `audit-backend.md`，**策略全流程深度审计见 `audit-strategy.md`**（六大维度 + 四大模块拆分 + 边界全覆盖 + 交付六步结构）。
> **上线准入判定见 `docs/06-标准规范/06_策略实盘准入标准.md`**（六道门 G0–G5 + 分层 20 项）。
> 本规则仅在策略文件变更时加载，作为快速检查清单。完整审计请执行 `audit-strategy.md`。
>
> ⚠️ **表名/类名/参数一律以代码与 DDL 为准**（`docs/sql/create_table.sql`、策略文件本身）。
> 2026-09-15 修正：此前版本写的 `factor_metadata` 表**不存在**（真名 `factor_definitions`）、`generate_signals()` 方法**不存在**（真名 `on_bar` / `on_bar_batch_end`），均已修正。

## 每次变更必须检查

- [ ] 策略代码变更后，DB `strategies.code` 是否同步更新？**全部副本**（多实例 + `strategy_templates.code_template`）都更新了吗？
- [ ] 改参数默认值时，`strategy_parameters` 覆盖是否同步？（JSON 列会盖掉 `DEFAULT_PARAMS`）
- [ ] 新增参数是否在 `DEFAULT_PARAMS` 中声明？
- [ ] 新增因子是否已在 **`factor_definitions`** 表注册？（⚠️ 不是 `factor_metadata`）
- [ ] 3 个月冒烟回测是否通过？**（全项目统一口径：至少 1 笔交易、无 NaN、收益率 ∈ [−95%, +500%]）**
- [ ] **回归门：全量 `pytest` 是否通过？**（新增失败 = 阻断；详见下节）

## 回归门（2026-09-15 新增）

> **这是本项目唯一的"机器判断"门 —— 单人开发下唯一能替代第二双眼睛的东西。**

- [ ] 改动前先跑一次 `cd quant_server && .venv/Scripts/python.exe -m pytest -q` 记录基线
- [ ] 改动后再跑一次，**新增的 failed/error 必须清零才能提交**
- [ ] 不得以「既有失败」为由跳过 —— 既有失败应逐条登记（见下）
- [ ] 策略文件变更必须有对应 pytest 用例（新增策略无用例 = 警告）

**已知既有失败基线** —— 修完一项划掉一项：

| 时点 | failed | errors | passed | skipped | 耗时 |
|:---|---:|---:|---:|---:|---:|
| 2026-09-15 清理前 | 18 | 31 | 235 | 35 | 5.08s |
| 2026-09-15 清理后 | **0** | **0** | 253 | 66 | 2.87s |
| 2026-09-15 止损统一后（+2 个新测试文件，23 用例） | **0** | **0** | **276** | 66 | 2.92s |

**清理明细（全部已清）**

| 类别 | 文件 | 数量 | 根因与处置 |
|:---|:---|---:|:---|
| ERROR | `test_industry_rotation.py` | 21 | 策略已删除 → 补模块级 `pytest.mark.skip` |
| ERROR | `test_event_engine.py` | 6 | 构造签名过时（`EngineConfigEntity` + `config.config`）→ 重写；**并修掉引擎 2 个真缺陷**（§5-12/5-13） |
| ERROR | `test_data/test_services.py` | 4 | 缺 pytest-asyncio → fixture 改同步 + **用例测的是 stub，价值为零** → 类级 skip |
| FAILED | `test_strategy_manager.py` | 6 | 注册表抽为 `StrategyRegistry` 单例（`_strategy_registry`→`registry`，Dict→List）+ 注册时机移到 `_on_initialize` + `StrategyContext` 三个字段变必填 → 逐项对齐 |
| FAILED | `test_high_vol_momentum.py` | 3 | 2 个属已删 v9.0 原型（`set_injected_regime`）+ 1 个 v9.0 版本断言 → 前者 skip、后者校正为 `v7.1` |
| FAILED | `test_panic_bottom_strategy.py` | 4 | 相对「ATR 化重构」过时（需灌 ≥15 根 bar 才有 ATR）→ **skip + 写明重写要点**（卫星池已暂停，本次仅登记） |
| FAILED | `test_industry_scoring.py` | 1 | 断言过时（V4 起 C3 已移除，向量 11 非 12）→ 校正 |
| FAILED | `test_data/test_simple.py` | 2 | 由 `tests/conftest.py` 的 async 钩子修复（见下） |
| FAILED | `test_review_fixes.py` | 1 | 助手用废弃 API `get_event_loop().run_until_complete` → 改 `asyncio.run`（顺序依赖型失败） |
| FAILED | `test_signal_engine_reuse.py` | 1 | `FakeRepo` 缺 `get_by_stock` 桩（引擎新增「新信号覆盖旧 pending」逻辑）→ 补桩 |

> **根因共识**：`pytest-asyncio` **不在依赖中**，而 4 个测试文件用 `@pytest.mark.asyncio` + `async def`
> → 这些用例**从未真正执行**。已在 `tests/conftest.py` 增加标准库 asyncio 钩子（零新依赖），
> 使 `async def` 用例可运行，并保留 `asyncio.run` 写法兼容。

> ⚠️ **`CLAUDE.md` 曾称 industry_rotation 相关测试「已 `pytest.mark.skip`」—— 实测 skip 标记数为 0，实际是 21 个 ERROR。** 该表述已订正。

> ⚠️ **当前 66 个 skip 中有 4 个是「待重写」而非「已废弃」**：`test_panic_bottom_strategy.py` 的
> `TestStateMachine::test_full_sequence`、`TestStopProfitLoss` 三个 —— skip reason 里已写明重写要点。
> 另有 `test_data/test_services.py` 整类 skip（测的是 stub，建议直接删除）。

> ⚠️ **清理过程中发现 2 个真实产品缺陷**（非测试问题，已修 + 已登记 `docs/review/17` §5-12/5-13）：
> 1. **事件优先级被解读反**：`EventPriority`（IntEnum，越大越紧急）与 `PriorityLevel`（越小越紧急）两套尺度并存，归一化漏掉前者 → CRITICAL 排最后、LOW 排最前，且队列溢出保护的 CRITICAL 强插从未生效。
> 2. **类式订阅静默失效**：`BaseEvent.event_type` 是 property，对类取 `getattr` 得到 property 对象 → 订阅键变成 `'<property object at 0x...>'`，事件能入队、统计显示"已处理"，但永远匹配不到处理器且无任何报错。

## 禁止项（策略特定）

- **严禁** `shift(-1)`、`.iloc[i+1]`、`df[col].shift(-N)` — 未来数据泄露
- **严禁** 硬编码 Tushare Token、DB 密码、API key 等凭证（⚠️ 已知遗留：`etf/bottom_strategy.py:76-78`，待迁 `.env`；**新策略不得再出现**）
- **严禁** 在 `on_bar` / `on_bar_batch_end` 中执行网络请求 — 数据应预先存入 DB（⚠️ 非 `generate_signals()`，项目无此方法）
- **严禁** 修改 `DEFAULT_PARAMS` 结构而不更新 DB 中的代码副本
- **严禁** 不设止损的裸策略（止损参数用**正数** `stop_loss_pct ∈ (0,1)`；ATR 倍数式豁免）

## 数据泄露检查（ML 策略）

- [ ] 训练集/验证集/测试集在时间轴上是否严格分离？（先 train → 后 val → 最后 test）
- [ ] 特征计算是否仅使用 `t` 时刻及之前的信息？
- [ ] 是否使用了未来基本面数据（**必须按 `f_ann_date` 公告日对齐，禁止按报告期 `end_date` + 日历日 ffill** —— 后者可达 4 个月前视，见 `docs/review/17` §2-1）
