# 08 前端 quant_web 审查报告

> 审查基准日期：2026-08-14（只读审查，未修改任何业务代码；唯一写入为本报告文件）
> 审查文件清单：`quant_web/src/` 共 **291 个文件**：views/ 54、api/ 18、components/ 98（charts 10、common 16、market 12、strategy 19、trade 17、data 13、dashboard 4、editors 4、basket 1、three 1）、store/ 13、composables/ 19、router/ 3、types/ 41、utils/ 11（含 worker 2）、其余 12。
> 方法：核心链路（utils/request、router/guard、store 全部模块、api 全部封装、重点视图 Signal/TradeCenter/StrategyCenter/DataCenter）逐文件精读 + 全仓 grep 交叉验证引用关系；报告内所有"无引用/无消费"结论均经 grep 验证（仅命中自身定义），行号为实测。
> 重点精读文件：`utils/request.ts`、`router/{index,guard,routes}.ts`、`store/{index.ts,plugins/persistedstate.ts,modules/*.ts(11 个)}`、`api/{auth,signals,strategy,market,websocket,trade,index}.ts`、`views/Signal/{SignalConfirm,SignalMonitor}.vue`、`views/TradeCenter/{Workspace,Trading/TradingDashboard}.vue`、`views/DataCenter/Market/{MarketDashboard,StockScreener,StockDetail,ETFMarket}.vue`、`views/DataCenter/DataSync/DataSync.vue`、`views/StrategyCenter/{StrategyWorkspace,Backtest/BacktestWorkspace,Backtest/BacktestReport,FactorDashboard}.vue`、`views/Login.vue`、`views/Register.vue`、`views/Risk/*`、`views/System/Dashboard.vue`、`components/common/{AppSidebar,AppHeader,MainLayout 引用,StatCard,DashboardCard}.vue`、`components/trade/OrderForm.vue`、`components/charts/*`、`composables/{useWebSocket,useChartLifecycle,useBacktestPolling,useSyncTimer,useSyncEventHandler}.ts`、`plugins/echarts.ts`、`locales/index.ts`、`utils/{number,date,responseHandler,icons}.ts`、`vite.config.ts`、`package.json`。

## 1. 业界对比分析

### 1.1 总体评价：工程结构清晰，图表与轮询生命周期管理达到业界水准
- **组合式 API 使用成熟**：页面普遍使用 `<script setup lang="ts">`；图表公共逻辑抽为 `useChartLifecycle`（`composables/useChartLifecycle.ts:54-186`：ResizeObserver 自适应、`chart.remove()` 销毁、theme-change 事件重绘），配套 `useTimeCoordinate`/`usePrimitiveManager`；轮询抽为 `useBacktestPolling`（`composables/useBacktestPolling.ts:61-99,151,273`：自适应间隔 + 连续错误指数退避 + `onUnmounted` 自动停止），被 BacktestWorkspace/DataSync 复用。
- **lightweight-charts 生命周期处理优秀**：`useChartLifecycle.ts:100-118` 用 ResizeObserver 替代 window.resize 并注释了 `applyOptions` 不重绘 canvas 的坑；`ETFMarket.vue:118-185` 重建前先 `remove()`、卸载时销毁；`BacktestReport.vue:132` 对空数据用 `v-if` 守卫图表渲染。
- **ECharts 部分页面已按需注册**：`MarketDashboard.vue:28-33`、`MoneyFlow.vue:22-25` 等用 `echarts/core + use()` 摇树。
- **路由守卫分层合理**：authGuard → dataReadyGuard（预取 userInfo + system 初始数据）→ layoutGuard（`guard.ts:5-90`）。

### 1.2 与业界标准的主要差距（详见后续清单）

| 维度 | 现状 | 业界标准 | 差距 |
|---|---|---|---|
| 状态管理 | **Vuex 4**（`store/index.ts:1`），11 模块中 6 个无消费方；持久化用 npm vuex-persistedstate，自研插件废弃 | Pinia（类型友好、组合式） | 任务书按 Pinia 预期，实际为 Vuex；建议迁移或至少清理死模块 |
| 请求层 | 有集中拦截器与 401 处理（`utils/request.ts:60-134`），但**无 token 刷新、无重复请求取消、无失败重试**；`authApi.refreshToken` 存在但从未接入 | axios 刷新队列 + AbortController 竞态取消 | 中 |
| 打包体积 | `main.ts:9` **全量 `import * as echarts`**；`main.ts:17-129` **全量引入并全局注册约 80 个 Naive UI 组件**；另有 11 处视图级 `import * as echarts` | 按需引入 + 组件自动按需注册 | 大 |
| 巨型组件 | DataSync.vue ≈1627 行、MarketDashboard.vue 1329 行、Workspace.vue 1189 行、RiskManagement.vue 1086 行、StockDetail.vue 1008 行、IndexDetail.vue 963 行 | 单组件 <500 行，拆 composable/子组件 | 大 |
| API 分层 | 27 处视图**绕过 api/ 层直接 `request.get/post/put/delete`**（`Workspace.vue:76-81,527-591`、`StrategyList.vue:453-641`、`PerformanceHub.vue:185`、`Login.vue:107` 等） | 统一 api 层 + 类型化返回 | 中 |
| 格式化 | `utils/number.ts` 零消费，各组件重复实现 `formatPercent` 且语义不一（乘 100 与不乘并存） | 单一工具 + 单位契约 + 单测 | 中 |
| WebSocket | **两套互不兼容客户端**：`api/websocket.ts`（channel 订阅制）与 `composables/useWebSocket.ts`（event 制，且全部 commit 到不存在的 store 模块）；DataSync 订阅了 WS 却无人 connect | 单例 + 心跳 + 断线重连 + 统一消息路由 | 高 |

### 1.3 请求层细节对比
- 优点：`baseURL` 读环境变量、请求日志按环境裁剪（`request.ts:7-25`）、超时 120s（`:9`，适配回测长任务）、统一 Bearer 注入（`:40-49`）。
- 不足：① 401 处理只清 `localStorage` 不清 Vuex store（`:104-115`），且用 `window.location.href` 整页跳转丢失 SPA 状态；② 无 401 并发去重（多个请求同时 401 会弹多次、跳多次）；③ 全局 `message.error`（`:131`）与视图 catch 的 `message.error` 双提示并存；④ 无请求取消/竞态保护（详见 §3）。

### 1.4 组件化与复用
- 正面：SmartIcon（统一 Iconify 图标，被 30+ 页面复用）、StatCard/CodeDiff/TradeTable/DataCompletenessTable 等被多页复用；BacktestSubplots 被 3 个页面复用；Composables 提取方向正确。
- 反面：**死代码规模大**（详见 §2）：约 8 个视图、50+ 组件、6 个 store 模块、2 个 worker、多个 api/composable/工具文件无消费方；`components/common/DashboardCard.vue:45` 还残留指向不存在目录的 import（`../ui/StatusBadge.vue`），一旦被引用即构建失败——死代码不仅增维护成本，还是潜在构建炸弹。

### 1.5 状态管理与数据一致性
- 正面：`SignalMonitor.vue:114-129` 审核信号用乐观更新 + 失败回滚 + 具体错误提示；`SignalConfirm.vue:116-136` 确认/取消后立即 `fetchSignals()` 刷新（前后端闭环正确）；`Workspace.vue:70-80` 用 failedSources 数组逐源降级提示。
- 反面：风控告警 commit 进 layout store 后**无任何组件渲染**（`store/modules/risk.ts:312-323`）；`useWebSocket.ts` 全部 commit 到不存在的模块（§3.1）；store 与 localStorage 双 token 源不一致（§5.2）。

### 1.6 路由与权限
- 守卫只做 token 存在性校验，无 JWT 过期/角色权限校验（`guard.ts:10-26`）；`layoutGuard` 中 `window.dispatchEvent(new Event("resize"))`（`guard.ts:84-87`）是为旧式图表 resize 的遗留 hack，现图表已用 ResizeObserver，可移除。
- 路由表存在 8 条旧路径 redirect（`routes.ts:20-33`）与侧边栏 routeMap 间接匹配（`AppSidebar.vue:277-300`），导航链依赖 redirect 兜底，属可容忍的兼容层，但应随版本收敛。

### 1.7 前后端数据一致性专项
- **信号确认闭环正常**：`SignalConfirm.vue:116-136` 确认/取消成功后重新拉取列表；`SignalMonitor.vue:114-129` 采用乐观更新 + 失败回滚，是本项目可推广的范式。
- **风险闭环断裂**：`store/modules/risk.ts:312-323` 将告警 commit 进 layout store 后无人渲染（§3.15）；`useWebSocket.ts:114-119` 的 `ui/showAlert` 指向不存在的模块（§3.1），两条告警链路均未到达用户。
- **行情闭环断裂**：现役唯一 WS 通道（`Workspace.vue:25-28` 触发 useWebSocket）的 5 个消息 handler 全部 commit 到不存在的 store 模块，实时行情/信号/订单状态**不会反映到界面**（§3.1）。
- **同步闭环半通**：DataSync 依赖轮询（useBacktestPolling）+ 手动刷新兜底，WS 事件因无人 connect 永不到达（§3.2）；任务取消后 2s 轮询一次状态（`DataSync.vue:608-614`）属合理降级。
- **时区与格式统一性**：UTC 日期/时间截取出现在至少 3 处（§3.6、§5.9、§5.14），金额/百分比格式化各组件自实现、单位语义不一（§5.8），建议收敛为 dayjs + 统一 format 工具。

### 1.8 图表使用模式专项（ECharts / lightweight-charts）
| 模式 | 代表位置 | 评价 |
|---|---|---|
| lightweight-charts 生命周期（创建/销毁/resize） | `useChartLifecycle.ts:59-118`、`ETFMarket.vue:118-185` | 优秀：remove + ResizeObserver + 主题切换 |
| ECharts 手动实例 + 卸载销毁 | `ExecutionAnalysis.vue:226-339,481-487`（4 实例 dispose + resize 监听移除） | 良好 |
| ECharts 按需注册 | `MarketDashboard.vue:28-33`、`MoneyFlow.vue:22-25` 等（echarts/core + use()） | 良好 |
| ECharts 全量引入 | `main.ts:9` 全局 + 11 处视图级 `import * as echarts` | 差：摇树失效（§4.2） |
| vue-echarts 组件 | `MarketDashboard.vue:28,882,961`（autoresize） | 可接受，但与手动 echarts.init 混用风格不统一 |
| 图表空数据 | `BacktestReport.vue:132` `v-if="monthlyReturns.length > 0"`；`ETFMarket.vue:171-178` 空则 destroy | 良好；其余图表未逐一核验空数据处理（待确认） |
| 图标 hack | `ETFMarket.vue:134` `el.querySelector('a')?.remove()` 手动删 attribution logo | 应用 `attributionLogo:false` 选项（useChartLifecycle 已用）统一处理 |

## 2. 死代码清单

> 以下均为 grep 全量验证：除自身定义外无任何 import/路由/调用方。

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|---|---|---|---|
| `api/scenario.ts`（整文件） | API 封装 | 无任何消费方（grep 仅命中自身）；后端 run-scenario 由 `TemplateDetail.vue:511` 用裸 request 直连 | 删除；如需保留场景功能，收编进 backtest.ts 并让 TemplateDetail 走 api 层 |
| `api/index.ts`（整文件） | 桶文件 | 无 `from "@/api"` 引用 | 删除 |
| `api/dashboard.ts`（整文件） + `store/modules/dashboard.ts` | API+store | 仅两者互引，无视图 dispatch/读取 | 成对删除 |
| `api/market.ts:296-304` `getStockFactorScores` | API 方法 | 定义后无任何调用（用户线索已验证） | 删除或接入 StockSignalPanel |
| `store/plugins/persistedstate.ts`（整文件，260 行） | 自研插件 | `store/index.ts:2` 实际从 **npm 包 vuex-persistedstate** 导入；本地文件（含 186-257 行 `quantPersistedState` 配置）从未被引 | 删除整个文件 |
| `store/modules/layout.ts:32-92,122-130,209-210,255-257` | store 状态 | `siderNavigation`（menuItems 菜单配置/collapsed/activeKey/openKeys）无任何消费方：AppSidebar 用本地 ref 管理菜单（`AppSidebar.vue:109-375`）；`store/index.ts:41` 持久化路径 `layout.siderNavigation.collapsed` 亦无效（用户线索已验证） | 删除 siderNavigation 相关 state/mutation/action/getter |
| `store/modules/{data,performance,strategyStudio,trade}.ts` | store 模块 | 已注册但无任何视图 dispatch/读取（仅死代码 useTrade/useWebSocket/PortfolioPerformance 引用） | 成对删除 |
| `store/index.ts:36-37,43` 持久化路径 `events.currentStrategy/backtestParams/currentAccount` | 配置 | `events` 模块不存在，持久化还原恒为 undefined | 删除无效路径 |
| `composables/index.ts`（整文件） | 桶文件 | 无 `from "@/composables"` 引用 | 删除 |
| `composables/{useTrade,useStrategy,useDataSync,useChart,useChartDrawing,useVisibilityCulling,useBacktestResult}.ts` | composable | 仅被死组件（ParameterOptimize/MultiStrategyCompare/PortfolioPerformance 等）或死桶引用；useStrategy 内含未清理的 setInterval（`:184`） | 随死组件删除 |
| `utils/worker/backtest.worker.ts`（≈340 行） | Web Worker | 全项目无 `new Worker(...)` 实例化 | 删除（若计划前端计算则接入） |
| `utils/worker/dataProcessor.worker.ts`（≈270 行） | Web Worker | 同上，从未实例化 | 删除 |
| `utils/{riskCalculator,strategyHelper,indicators,colorTokens}.ts` | 工具 | 均无 import | 删除 |
| `utils/number.ts` / `utils/icons.ts` | 工具 | 无消费方（@vicons/ionicons5 依赖仅 icons.ts 引用） | 删除或接入使用 |
| `components/dashboard/*`（MarketSentiment/RealTimeSignals/RiskOverview/PortfolioPerformance） | 组件 | 无任何视图引用；内含对不存在 store 模块的 WS commit | 删除 |
| `components/common/{AppAlert,ConnectionStatus,DashboardCard,DateRangePicker,GlobalNotification,JsonViewer,PerformanceMetrics,ResourceUsage,StatusBadge,SystemLogs}.vue` | 组件 | 无引用；`DashboardCard.vue:45` import `../ui/StatusBadge.vue` 路径不存在，一旦被引用即构建失败 | 删除 |
| `components/strategy/{BacktestConfig,BacktestLogs,FactorDetailAnalysis,FactorSelector,MultiStrategyCompare,ParameterOptimize,ParameterOptimizer,ParameterTable,ParamSlider,PerformanceBadge,PerformanceTable,RealTimePerformance,SignalMonitor,StockPoolSelector,StrategyTemplate,VariableMonitor}.vue` | 组件 | 无引用；ParamSlider/TimeRangeSlider 仅被死组件 BacktestConfig 引用 | 删除 |
| `components/trade/{AccountBar,BasketEditor,OrderList,OrderTable,PositionCard,PositionDistribution,PositionList,PositionTable,RecentTrades,RiskMatrix,SignalTable,TradeConfirm,TradeForm}.vue` | 组件 | 无引用 | 删除 |
| `components/editors/{BacktestPanel,LiveFeedbackPanel,ParameterPanel}.vue` | 组件 | 无引用（MonacoEditor↔CodeEditorPanel↔StrategyWorkspace 链路正常，保留） | 删除 |
| `components/data/{AccuracyDetail,AnomalyDetail,DataTable,DataTableDetail,FactorSelector,IndustryStrengthChart,MarketDepth,QuotePanel,StockAnnouncements,StockDetailPanel}.vue` | 组件 | 无引用 | 删除 |
| `components/market/{FinStatementTable,IndustryMomentumChart,MacroTrendModal}.vue` | 组件 | 无引用（用户线索已验证；IndustryMomentumChart 仅 wrap 被用的 IndustryMomentumScatter） | 删除 |
| `views/Signal/{SignalHistory,SignalTimeline}.vue` | 视图 | 路由 `/signals/history`、`/signals/timeline` 均 redirect（`routes.ts:405-411`），两文件无引用 | 删除 |
| `views/System/{DataSync,Monitor}.vue` | 视图 | 无路由（旧版重复页，现役为 DataCenter/DataSync 与 System/Dashboard） | 删除 |
| `views/TradeCenter/Trading/TradingDashboard.vue`（782 行） | 视图 | 无路由/引用（`/trade` redirect 到 `/trade/workspace`）；内含 OrderForm 假下单（§5.11） | 删除 |
| `views/StrategyCenter/Performance/{StrategyPerformance,AttributionAnalysis,PerformanceComparison}.vue` | 视图 | 无路由；`StrategyPerformance.vue:59-62` 仍 push 不存在的 `/performance/comparison`、`/performance/attribution` | 删除或补路由 |
| `layouts/StrategyLayout.vue` | 布局 | `App.vue:142-146` layoutMap 无 "strategy" 键，`routes.ts:235,242` 的 `layout:"strategy"` 静默回落 MainLayout | 删除 |
| `layouts/ReportLayout.vue` | 布局 | 无任何路由使用 layout:"report" | 删除或补路由 |
| `plugins/echarts.ts` | 插件 | 从未 `app.use()`；main.ts:9 直接全量引入 echarts | 删除（或改为唯一按需入口） |
| `locales/`（zh-CN/en-US.json + index.ts） | i18n | `main.ts:292` 注册 vue-i18n，但全项目无 `useI18n`/`$t` 调用 | 删除或落地使用 |
| `store/modules/strategy.ts:398-412,417-421` `startStrategyMonitoring/startSignalCleanup` | store action | 无任何 dispatch；`startSignalCleanup` 的 setInterval 永不清理 | 删除 |
| `store/modules/strategy.ts:386` `signalsAPI.getSignals({ strategyId,... })` | 参数 bug | `SignalQueryParams` 字段为 `strategy_id`（`api/signals.ts:10-18`），传 camelCase 后端收不到；该 action 无调用方 | 删除或改 `strategy_id` |

> 清理收益估算：上述死代码合计约 8 个视图（≈3,000 行）、50+ 组件（≈12,000 行）、6 个 store 模块（≈3,000 行）、2 个 worker（≈600 行）、2 个桶文件、3 个工具/插件、i18n 资源与自研持久化插件（≈400 行），约占 src 总行数 35%。清理不改变任何现役功能，同时消除 `DashboardCard.vue:45` 这类"一旦引用即构建失败"的隐患，并让 `vue-tsc`/构建基线恢复干净。

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|---|---|---|---|---|
| `composables/useWebSocket.ts:83-124` | WS 收到 market_data/trade_signal/order_update/risk_alert/system_status | commit 到**不存在的模块**：`market/UPDATE_REAL_TIME_DATA`、`strategy/ADD_SIGNAL`、`trade/UPDATE_ORDER_STATUS`、`risk/ADD_RISK_EVENT`、`system/UPDATE_SYSTEM_STATUS`，及 `dispatch("ui/showAlert")`（store 无 market/ui 模块，trade/strategy/risk/system 无对应 mutation）→ 运行时 Vuex 报错/未处理 rejection；`.env` 已设 `VITE_WS_URL=ws://localhost:8080/api/ws`，`Workspace.vue:25-28` 会真实触发 | **高** | 重写 handler 对接现役 store，或统一到 `api/websocket.ts` 单例 + channel 订阅 |
| `composables/useSyncEventHandler.ts:57` + `api/websocket.ts:106-110` | DataSync 页面挂载 | 订阅 `events:sync` 但**全项目无人调用 `webSocketService.connect()`**（仅死代码 TradingDashboard/strategyStudio 调用），订阅消息入队后永不到达，页面退化为轮询 | 中 | 页面挂载时 connect（带 token），或删除 WS 通道改纯轮询 |
| `composables/useWebSocket.ts:128-141,185-187` | 组件卸载时恰逢断线 | `disconnect()` 不清理重连 setTimeout，卸载后定时器仍触发 `connect()` 重建连接（泄漏） | 中 | disconnect 中保存并 clearTimeout |
| `api/websocket.ts:24,158-165` + `:66-72` | 断线重试 | messageQueue 无上限；重连 5 次后**静默放弃**且无 UI 提示；无心跳探测（长连接假活） | 低 | 队列限长 + 放弃时通知全局状态；加 ping/pong 心跳 |
| `utils/request.ts:131` + 各视图 catch | 任何请求失败 | 拦截器 `message.error` + 视图 catch `message.error` 双 toast（`SignalConfirm.vue:96,123,134`、`StockScreener.vue:152` 等） | 低 | 单一提示出口（拦截器提示后视图不再提示，或反之） |
| `views/Signal/SignalConfirm.vue:105` | 打开确认弹窗 | `fill_time = new Date().toISOString().slice(0,16)` 为 **UTC**，东八区默认成交时间少 8 小时 | 中 | `dayjs().format("YYYY-MM-DD HH:mm")` 本地时间 |
| `views/Signal/SignalMonitor.vue:39-44,157-166` | 按状态筛选 | `signalStatus()` 归一化（pending_manual→pending），但筛选项值为 `pending_confirm`（`:159`），且 `params.status`（`:68`）原样透传后端 → 归一化与筛选项值不一致，筛选可能查空 | 待确认 | 统一状态枚举：筛选项与归一化及后端取值对齐 |
| `views/DataCenter/Market/StockScreener.vue:136-161` | 快速连续改筛选 | 有 500ms 防抖，但**无竞态保护**：慢的旧请求返回后覆盖新结果；timer 卸载未清理 | 中 | AbortController/请求序号取最后结果；onUnmounted clearTimeout |
| `views/DataCenter/Market/MarketDashboard.vue:440-484` | 部分接口失败 | 7+ 并行请求各自 `.catch(()=>{})`（:438,450,464,472,478）静默吞错，页面无部分失败提示；仅主请求失败才置 error | 中 | failedSources 模式（同 Workspace.vue:76-80）统一提示 |
| `views/Signal/SignalMonitor.vue:80-81` | 列表加载失败 | catch 仅置 `error=true` 显示 n-result，无 message 提示与错误详情 | 低 | 补错误详情或 message |
| 空数据渲染 | 各表格/图表 | SignalConfirm 有 `#empty`（`:153`）、MarketDashboard 有空态、BacktestReport 用 `v-if` 守卫空图表（`:132`）——覆盖较好；但 StockScreener/IndexDetail 等搜索结果的空态与加载骨架覆盖不均（部分仅 loading） | 低（待确认逐页） | 统一 Empty/Skeleton 组件规范 |
| 表单校验 | 信号确认/放弃、账户增改、资金操作 | SignalConfirm 表单无 n-form rules（仅 required 标记 + `:min`，`:158-168`），取消原因非必填可空提交；Workspace 账户/资金表单（`:527-591`）校验强度未逐项确认 | 中（待确认） | 补 n-form rules + 金额/数量精度校验 |
| `views/Login.vue:67-74` | 开发环境打开登录页 | 测试模式自动填充 `superAdmin/111111.a` 凭据 | 低（安全边界） | 凭据不写死，仅本地显式开关 |
| `views/DataCenter/Market/ETFMarket.vue:145-165` | DOM 未就绪建图 | setTimeout 重试最多 3 次，timer 未记录清理（卸载后仍可能触发一次 build） | 低 | 记录 timer 并在 onBeforeUnmount 清理 |
| `components/common/DashboardCard.vue:45` | 一旦被引用 | import `../ui/StatusBadge.vue` 不存在 → 构建失败（当前因死代码未触发） | 中 | 删除文件（§2 已列） |
| `store/modules/risk.ts:312-323` | 风控事件触发 | `commit("layout/ADD_ALERT", ...)` 写入 layout.rightPanel.alerts，**无任何组件渲染这些告警** → 数据无出口 | 中 | 接入 GlobalNotification/AppHeader 或移除该 commit |
| `router/guard.ts:58-68` | 系统初始数据加载失败 | `system/loadInitialData` 抛错仅 console.error 后放行导航，页面可能长期空数据（依赖各页 n-result 兜底，但无统一重试引导） | 低（待确认） | 放行同时记录全局 error 状态并引导刷新 |
| `views/Risk/RiskMonitor.vue:139` | 事件列表加载 | 固定 `page_size: 100` 一次性全量拉取，无分页 | 中 | 分页 + 按需加载 |
| `views/DataCenter/DataSync/SyncHistory.vue:146-148` | CSV 导出 | 用 `document.createElement("a")` 下载，文件名 `signals_${toISOString().split("T")[0]}.csv` 为 UTC 日期（仅影响文件名，低危） | 低 | 换 dayjs 本地日期 |
| `views/StrategyCenter/Backtest/BacktestWorkspace.vue:364-367` | URL 带 taskId 直达 | `setTimeout` 异步启动轮询，一次性 timer 未记录清理（组件卸载后仍可能执行一次回调） | 低 | 记录 timer 并在 onBeforeUnmount 清理 |
| `views/DataCenter/Market/IndexDetail.vue:240` | 指数/代码搜索输入 | 未发现防抖（与 StockScreener 的 500ms 防抖不一致） | 待确认 | 统一 debounce composable |
| `views/TradeCenter/Account/AccountPerformance.vue:378` | 账户数据加载 | 裸 `request.get("/quantTrade/account/list")` 全量拉取（page_size 100），绕过 api 层 | 中 | 走 performanceAPI/tradeAPI 并分页 |
| `views/Register.vue:117-119` | 注册成功后跳转 | `setTimeout(1500ms)` 跳登录，timer 未记录清理（一次性，低危）；注册表单有必填/密码一致性/长度校验（`:92-105`），但无邮箱格式与复杂度校验 | 低 | 校验补全；timer 可忽略或统一封装 |
| `views/DataCenter/Market/StockDetail.vue:402-403` | 切换股票代码 | `watch(tsCode, load)` + onMounted 加载，无竞态保护（快速切换时旧请求可能覆盖新股票数据） | 待确认 | 请求序号/AbortController |
| `views/TradeCenter/Execution/ExecutionAnalysis.vue:476-487` | 页面卸载 | 4 个 ECharts 实例 dispose + resize 监听移除（正面示例） | — | 保持，作为 ECharts 清理范本 |

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|---|---|---|---|
| `main.ts:9` + `:17-129` | 全量 `import * as echarts` + 全量 Naive UI 全局注册 ~80 组件 | ECharts、Naive UI 全量打入首包；manualChunks（vite.config.ts:39-78）只能拆包不能摇树 | unplugin-vue-components 按需 + `echarts/core` 按需；删除全局注册 |
| 11 处视图级 `import * as echarts`（ExecutionAnalysis:131、RiskMonitor:5、StockContextPanel:4、ProfitDistributionChart:7、StrategyPerformance:136、AccountPerformance:237、PerformanceComparison:12、IndustryStrengthChart:21、FactorDetailAnalysis:153、PositionDistribution:23、MacroTrendModal:6） | 与按需注册并存 | 全量包被多处拉入，按需注册形同虚设 | 统一 `echarts/core` 按需；main.ts 不挂全局 $echarts |
| `views/TradeCenter/Workspace.vue:76-81,122` | 一次并行拉取 account/positions/orders/baskets/signals，page_size 100~200 全量 | 大账户首屏请求大、表格渲染卡顿 | 分页 + 游标；表格虚拟滚动 |
| 全局 n-data-table | 无虚拟滚动（Workspace、SyncHistory、SignalMonitor 等） | 千行级卡顿 | vxe-table 或调小分页（现多数 20-50/页，中等风险） |
| `views/DataCenter/Market/MarketDashboard.vue:440-484` | 单页 7+ 独立 HTTP 请求 | 弱网首屏慢 | 后端聚合（api/dashboard.ts 本是聚合但已死）或前端并发上限 + 缓存 |
| `store/modules/strategy.ts:418-421` | startSignalCleanup setInterval 每小时执行、永不清理（且无调用方） | 若启用即全局定时器泄漏 | 删除 |
| `utils/request.ts:9` | 全局 timeout 120s | 对普通查询过长，失败感知慢 | 按请求覆盖（回测类保持长超时） |
| 防抖覆盖不全 | StockScreener 有防抖（`:158-161`）；IndexDetail 搜索框（`:240`）等未见防抖 | 输入即请求 | 统一 debounce composable |
| 图表更新模式 | LightweightKLine/EquityCurve 等用 setData 增量更新（良好）；ETFMarket 每次展开重建 chart（有 remove，可接受） | — | 保持 |
| 深 watch/未用 computed | 未发现滥用；主要视图均用 computed 缓存派生数据（MarketDashboard/SignalMonitor stats） | — | 保持；个别模板内直接调方法处待确认 |
| 死代码打包 | §2 所列死代码多数不被 Vite 打包（未被引用），但 `DashboardCard.vue:45` 等坏 import 是定时炸弹；i18n/worker/自研插件等已引用资源纯增包体 | 中 | 按 §2 清理后再做体积基线 |
| `views/Risk/RiskMonitor.vue:139` | 固定 page_size 100 拉取事件 | 事件量大时首屏慢 | 中 | 分页 |
| `views/TradeCenter/Account/AccountPerformance.vue:378` | 全量账户列表 | 账户多时请求重 | 低 | 分页/按需 |
| `views/DataCenter/DataSync/SyncHistory.vue` | 历史任务大表 | n-data-table 无虚拟滚动（全项目同款问题） | 低 | 分页已存在则缩小页容量 |
| three.js 加载 | `MainLayout.vue:73-74`、`TradingDashboard.vue:329-330` 用 defineAsyncComponent 异步加载 ParticleBackground | 已按需分包（正面） | — | 保持；TradingDashboard 删除后同步移除 |
| 定时器清理抽查（正面） | `MainLayout.vue:119,122`（30s stats）、`AppHeader.vue:330-334`（时钟/交易时段）、`System/Dashboard.vue:253-254`、`FactorDashboard.vue:594,763`、`RiskMonitor.vue:309`、`StrategyWorkspace.vue:450` | 均已 onUnmounted/onBeforeUnmount 清理 | — | 保持，作为后续轮询/定时器编写的对照范本 |
| `views/DataCenter/DataSync/DataSync.vue:66` + `useSyncTimer.ts:9-11` | 每秒 now 定时器 | 仅驱动 elapsedTime 展示，1s 粒度合理且已清理 | 低 | 保持 |
| `components/charts/LightweightKLine.vue:216-244` 等 | tooltip 3s 自动隐藏 | 组件内局部 timer，正常 | — | 保持 |
| `main.ts:401-405` | 开发模式暴露 `globalThis.__QUANT_APP__` | dev 调试便利；需确认生产构建 VITE_APP_ENV 未设置（否则泄漏调试句柄） | 低 | 生产环境裁剪 |

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|---|---|---|---|
| `composables/useWebSocket.ts:83-124` + `.env` VITE_WS_URL | 交易工作台实时通道全部落到不存在的 store mutation/action，行情/信号/告警推送**功能性失效**（§3.1） | 高 | 重构 WS 消息路由到现役 store，或统一单例 |
| `utils/request.ts:104-115` | 401 仅清 localStorage 不清 Vuex（`store.user.token` 残留）→ 守卫仍放行、下请求带失效 token；整页 `window.location.href` 跳登录丢 SPA 状态；并发 401 多次跳转；`authApi.refreshToken`（api/auth.ts:91-98）存在但从未接入 | 高 | 401 同步清 store + 路由跳转；接入 refresh token 队列重放 |
| `views/Login.vue:107-123` | 直连裸 request 绕过 authApi 与 user store login action（后者成死代码）；`:118-119` 完整响应 user 原样入 localStorage（绕过 SET_USER_INFO 的敏感字段裁剪） | 中 | 统一 `store.dispatch("user/login")` |
| `views/Signal/SignalConfirm.vue:116-136` | 确认/取消后刷新 ✓（闭环正常）；但该页**无任何入口**（AppSidebar/SignalMonitor 均不链向 /signals/confirm，`routes.ts:413-417` 为孤儿路由） | 低（待确认） | SignalMonitor 待确认列表加"去确认"入口 |
| `views/Signal/SignalMonitor.vue:114-129` | 审核采用乐观更新 + 失败回滚 + 错误详情提示（正面示例，建议推广） | — | 保持 |
| `views/StrategyCenter/Performance/StrategyPerformance.vue:59-62` | push 不存在的路由 `/performance/comparison`、`/performance/attribution` → 404；该页本身未路由（死代码） | 中 | 删页或补路由 |
| `views/TradeCenter/Workspace.vue:76-81` 等 27 处 | 视图层直连 `request` 绕过 api/ 层，端点字符串散落、无类型返回、绕开 handleResponse 统一处理 | 中 | 收编进对应 api 模块 |
| `utils/number.ts` 零消费 + 各组件自实现 | `formatPercent` 语义不一：`FactorDetailAnalysis.vue:258`、`PerformanceTable.vue:33` 乘 100；`IndexDetail.vue:704` 自实现；若后端混用比值/百分数单位则显示错误 | 中（待确认后端单位） | 统一工具 + 明确单位契约 |
| `views/Risk/RiskEvents.vue:47` | `new Date().toISOString().split("T")[0]` 取 UTC 日期，东八区 00:00-08:00 取到前一天 | 中 | dayjs 本地日期 |
| `components/trade/OrderForm.vue:35-41,164-168` | 硬编码 5 只"模拟股票"（价格写死）；`submitOrder` 只弹"订单提交成功"**不调任何 API**（幽灵订单）；当前仅被死视图 TradingDashboard 引用 | 高（若被启用） | 整链删除；如需真实下单走 tradeAPI.createOrder + 后端校验 |
| `views/DataCenter/Market/MarketDashboard.vue` 等 | 多处 `.catch(()=>{})` 静默吞错（:438,450,464,472,478），用户无感知 | 中 | failedSources 列表 + 局部降级提示 |
| `store/index.ts:33-44` | 持久化路径含死模块（events.*、layout.siderNavigation） | 低 | 清理 |
| `router/guard.ts:10-26,84-87` | authGuard 仅查 token 存在性无过期校验；`/login` 已登录硬编码跳 `/market/dashboard`（与 `/` redirect 重复）；layoutGuard 的 window resize hack 为旧图表遗留 | 低 | 统一 redirect；移除 resize hack |
| `api/websocket.ts:83-89` | `disconnect()` 清空全部 subscribers，组件 A 断开导致组件 B 订阅丢失（单例隐式耦合） | 低 | 引用计数式订阅/退订 |
| `router/routes.ts:20-33` | 8 条旧路由 redirect 依赖链（AppSidebar routeMap `market→/market/overview` 等经 redirect 兜底） | 低 | 侧边栏 routeMap 直接指向现役路径 |
| `views/Risk/RiskMonitor.vue:139` | 事件列表固定 100 条无分页，页面无"加载更多" | 中 | 分页/滚动加载 |
| `router/guard.ts:58-68` | 系统初始数据失败仅 console.error 后放行，用户进入空数据页 | 低 | 全局错误横幅 + 重试 |
| `views/DataCenter/DataSync/SyncHistory.vue:146-148` | 导出文件名用 UTC 日期 | 低 | dayjs 本地日期 |
| `views/StrategyCenter/Backtest/BacktestWorkspace.vue:364-367` | URL taskId 直达时的启动 setTimeout 未清理 | 低 | 记录并清理 timer |
| `views/DataCenter/Market/IndexDetail.vue:240` | 搜索无防抖（与 StockScreener 不一致） | 待确认 | 统一 debounce |
| `store/modules/strategy.ts:398-412` | startStrategyMonitoring 返回清理函数但调用方不存在（死代码），若被外部调用须由调用方负责清理 | 低 | 删除（§2） |
| `views/TradeCenter/Workspace.vue:33-34` | activeTab 仅初始化时读 URL，切换不写回 | 避免与侧边栏 push 竞争（正面） | — | 保持 |
| `views/Signal/SignalMonitor.vue:79` | 分页 total 取 `res.pagination.total` | 依赖后端分页响应结构，字段名未与后端契约核验 | 待确认 | 对齐后端分页结构 |
| `store/modules/strategy.ts:40,488` | strategyPerformance 用 Map 存储 | Vue 3 reactive 支持 Map 代理，但 Map 内对象深层变更的响应性依赖访问路径，getter 多次 `.get()` 有性能/正确性隐患 | 待确认 | 确认依赖收集或改普通对象 |
| `composables/useBacktestPolling.ts:128-136` | 轮询连续失败 | 连续 3 次 API 错误自动停止并回调 onFailed（正面范式） | — | 保持 |

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|---|---|---|---|---|---|
| 1 | 高 | 业务闭环 | `composables/useWebSocket.ts:83-124` | WS 实时推送 commit 到不存在的 store 模块，行情/信号/告警失效 | 统一到 api/websocket.ts 单例并重写消息路由 |
| 2 | 高 | 业务闭环 | `utils/request.ts:104-115` | 401 只清 localStorage 不清 Vuex；无 token 刷新；整页跳转丢状态 | 同步清 store + refresh 队列重放 + 路由跳转 |
| 3 | 高 | 业务闭环 | `components/trade/OrderForm.vue:35-41,164-168` | 假订单"提交成功"无 API，幽灵订单风险（当前死链） | 整链删除（TradingDashboard 死代码） |
| 4 | 中 | 边界 | `composables/useSyncEventHandler.ts:57` | DataSync 订阅 WS 但无人 connect，事件永不到达 | 页面挂载 connect 或改纯轮询 |
| 5 | 中 | 性能 | `main.ts:9,17-129` | 全量 ECharts + Naive UI 全局注册，首包过大 | 按需引入 + 移除全局注册 |
| 6 | 中 | 死代码 | `store/modules/{dashboard,data,layout,performance,strategyStudio,trade}.ts` | 11 个 store 模块 6 个无消费方 | 删除死模块 |
| 7 | 中 | 死代码 | `store/plugins/persistedstate.ts`（整文件） | 自研持久化插件从未被引（实际用 npm 包） | 删除 |
| 8 | 中 | 死代码 | 8 个无路由视图（TradingDashboard/SignalHistory/SignalTimeline/System-DataSync/System-Monitor/Performance×3） | 无路由/无引用 | 删除 |
| 9 | 中 | 死代码 | `components/*` 约 50 个无引用组件 | 死组件群 + DashboardCard 坏 import（构建炸弹） | 批量删除（§2 清单） |
| 10 | 中 | 边界 | `views/Signal/SignalConfirm.vue:105` | 成交时间用 UTC toISOString，东八区偏差 8 小时 | dayjs 本地时间 |
| 11 | 中 | 边界 | `views/DataCenter/Market/StockScreener.vue:136-161` | 防抖无竞态保护，旧请求覆盖新结果 | AbortController/序号守卫 |
| 12 | 中 | 边界 | `composables/useWebSocket.ts:128-141,185-187` | 卸载后重连定时器仍触发，连接泄漏 | disconnect 清理 timer |
| 13 | 中 | 业务闭环 | `views/StrategyCenter/Performance/StrategyPerformance.vue:59-62` | 跳转不存在的路由 → 404（该页亦未路由） | 删页或补路由 |
| 14 | 中 | 业务闭环 | `views/Login.vue:107-123` | 绕过 authApi/user store，敏感 user 原样入 localStorage | 统一走 user/login action |
| 15 | 中 | 业务闭环 | `views/Risk/RiskEvents.vue:47` | toISOString 取 UTC 日期，凌晨跨天取错 | dayjs 本地日期 |
| 16 | 中 | 业务闭环 | `store/modules/strategy.ts:386` | getSignals 传 camelCase 参数与后端 snake_case 不符 | 删除死 action 或改字段 |
| 17 | 中 | 边界 | `store/modules/risk.ts:312-323` | 风控告警写入 layout store 但无组件渲染 | 接入展示或移除 |
| 18 | 中 | 边界 | `views/DataCenter/Market/MarketDashboard.vue:440-484` | 7+ 请求静默吞错，无部分失败提示 | failedSources 模式统一提示 |
| 19 | 低 | 边界 | `utils/request.ts:131` + 视图 catch | 拦截器 + 视图双 toast | 单一提示出口 |
| 20 | 低 | 业界对比 | `layouts/{StrategyLayout,ReportLayout}.vue`、`plugins/echarts.ts`、`locales/`、`utils/worker/*` | 布局/插件/i18n/worker 均死代码或空注册 | 删除或落地使用 |

---
**待确认项汇总**（需结合后端契约或运行验证）：
1. `SignalMonitor.vue:157-166` 筛选项值（pending_confirm）与后端实际状态枚举（pending/pending_manual/approved/promoted...）是否一致；
2. `utils/number.ts`/各组件 formatPercent 的乘 100 语义与后端返回单位（比值还是百分数）；
3. IndexDetail 搜索（`:240`）是否已存在防抖（未逐行确认 watch/事件绑定）；
4. `guard.ts:64-68` loadInitialData 失败放行后各页面空数据兜底是否足够；
5. Workspace/账户/资金表单（`Workspace.vue:527-591`）的校验强度与金额精度约束；
6. 各页空数据骨架屏/Empty 覆盖完整性（多数页面已覆盖，剩余待逐页核对）。

**审查结论摘要**：工程整体结构清晰、图表与轮询生命周期管理达业界水准；核心问题集中在（1）WebSocket 双客户端且现役路径 handler 全部指向不存在的 store 模块（高危功能失效）、（2）大规模死代码（约 8 个视图、50+ 组件、6 个 store 模块、2 个 worker、多个 api/composable/工具文件，含 1 处坏 import 构建炸弹）、（3）ECharts/Naive UI 全量引入导致打包体积偏大、（4）UTC 时区、格式化语义、请求竞态等边界细节。建议按 §2 死代码清单先行清理（可显著减小源码与包体），再修复 §5 的 1-2 号高危业务闭环问题；所有"待确认"项已在上文标注。

**补充说明**：本报告行号基于 2026-08-14 工作区快照；`package.json` 的 build 脚本（`vite build`）未接入 `vue-tsc`/ESLint，死代码与坏 import 无静态检查防线，建议清理后补上 `vue-tsc --noEmit` 与 lint 到 CI/构建链路，防止同类问题回潮。另注：任务书按"Pinia store 设计"维度审查，但项目实际使用 Vuex 4，本报告按实际情况审查并已在 §1.2 标注。

## 7. 业界标准对照（问题 → 标准映射）

> 本章把 §1-§6 的问题与业界公认评审标准逐一映射，作为判定依据。引用标准速查：
> - **GCR**：Google 代码评审规范（Code Review Developer Guide / Code Health）— 正确性、可读性、删除死代码、错误处理、不留下调试/桩代码（google.github.io/eng-practices/review/reviewer/looking-for/）
> - **CC**：Robert C. Martin《Clean Code》— 单一职责（SRP）、DRY、错误处理不吞异常、不留假数据/桩
> - **V3S**：Vue 3 官方风格指南与性能最佳实践 — 组件拆分、组合式 API、`onUnmounted` 清理、按需引入、虚拟滚动（vuejs.org/style-guide/、vuejs.org/guide/best-practices/performance.html）
> - **RF**：Martin Fowler《重构》坏味道清单 — Long Function、Large Class、Duplicated Code、Dead Code、Feature Envy（refactoring.com/catalog/）
> - **WV**：Web Vitals 与前端性能规范 — LCP/INP/TBT、包体控制、防抖节流、虚拟滚动、长任务（web.dev/vitals/）
> - **OWASP**：OWASP 前端安全 — XSS 防护、敏感信息存储、会话管理、硬编码凭据（Top 10 / Cheat Sheet Series）

### 7.1 问题 → 标准映射表

| 报告位置（§ / 文件:行） | 问题 | 依据标准 | 标准要点 |
|---|---|---|---|
| §1.2、§4.3；DataSync.vue ≈1627 行、MarketDashboard.vue 1329 行、Workspace.vue 1189 行 | 巨型组件未拆分 | **V3S**：组件拆分（清晰单一职责，大组件拆子组件/composable）；**RF**：Long Function / Large Class；**GCR**：可读性 | 组件应职责单一、单文件可控；大组件难读难测难复用 |
| §2 全部死代码（8 视图/50+ 组件/6 store/2 worker 等） | 大量无引用代码 | **GCR**：Code Health（删除死代码，不保留"以后可能用到"的代码）；**RF**：Dead Code 坏味道；**CC**：YAGNI/DRY | 死代码增加认知负担与回归面；坏 import（DashboardCard.vue:45）是构建炸弹 |
| §1.2、§5.7、§5.8；27 处视图直连 request、formatPercent 各组件自实现 | 重复封装/重复格式化，语义不一 | **RF**：Duplicated Code；**CC**：DRY / Once and Only Once；**GCR**：避免重复（易漂移不一致） | 同一逻辑只实现一次，收敛到 utils/api 层并加单测 |
| §3.1、§5.1；useWebSocket.ts:83-124 commit 到不存在的 store 模块 | 运行时错误路径、功能静默失效 | **GCR**：正确性是评审首要标准；**CC**：错误处理（fail fast，不静默） | 调用不存在的 mutation/action 应被静态检查/单测捕获，而非运行时报错 |
| §3.2；useSyncEventHandler.ts:57 订阅 WS 但无人 connect | 订阅无连接，事件永不到达 | **GCR**：正确性；**CC**：错误处理 | 生命周期闭环（connect→subscribe→unsubscribe→disconnect）应成对出现 |
| §3.10、§5.10；MarketDashboard.vue:440-484 等多处 `.catch(()=>{})` | 静默吞错、无部分失败提示 | **CC**：错误处理章节（不吞异常，失败要有出口）；**GCR**：可观测性 | 吞错导致问题不可诊断；用 failedSources 模式统一呈现 |
| §5.2；request.ts:104-115 401 只清 localStorage 不清 Vuex、双 token 源 | 状态双源不一致、会话失效处理不完整 | **GCR**：正确性；**CC**：Single Source of Truth（DRY 的架构延伸） | token 唯一来源（store）统一读写，401 需同步清理并跳转 |
| §3.6、§5.9、§5.14；SignalConfirm.vue:105 / RiskEvents.vue:47 用 UTC | 时区处理错误，东八区偏差 | **GCR**：正确性；**CC**：边界处理 | 日期时间统一 dayjs + 本地时区，UTC 仅用于存储/传输 |
| §4.1、§4.2；main.ts:9 全量 echarts + Naive UI 全局注册 + 11 处全量 import | 包体过大、摇树失效 | **WV**：LCP/TBT（bundle 体积直接影响加载与主线程）；**V3S**：按需引入/懒加载 | 按需注册组件与图表模块，删除全局全量引入 |
| §4.3-4.6、§3.8；大表无虚拟滚动、page_size 100-200 全量、StockScreener 竞态 | 长列表与请求竞态 | **WV**：INP（长任务/大列表渲染卡顿）；**V3S**：性能（虚拟滚动）；**GCR**/前端性能规范：防抖节流、取消过期请求 | 虚拟滚动 + 分页 + AbortController 竞态守卫 |
| §3.11、§5.5；IndexDetail.vue:240 搜索无防抖（待确认）、StockScreener 无竞态保护 | 输入即请求 / 旧请求覆盖新结果 | **WV**/前端性能规范：防抖节流；**GCR**：正确性 | 统一 debounce composable + 请求序号 |
| §3.13、§5.3；Login.vue:107-123 直连 request、完整 user 原样入 localStorage | 敏感信息存 localStorage（XSS 可窃取） | **OWASP**：XSS 与敏感信息存储（localStorage 存储敏感数据 + XSS 注入风险）；**GCR**：安全 | 仅存最小必要信息，token 存内存/受限存储，敏感字段裁剪（SET_USER_INFO 已有裁剪，登录路径未走） |
| §3.13、§5.3；Login.vue:73 测试凭据 superAdmin/111111.a 写死 | 硬编码凭据 | **OWASP**：硬编码凭据（ASVS 会话/凭据管理）；**CC**：不留桩数据 | 凭据走环境变量/配置，禁止进代码库 |
| §5.2、§1.6；guard.ts:10-26 仅 token 存在性校验 | 前端访问控制薄弱 | **OWASP**：访问控制（前端校验不可信，服务端必须兜底）；**GCR**：正确性 | 前端校验仅 UX，安全以服务端为准；前端补过期提示 |
| §5.11；OrderForm.vue:35-41,164-168 硬编码股票 + 假提交 | 生产代码含 mock 数据与假提交（幽灵订单） | **CC**：不留假数据/桩代码；**GCR**：不留调试桩（Code Health） | 整链删除或接真实 API |
| §3.5、§5.12；拦截器 + 视图双 toast、重复提示 | 错误提示重复/出口不唯一 | **CC**：错误处理；**GCR**：可读性/一致性 | 单一提示出口 |
| §5.6；StrategyPerformance.vue:59-62 跳不存在的路由 | 死链 404 | **GCR**：正确性；**V3S**：路由与导航一致性 | 路由与跳转点同步维护，加路由清单测试 |
| §1.1、§4.10（正面）；useChartLifecycle/useBacktestPolling/各 onUnmounted 清理 | 生命周期与轮询清理规范 | **V3S**：组合式 API 生命周期（onUnmounted 清理定时器/监听）；**WV**：避免后台定时器空转 | 符合标准，作为项目范式固化 |
| §1.1、§4.11（正面）；lightweight-charts remove + ResizeObserver、ECharts 按需注册 | 图表实例销毁与 resize | **V3S**：组件卸载必须释放资源；**WV**：避免内存泄漏 | 符合标准，保持并推广到 ECharts 全量引入处 |

### 7.2 判定口径说明
- 同一问题可同时命中多条标准，表中按"最相关"取主标准（如巨型组件主判 V3S 组件拆分 + RF Large Class，辅判 GCR 可读性）。
- **GCR/CC/RF 属于工程通用标准**，适用于任何语言；**V3S/WV/OWASP 为领域标准**，分别约束 Vue 组件、性能与安全。判定顺序：先领域标准（V3S/WV/OWASP），再通用标准（GCR/CC/RF）。
- 待确认项（§6 尾部列表）的判定依赖后端契约/运行验证，未强行套标准，待确认后按同表口径归位。
