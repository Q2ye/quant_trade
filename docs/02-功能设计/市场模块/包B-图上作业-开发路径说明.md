# 包 B｜图上作业层 · 前端开发路径说明（阶段 1）

> **上位文档**：`看盘能力扩展设计方案.md`（终稿）§五-B、§六、§八
> **规范**：`.claude/rules/frontend.md` 阶段 1 ｜ `audit.md` ｜ `audit-backend.md`
> **日期**：2026-09-23 ｜ **状态**：待确认（确认后进入阶段 2 编码）
> **开工前置**：**无** —— 本包不依赖 regime 口径 / 组合组状态 / `signals.reason` 语义等任何未决项

---

## 一、范围与结论

**做什么**：把仓库里**已建好但零接线**的绘图地基接上 UI 与持久化。
**不做什么**：不改 `LightweightKLine` 的渲染与同步逻辑、不改现有 9 个 Market 页面既有区块、不做统计断言出口（终稿 §2.3）。

**结论：本包可在阶段 1 确认后立即编码。** 但有 **3 项交互决策**与 **1 项色板新增**需你先定（§七）。

---

## 二、涉及文件

### 2.1 新增

| 文件 | 说明 |
|:---|:---|
| `quant_web/src/components/market/ChartDrawingToolbar.vue` | 工具条：趋势线 / 水平线 / 垂直线 / 文本 / 删除 / 清空；props `active` `count` `disabled`；emits `select` `delete` `clear` |
| `quant_web/src/composables/useChartDrawings.ts` | 统一编排 4 类工具的绘制状态 + 增删改 + 持久化读写（趋势线复用 `useTrendLineDraw`，另三类为单击落点） |
| `quant_web/src/components/charts/chart-palette.ts` | **canvas 专用色板常量**（见 §七-4）。canvas 无法解析 `var(--x)`，`design-tokens.ts` 全部是 `"var(--color-*, #hex)"` 形态 → 绘图原语不能直接引用，必须有一处 hex 常量集中定义 |

### 2.2 修改

| 文件 | 行号 | 改动 | 风险 |
|:---|:---|:---|:---|
| `components/charts/LightweightKLine.vue` | `:493` `defineExpose` | **仅新增** `getDrawTarget(): { chart, series, container }`（喂给 `activate()`） | ⚠️ 共享组件，4 处使用（StockDetail / ETFMarket / IndexDetail / TradeRecordChart）→ **只加不改**，`props` 默认值与现有 `drawings` 同步逻辑（`:411` `:458-461`）一律不动 |
| `views/DataCenter/Market/StockDetail.vue` | `:622` KLine 处；`:623` `:key="kPeriod"` | 卡片头部挂工具条；新增 `drawings` ref 并 `:drawings="drawings"`；接入 `useChartDrawings` | ⚠️ **`:key="kPeriod"` 会导致周期切换时组件销毁重建** → 绘制目标失效，须重绑定（见 §九-1） |
| `api/market.ts` | `:331`/`:338` 自选股范式旁 | 新增 `getChartAnnotations(tsCode)` / `saveChartAnnotations(tsCode, list)`（**不吞异常**，四态需要） | 低 |
| `composables/useTrendLineDraw.ts` | `:14`/`:204` | **修 2 处缺陷**（§九-2 Esc 失效、§九-3 无完成信号）—— 实施中新发现其 `DrawState` 缺"已完成"态 | 中（原方案未列此文件，见 §十一-D4） |
| `modules/market/handlers.py` | `:189`/`:220` 自选股范式旁 | 新增 `do_get_chart_annotations` / `do_save_chart_annotations` | 低（复用同款 JSONB 机制，但**该机制本身有缺陷**，见 §十一-D2） |
| `api/routers/market_router.py` | `:340`/`:349` 自选股路由旁 | 新增 `GET`/`PUT /market/user/chart-annotations` | 低 |

### 2.3 阶段 L4 才动（本包延伸，不在首批）

| 文件 | 行号 |
|:---|:---|
| `views/DataCenter/Market/ETFMarket.vue` | `:331` |
| `views/DataCenter/Market/IndexDetail.vue` | `:145` |

> **不在规划内、一律不动**：`styles/`、`naive-theme.ts`、`primitives/*.ts`（原语实现完整，零改动）、其余 6 个 Market 页面、`TradeRecordChart.vue`。

---

## 三、跨模块影响

| 维度 | 结论 |
|:---|:---|
| `core/` / `shared/` | **不涉及** —— 故无需列受影响模块 |
| 后端模块 | 仅 `modules/market`（handlers）+ `api/routers`（路由注册），**不新增表、不新增数据源** |
| 共享前端组件 | `LightweightKLine.vue` 被 4 处引用 → **只做 additive 修改**（新增 `defineExpose` 成员），不改 props 契约与默认值 → 其余 3 处零感知 |
| 全局样式 | **不碰** `styles/` 与 `naive-theme.ts` |
| 数据层 | 复用 `user_preferences.display_settings` JSONB（与自选股同款机制，**单源**） |

---

## 四、数据契约

### 4.1 存储形态

```jsonc
// user_preferences.display_settings.chart_annotations
{
  "chart_annotations": {
    "600519.SH": [
      {
        "id": "tl-1758600000000-1",
        "type": "trendLine",          // trendLine | horizontalLine | verticalLine | annotationLabel
        "period": "daily",            // daily | weekly | monthly  ← 必须带（见 §九-1）
        "startTime": "2026-09-01",    // 归一化为 'YYYY-MM-DD'
        "endTime": "2026-09-15",
        "startPrice": 1680.5,
        "endPrice": 1725.0,
        "lineColor": "#FF9800",       // 取自 chart-palette.ts
        "lineWidth": 2,
        "lineStyle": 0,
        "extendLeft": false,
        "extendRight": true
      }
    ]
  }
}
```

### 4.2 三条硬约束

1. **时间一律归一化为 `'YYYY-MM-DD'` 字符串**
   `chart.timeScale().coordinateToTime()` 在 lightweight-charts 中可能返回 `BusinessDay` 对象（`{year,month,day}`）→ 直接 `JSON.stringify` 会把对象存进库。写入前必须归一化。
   > 依据：`primitives/types.ts:2` 明写「所有位置信息只存储时间戳和价格，**绝不存储像素坐标**」；`SignalMarker.time` 已是 `'YYYY-MM-DD'` 先例（`LightweightKLine.vue:34`）。
2. **渲染时按 `period` 过滤** —— 只渲染当前周期的标注，避免日/周/月互相污染。
3. **上限（后端强制）**：单标的最多 **200** 条、最多 **50** 个标的；超限返回 409 + 明确文案。依据 `audit-backend.md`「JSON 字段不超限」。

### 4.3 数据流（单源追踪）

```
画线 → useChartDrawings（内存 list）
     → PUT /market/user/chart-annotations {ts_code, annotations}
     → do_save_chart_annotations：读 display_settings → 覆盖 chart_annotations[ts_code]
       （INSERT ... ON CONFLICT (user_id) DO UPDATE，同 do_save_watchlist:236-242）
     → GET 回读 → 按 period 过滤 → new XPrimitive(data) → :drawings
```

写入/读取各只有一个位置，**无双写、无多源合并**。

---

## 五、四层实施计划

| 层 | 内容 | 产出 | 可独立验证 |
|:--|:---|:---|:---|
| **L1** | 后端持久化契约 | `handlers.py` 2 函数 + `market_router.py` 2 端点 + 上限校验 | `curl` PUT→GET 往返一致；超限 409 |
| **L2** | **趋势线先打通**（单页最小闭环） | `LightweightKLine` 新增 `getDrawTarget()`；`ChartDrawingToolbar.vue`（仅趋势线按钮）；`useChartDrawings`（趋势线路径）；`StockDetail` 接线 | 画一条趋势线 → 刷新 → 仍在 |
| **L3** | 补齐四类工具 + 编辑操作 + 状态覆盖 | 水平线 / 垂直线 / 文本；删除 / 清空；四态（§六）；`chart-palette.ts` | 四类工具各画一条，全部可持久化；Error 有重试 |
| **L4** | 扩展到 ETF / 指数 | `ETFMarket.vue:331`、`IndexDetail.vue:145` 挂工具条 | 三页行为一致 |

> **L2 独立可用**：若 L3/L4 需延后，L2 本身已是完整闭环（画→存→读→渲染）。

---

## 六、状态覆盖（四态 + 边界态）

| 状态 | 工具条 | 画布 |
|:---|:---|:---|
| Loading | 按钮禁用（`disabled`） | 沿用容器 `n-skeleton`（`LightweightKLine.vue:516`） |
| Empty | 启用；`count=0` | 空画布，无提示（绘图入口即提示） |
| **Error + 重试** | **保存失败 → `n-message.error` + 保留本地 list 不丢**；读取失败 → toast + 可继续画（降级为本地态） | 沿用容器 `n-result`（`:517`） |
| Data | 显示 `count` | 渲染当前周期标注 |
| **非交易时段** | **只读**（禁用绘制，仍可查看已存标注） | 只读 |
| 周期切换 | 重新绑定绘制目标（§九-1） | 按新周期过滤重渲染 |

---

## 七、需你先定的 4 项

| # | 事项 | 选项 | 建议 |
|:--|:---|:---|:---|
| 1 | **绘制交互模型** | A. 选一次工具画一条，画完自动回 idle ｜ B. 连续绘制（画完保持激活） | **A** —— 与 TradingView 默认一致，误触少 |
| 2 | **删除交互** | A. 点击已画线选中 → 显示删除按钮 ｜ B. 橡皮擦模式 ｜ C. 侧栏列表删除 | **A**（B/C 留 P1） |
| 3 | **持久化范围与上限** | 按 `ts_code` 存、`period` 字段隔离周期；上限 200 条/标的、50 标的 | **接受**（可调） |
| 4 | **新增 `chart-palette.ts`** | canvas 吃不了 `var(--x)`（`design-tokens.ts` 全是 `"var(--color-*, #hex)"`），绘图色必须有一处 hex 常量 | **同意新增**，且本包只**新增引用**、**不批量清理**存量硬编码（避免顺手重构） |

---

## 八、验证方案

| # | 项 | 命令 / 方法 |
|:--|:---|:---|
| 1 | 类型 | `npx vue-tsc --noEmit`（无新增错误） |
| 2 | 构建 | `pnpm build` 通过 |
| 3 | 单测 | `pnpm test:unit` 不新增失败 |
| 4 | **持久化** | 画线 → 刷新页面 → 标注仍在 |
| 5 | **周期隔离** | 日 K 画线 → 切周 K → **不出现** → 切回日 K → 仍在 |
| 6 | **Esc 回归**（§九-2） | Esc 取消后**能继续画**（当前代码不能） |
| 7 | **无限滚动** | 下拉加载更多历史后，标注**不漂移**（时间锚定，非像素） |
| 8 | 三态 | 断网保存 → 有错误提示且本地不丢；非交易日 → 只读 |
| 9 | 共享组件回归 | ETF / 指数 / TradeRecordChart 页面**零变化** |
| 10 | N 边界 | 页面**无任何统计断言出口**（终稿 §2.3） |

---

## 九、已知缺陷（本包必须修 —— 均属"接线"范围，非顺手重构）

### 9.1 `:key="kPeriod"` 导致周期切换重挂载

`StockDetail.vue:623` `<LightweightKLine :key="kPeriod">` → 切周期时组件销毁重建，`chart`/`series`/`container` **全部失效**。
→ `useChartDrawings` 须在 `onMounted` / 周期变更后**重新 `getDrawTarget()` 并重绑定**；工具条须在切周期时回到 idle。**不重绑定 = 切一次周期绘图就静默失效。**

### 9.2 `useTrendLineDraw.cancel()` 使 Esc 之后无法再画（真实缺陷）

`useTrendLineDraw.ts:204-208` `cancel()` 调 `resetInternal()`，而 `:220-223` 会 `removeEventListener` 掉容器的 mousedown，随后 `:207` 却把 `state` 置回 `'drawing'`。
→ **Esc 后 state 说 drawing、监听已移除 → 后续点击无反应**（静默失效）。
→ 修法：`cancel()` 改为重新绑定监听（或统一走 `deactivate()` 后由工具条重新 `activate()`）。**本包不修则验收项 6 必挂。**

### 9.3 成功画完后状态停在 `preview`，需父组件显式消费

`useTrendLineDraw.ts:174-182` 成功后不 `resetInternal()`，注释自承「父组件应在收到数据后调用 `deactivate()`」；而 `consumePreview()`（`:211`）内部 `deactivate()` → `state='idle'`，**下一条线必须重新 `activate()`**。
→ 与 §七-1 的交互模型选择强耦合：选 A 则工具条在每次落笔后重新 `activate()`；选 B 则在 `consumePreview()` 后立即 `activate()`。

### 9.4 时间类型未经归一化

`coordinateToTime()` 可能返回 `BusinessDay` 对象（§4.2-1）。**不修则存进去的是对象，回读渲染位置可能错位。**

---

## 十、风险与明确不做

**风险**

| 风险 | 应对 |
|:---|:---|
| 改共享组件 `LightweightKLine` 影响另 3 处 | 只 `defineExpose` 新增成员；改完须验证另 3 页零变化（验收 9） |
| 标注体量增长撑大 `display_settings` | 上限 200×50（§4.2-3），后端强制 |
| 存量硬编码色散落 | 本包**只新增**集中常量，不批量改存量（避免超范围） |

**明确不做（本包外）**

- 拖拽微调端点（`TrendLinePrimitive.updateData` 已在，留 P1）
- 跨周期共享标注（周期隔离，见 §4.2-2）
- 标注的检索/统计出口（**属包 E，须登记台账** —— 终稿 §五-B N 边界）
- 清理存量 `#ef5350`/`#26a69a` 硬编码

---

## 十一、实施记录（2026-09-23 · 阶段 2 完成）

### 11.1 验证结果（可复跑）

| # | 项 | 结果 |
|:--|:---|:---|
| 1 | `npx vue-tsc --noEmit` | **零新增错误**（余 10 条全在未触碰文件：`api/trade.ts` / `EquityCurveChart.vue` / `DrawdownAreaChart.vue` / `primitives/*.ts` 的 `@ts-expect-error` 等，经 `git status` 逐文件确认既有） |
| 2 | `pnpm build` | ✓ 通过（26.5s） |
| 3 | `pnpm test:unit` | ✓ 3 文件 / 20 用例全通过 |
| 4 | 后端全量 `pytest -q`（回归门） | ✓ **377 passed / 66 skipped / 0 failed / 0 errors**（记录基线 276/66/0/0） |
| 5 | 路由注册 | ✓ `GET`/`PUT /user/chart-annotations` 已注册（37 条路由） |
| 6 | **持久化闭环（真实 DB）** | ✓ **17 项断言全通过** —— 脚本 `quant_server/scripts/_diag/_pkgB_annotation_roundtrip.py`（dev 库，备份→测试→还原并断言逐键一致） |
| 7 | **运行时挂载回归**（§11.5 新增） | ✓ `tests/unit/useChartDrawings.spec.ts` 11 用例；**已用反向实验证明有牙**（把 bug 放回 → 复现原错误） |

> ⚠️ **本轮暴露的验证盲区**：第 1–6 项**全部通过**，但页面**仍然打不开**（§11.5 的 TDZ）。
> 原因：`vue-tsc` 的"声明前使用"检查只在**词法上直接引用**时触发（如 `watch([klineData, …])`），
> 而 `applyCursor()` 是在**函数体内**引用 `_container` → TS 放行，只有真正 mount 才暴露。
> **结论：类型检查 + 构建 + 后端测试都替代不了"真的挂载一次"。**

闭环测试覆盖：往返一致 / BusinessDay 对象归一化 / `period` 保留 / 中文不损坏 / **合并不覆盖原有 `display_settings` 键** / 按标的分仓 / 空列表清除 / **5 类校验拦截** / 校验失败后原数据完好（写入失败兜底） / 还原无残留。

> ⚠️ **未能验证的部分（修订）**：
> - **已补上**：`useChartDrawings` 的 setup 期运行时安全（§11.5，mount 级回归测试）
> - **仍未验证**：**视觉与手感** —— 画线是否跟手、命中测试的 6px 容差是否合适、色板在深色背景下的观感、
>   以及 §八 验收项 4–9 的全部行为路径（画线→刷新仍在 / 周期隔离 / Esc 后能续画 / 加载更多不漂移）。
>   这些**必须真人在页面上过一遍**，本轮无自动化手段（浏览器驱动未接入）。
> - 另：**真实 lightweight-charts 实例**下的坐标换算（`coordinateToTime` 反算）在测试里用的是 stub，
>   故"像素↔时间/价格"的正确性**未验证**。

### 11.2 实施偏差（4 项，需你知悉）

| # | 偏差 | 说明 |
|:--|:---|:---|
| **D1** | **§六「非交易时段 → 只读」未实施** —— 改为**始终可编辑** | 该条是我起草时的判断，实施时发现方向错了：**复盘标注恰恰发生在盘后/周末**，锁只读会把工具锁在唯一用得上的时候。`canEdit` 保留为可插拔入口，若你仍要该策略，改 1 行即可 |
| **D2** | **`user_preferences.id` 是 NOT NULL 且无默认值** —— 省略 `id` 的 INSERT 必然失败 | 见 §11.3。我的代码已修（显式传 `uuid4()`）。**同行发现既有 `do_save_watchlist` 有同一缺陷**，未擅自修改 |
| **D3** | 标注 id **必须**以 `draw-` 开头（新增强约束） | `LightweightKLine.syncDrawings:414-419` 只 detach `draw-` 前缀的 id，却用数据自带 id 挂载 → 不带头缀则**删除的线会留在画布上**。前端生成 + **后端强校验**（缺前缀 → 409）双向兜住 |
| **D4** | 原方案 §2.2 修改文件表**遗漏** `composables/useTrendLineDraw.ts` | 其实施中发现：该状态机 `DrawState` 只有 `idle/drawing/preview`，**画完与拖拽中同为 `preview`，父组件无法判完成**（§九-3 只提到"需显式消费"，未指出无完成信号）。已加 `done` 态作为唯一完成信号，并按 §九-2 修 Esc 重新武装 |
| **D5** | `useChartDrawings` 改为**自己持有 `target`** 并导出 `refreshTarget()` | L4 时三页需要同一套"取目标 + 有限重试（≤10 帧）"，抽入 composable 避免三份复制；`watch(chartRef)` 自动覆盖 `:key`/`v-if` 重建 |

### 11.3 ⚠️ 同行发现的既有缺陷（不在本包范围，等你决定）

**`do_save_watchlist`（`modules/market/handlers.py:236-242`）的 INSERT 写不进去 → 自选股保存静默失效。**

证据（事务内回滚，未留痕）：

```
真实 user_id = cd2f4a88-...（该行已存在 → 走 ON CONFLICT DO UPDATE）
省略 id 的写法 → NotNullViolationError: null value in column "id" ...
带 id 的写法   → 未报错 ✓
```

根因：`user_preferences.id VARCHAR(36) PRIMARY KEY` **NOT NULL 且无默认值**，而 PostgreSQL 在 **ON CONFLICT 解析之前**就校验 NOT NULL → 该写法对**任何**行都失败，与"行是否已存在"无关。

**为什么一直没被发现**：前端 `api/market.ts:338-344` 的 `saveWatchlist` 是 `.catch(() => false)` —— **错误被完全吞掉**，用户侧表现为"点了保存没反应"。

修法与 D2 相同（1 行）：`INSERT INTO user_preferences (id, user_id, display_settings) VALUES (uuid4, ...)`。
**我未改** —— 该函数不在本包规划内。请指示：① 顺手修（1 行）② 另开条目 ③ 保持现状。

### 11.5 运行时缺陷（页面打不开）+ 新增防线

**现象**（个股详情页）：

```
useChartDrawings.ts:393 Uncaught (in promise) ReferenceError:
  Cannot access '_container' before initialization
    at applyCursor (useChartDrawings.ts:393:5)
    at watch.immediate (useChartDrawings.ts:361:7)
    at useChartDrawings (useChartDrawings.ts:352:3)
```

**根因**：`watch([activeTool, target, canEdit], …, { immediate: true })` 在 **setup 期间**就调用
`applyCursor()`，而 `applyCursor` 读的 `let _container` 声明在该 watch **之后** → TDZ。
**修法**：把 6 个 `let` 句柄声明**上移到任何 watcher 之前**（`target` 声明之后）。

**顺带修掉的隐患（同一次排查发现）**：`target` 原用 `ref()` → Vue 对 `{ chart, series, container }`
做**深层响应式代理**。这三者是第三方类实例（lightweight-charts 的 `IChartApi`/`ISeriesApi` + DOM 节点），
用 `ref()` 对只读句柄毫无收益，且库一旦改用 `#private` 字段，代理会抛
"Cannot read private member"。已改 **`shallowRef`**。
> 诚实标注：**这不是活的运行时 bug** —— 实测 lightweight-charts v5.2.0 产物**未使用 `#private`**
> （唯一 `#` 命中是 CSS `--fill:#131722`），故代理此前只是隐患，非故障。

**新增防线**：`tests/unit/useChartDrawings.spec.ts`（11 用例，`@vue/test-utils` + jsdom）
—— 用 `mount()` 真跑一次 setup，兜住"必须挂载才暴露"这一整类错误。
**有牙证明**（反向实验）：把 `let` 声明挪回 watcher 之后 → 11 用例中 6 个失败，报错文本与用户所报**完全一致**：

```
× mount 时 setup 不抛错（TDZ 回归） → ReferenceError: Cannot access '_co…
× selectTool 选中 / 同工具再点一次取消 → Cannot access '_container' before initialization
```

### 11.4 本包产出文件

**新增**：`components/charts/chart-palette.ts` · `components/market/ChartDrawingToolbar.vue` · `composables/useChartDrawings.ts` · `tests/unit/useChartDrawings.spec.ts` · `scripts/_diag/_pkgB_annotation_roundtrip.py`（验证资产，可复跑）
**修改**：`LightweightKLine.vue`（仅新增 `getDrawTarget` 到 `defineExpose`）· `useTrendLineDraw.ts`（2 处缺陷）· `StockDetail.vue` · `ETFMarket.vue` · `IndexDetail.vue` · `api/market.ts` · `modules/market/handlers.py` · `api/routers/market_router.py`
**未触碰**：`primitives/*.ts` 实现 · `syncDrawings` 同步逻辑 · `styles/` · `naive-theme.ts` · 其余 6 个 Market 页面 · `TradeRecordChart.vue`
