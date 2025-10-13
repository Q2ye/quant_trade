### 将警示规则写在首页：警惕：每个策略的有效性只有一到两年，策略要迭代，以适应不同的市场环境
### 一定要有止盈止损规则，并严格执行

```markdown
todo：后续工作
1. 前端菜单设计：菜单功能设计
2. 前后端数据交互：api接口调试
3. 数据同步
4. 策略开发


```ini
核心模块开发
主引擎（MainEngine）	系统协调中心  已完成
策略引擎	策略执行与回测（Backtrader/PyAlgoTrade） 已完成
以下引擎bug待修复
事件引擎	异步事件分发（asyncio + 优先级队列）
选股引擎	多因子筛选与组合优化
风控引擎	实时风险监控（规则引擎）

业务流程处理：
api--->service--->db--->api
service：添加对应业务数据处理流程

各个接口测试

```


数据模块（1.5个月）
集成Tushare API，设计本地数据库（MySQL存储基本面，MongoDB存储Tick数据）34。
实现复权计算、异常值清洗（如涨跌停板价格修正）3。
回测引擎（2个月）
参考Lean的事件驱动架构，按Bar推送数据25。
核心需求：支持多线程回测、动态滑点模拟（限价单按盘口冲击成本计算）6。
策略开发（1.5个月）
因子示例：技术指标（RSI、布林带）、基本面（ROE分位数）、资金流（大单净占比）69。
组合逻辑：因子加权打分 → 选前10%股票 → 动态止盈止损（回撤>5%减仓）6。
实盘部署（1个月）
通过券商API（如东方财富、华泰）接入交易，初始资金≤10%17。
监控重点：订单成交率（<90%需调整报价策略）、策略与回测收益偏差（>15%暂停）4。

```angular2html
src/
├── App.vue                          # 应用根组件，包含全局布局和路由出口
├── main.ts                          # 应用入口文件，初始化Vue实例和全局配置
├── shims-vue.d.ts                   # Vue类型声明文件，支持TypeScript
├── vite-env.d.ts                    # Vite环境变量类型声明
│
├── api/                             # API接口层：封装所有后端HTTP请求
│   ├── basket.ts                    # 篮子管理相关API（创建、查询、更新、删除）
│   ├── data.ts                      # 数据同步和行情数据API
│   ├── strategy.ts                  # 策略管理API（创建、回测、执行）
│   ├── system.ts                    # 系统管理API（用户、权限、日志）
│   ├── trade.ts                     # 交易执行API（下单、撤单、查询）
│   ├── user.ts                      # 用户认证和管理API
│   └── websocket.ts                 # WebSocket连接管理，实时数据推送
│
├── assets/                          # 静态资源目录
│   ├── fonts/                       # 字体文件
│   │   ├── sarasa-term-sc-nerd.ttf  # 等宽编程字体，支持图标显示
│   │   └── Source_Han_Sans_SC.otf   # 思源黑体中文字体
│   ├── icons/                       # 图标资源（SVG或图片）
│   └── scss/                        # 全局样式文件
│       ├── global.scss              # 全局样式入口文件
│       ├── _charts.scss             # 图表专用样式（ECharts定制）
│       ├── _layout.scss             # 布局相关样式
│       ├── _mixins.scss             # SCSS混入函数
│       └── _variables.scss          # 全局变量（颜色、间距、字体等）
│
├── components/                      # 可复用组件库，按业务模块组织
│   ├── charts/                      # 数据可视化图表组件
│   │   ├── HeatmapChart.vue         # 热力图组件（用于相关性分析）
│   │   ├── IndicatorChart.vue       # 技术指标图表（MACD、RSI等）
│   │   ├── KLineChart.vue           # K线图组件（支持技术分析）
│   │   ├── NetValueChart.vue        # 净值曲线图（策略绩效展示）
│   │   └── PortfolioPieChart.vue    # 投资组合分布饼图
│   │
│   ├── common/                      # 通用业务组件（原utils目录）
│   │   ├── CodeDiff.vue             # 代码差异对比组件（策略版本比较）
│   │   ├── DateRangePicker.vue      # 日期范围选择器
│   │   └── JsonViewer.vue           # JSON数据可视化查看器
│   │
│   ├── data/                        # 数据展示和操作组件
│   │   ├── DataTable.vue            # 通用数据表格（支持排序、分页）
│   │   ├── FactorSelector.vue       # 多因子选择器（量化研究）
│   │   ├── QuotePanel.vue           # 实时行情面板
│   │   ├── StockAnnouncements.vue   # 股票公告信息组件
│   │   └── TimeRangeSlider.vue      # 时间范围滑动选择器
│   │
│   ├── dashboard/                   # 仪表盘专用组件
│   │   ├── MarketSentiment.vue      # 市场情绪看板（涨跌家数等）
│   │   ├── PortfolioPerformance.vue # 组合绩效展示组件
│   │   ├── RealTimeSignals.vue      # 实时信号流展示
│   │   └── RiskOverview.vue         # 风险概览面板
│   │
│   ├── editors/                     # 代码和策略编辑器相关组件
│   │   ├── MonacoEditor.vue         # Monaco代码编辑器封装
│   │   └── StrategyEditor/          # 策略编辑器专用组件
│   │       ├── CodeEditorPanel.vue  # 代码编辑区域面板
│   │       ├── ParameterPanel.vue   # 策略参数配置面板
│   │       ├── BacktestPanel.vue    # 回测配置和执行面板
│   │       └── LiveFeedbackPanel.vue # 实时日志和反馈面板
│   │
│   ├── layout/                      # 布局相关组件
│   │   ├── AppHeader/               # 顶部导航栏组件
│   │   │   ├── Index.vue            # 头部主组件
│   │   │   ├── Navigation.vue       # 导航菜单组件
│   │   │   └── UserMenu.vue         # 用户下拉菜单
│   │   ├── AppSidebar/              # 侧边栏组件
│   │   │   ├── Index.vue            # 侧边栏主组件
│   │   │   └── MenuItems.vue        # 菜单项组件
│   │   └── AppFooter.vue            # 页脚组件
│   │
│   ├── strategy/                    # 策略管理相关组件
│   │   ├── BacktestConfig.vue       # 回测参数配置组件
│   │   ├── BacktestLogs.vue         # 回测日志展示组件
│   │   ├── BacktestStudio/          # 回测分析工作室组件
│   │   │   ├── MultiStrategyCompare.vue # 多策略对比分析
│   │   │   └── ParameterOptimize.vue    # 参数优化可视化
│   │   ├── ParamSlider.vue          # 参数滑动输入组件
│   │   ├── SignalMonitor.vue        # 信号监控面板
│   │   ├── StrategyTemplate.vue     # 策略模板选择组件
│   │   └── VariableMonitor.vue      # 策略变量监控器
│   │
│   ├── trade/                       # 交易执行相关组件
│   │   ├── BasketEditor.vue         # 股票篮子编辑器
│   │   ├── OrderForm.vue            # 订单表单组件
│   │   ├── OrderTable.vue           # 订单列表表格
│   │   ├── PositionCard.vue         # 持仓卡片组件
│   │   ├── PositionDistribution.vue # 持仓分布图组件
│   │   ├── PositionTable.vue        # 持仓列表表格
│   │   ├── RecentTrades.vue         # 最近成交组件
│   │   ├── RiskMatrix.vue           # 风险矩阵展示
│   │   ├── SignalTable.vue          # 信号列表表格
│   │   ├── TradeConfirm.vue         # 交易确认对话框
│   │   ├── TradeForm.vue            # 交易表单组件
│   │   └── cockpit/                 # 交易驾驶舱专用组件
│   │       ├── QuickOrderPanel.vue  # 快速下单面板
│   │       ├── ChartTrading.vue     # 图表联动交易组件
│   │       └── DepthChart.vue       # 买卖深度图组件
│   │
│   └── ui/                          # 基础UI组件库
│       ├── AppAlert.vue             # 全局提示alert组件
│       ├── DashboardCard.vue        # 仪表盘卡片容器
│       ├── GlobalNotification.vue   # 全局通知组件
│       └── StatusBadge.vue          # 状态徽章组件
│
├── composables/                     # Vue 3组合式API逻辑复用
│   ├── useWebSocket.ts              # WebSocket连接和消息管理
│   ├── useChart.ts                  # 图表初始化和更新逻辑
│   ├── useStrategy.ts               # 策略相关业务逻辑
│   ├── useTrade.ts                  # 交易执行逻辑
│   ├── useDataSync.ts               # 数据同步逻辑
│   └── index.ts                     # 统一导出入口
│
├── directives/                      # 自定义Vue指令
│   └── resize.ts                    # 元素大小变化监听指令
│
├── hooks/                           # 自定义React风格Hooks
│   ├── useDragResize.ts             # 拖拽调整大小逻辑
│   ├── useRealTimeData.ts           # 实时数据订阅管理
│   └── index.ts                     # 统一导出
│
├── layouts/                         # 页面布局组件
│   ├── EmptyLayout.vue              # 空布局（登录页等使用）
│   ├── MainLayout.vue               # 主布局（带导航栏和侧边栏）
│   ├── ReportLayout.vue             # 报告专用布局
│   ├── StrategyLayout.vue           # 策略编辑专用布局
│   └── TradeLayout.vue              # 交易专用布局
│
├── locales/                         # 国际化多语言配置
│   ├── en-US.json                   # 英文语言包
│   ├── zh-CN.json                   # 中文语言包
│   └── index.ts                     # 国际化配置和导出
│
├── plugins/                         # 第三方插件配置
│   ├── echarts.ts                   # ECharts图表库配置
│   └── monaco.ts                    # Monaco编辑器配置
│
├── router/                          # 路由配置
│   ├── guard.ts                     # 路由守卫（权限验证）
│   ├── index.ts                     # 路由实例创建和配置
│   └── routes.ts                    # 路由定义表
│
├── store/                           # Vuex状态管理
│   ├── index.ts                     # Store主入口和模块注册
│   ├── modules/                     # 业务模块状态管理
│   │   ├── basket.ts                # 篮子管理状态
│   │   ├── dashboard.ts             # 仪表盘状态
│   │   ├── data.ts                  # 数据管理状态
│   │   ├── layout.ts                # 布局状态（侧边栏折叠等）
│   │   ├── performance.ts           # 绩效分析状态
│   │   ├── risk.ts                  # 风险管理状态
│   │   ├── strategy.ts              # 策略管理状态
│   │   ├── strategyStudio.ts        # 策略工作室状态
│   │   ├── system.ts                # 系统管理状态
│   │   ├── trade.ts                 # 交易执行状态
│   │   └── user.ts                  # 用户认证状态
│   └── plugins/                     # Vuex插件
│       └── persistedstate.ts        # 状态持久化插件
│
├── types/                           # TypeScript类型定义
│   ├── index.ts                     # 类型定义主入口
│   ├── api/                         # API接口类型定义
│   │   ├── backtest.ts              # 回测API类型
│   │   ├── base.ts                  # 基础API类型
│   │   ├── basket.ts                # 篮子API类型
│   │   ├── data.ts                  # 数据API类型
│   │   ├── index.ts                 # API类型统一导出
│   │   ├── response.ts              # 响应数据结构类型
│   │   ├── strategy.ts              # 策略API类型
│   │   ├── system.ts                # 系统API类型
│   │   ├── trade.ts                 # 交易API类型
│   │   ├── types.ts                 # 通用类型定义
│   │   ├── user.ts                  # 用户API类型
│   │   └── websocket.ts             # WebSocket消息类型
│   ├── entities/                    # 业务实体类型
│   │   ├── base.ts                  # 基础实体类型
│   │   ├── basket.ts                # 篮子实体类型
│   │   ├── index.ts                 # 实体类型统一导出
│   │   ├── market.ts                # 市场数据实体
│   │   ├── performance.ts           # 绩效实体类型
│   │   ├── risk.ts                  # 风险实体类型
│   │   ├── strategy.ts              # 策略实体类型
│   │   ├── system.ts                # 系统实体类型
│   │   ├── trading.ts               # 交易实体类型
│   │   └── user.ts                  # 用户实体类型
│   ├── enums/                       # 枚举类型定义
│   │   ├── common.enum.ts           # 通用枚举
│   │   ├── index.ts                 # 枚举统一导出
│   │   ├── strategy.enum.ts         # 策略相关枚举
│   │   ├── system.enum.ts           # 系统相关枚举
│   │   ├── trading.enum.ts          # 交易相关枚举
│   │   └── user.enum.ts             # 用户相关枚举
│   └── state/                       # Vuex状态类型定义
│       ├── index.ts                 # 状态类型入口
│       ├── root-state.ts            # 根状态类型
│       └── module-states/           # 模块状态类型
│           ├── basket-state.ts      # 篮子状态类型
│           ├── dashboard-state.ts   # 仪表盘状态类型
│           ├── data-state.ts        # 数据状态类型
│           ├── index.ts             # 模块状态统一导出
│           ├── layout-state.ts      # 布局状态类型
│           ├── performance-state.ts # 绩效状态类型
│           ├── risk-state.ts        # 风险状态类型
│           ├── strategy-state.ts    # 策略状态类型
│           ├── strategy-studio-state.ts # 策略工作室状态类型
│           ├── system-state.ts      # 系统状态类型
│           ├── trade-state.ts       # 交易状态类型
│           └── user-state.ts        # 用户状态类型
│
├── utils/                           # 工具函数库
│   ├── date.ts                      # 日期时间处理工具
│   ├── indicators.ts                # 技术指标计算工具
│   ├── lazyLoad.ts                  # 懒加载工具函数
│   ├── number.ts                    # 数字格式化工具
│   ├── request.ts                   # HTTP请求封装（axios）
│   ├── responseHandler.ts           # 响应数据处理工具
│   ├── riskCalculator.ts            # 风险计算工具
│   ├── strategyHelper.ts            # 策略辅助函数
│   ├── charts.ts                    # 图表工具函数
│   ├── common.ts                    # 通用工具函数
│   ├── form.ts                      # 表单处理工具
│   ├── table.ts                     # 表格工具函数
│   ├── vuex.ts                      # Vuex辅助函数
│   └── index.ts                     # 工具函数统一导出
│
├── worker/                          # Web Worker多线程处理
│   ├── backtest.worker.ts           # 回测计算Worker（避免阻塞UI）
│   └── dataProcessor.worker.ts      # 大数据处理Worker
│
└── views/                           # 页面级组件（路由页面）
    ├── Login.vue                    # 用户登录页面
    ├── NotFound.vue                 # 404页面
    │
    ├── Backtest/                    # 回测相关页面
    │   ├── BacktestConfig.vue       # 回测配置页面
    │   ├── BacktestReport.vue       # 回测报告查看页面
    │   └── BacktestStudio.vue       # 回测工作室主页面
    │
    ├── Basket/                      # 篮子管理页面
    │   ├── BasketDetail.vue         # 篮子详情页面
    │   ├── BasketEditor.vue         # 篮子编辑页面
    │   ├── BasketList.vue           # 篮子列表页面
    │   └── BasketSelector.vue       # 篮子选择器页面
    │
    ├── Dashboard/                   # 仪表盘页面
    │   ├── Overview.vue             # 概览仪表盘
    │   └── TradingDashboard.vue     # 交易专用仪表盘
    │
    ├── DataSync/                    # 数据同步管理
    │   ├── DataSync.vue             # 数据同步主页面
    │   ├── SyncHistory.vue          # 同步历史记录
    │   └── TaskMonitor.vue          # 任务监控页面
    │
    ├── Market/                      # 行情数据页面
    │   ├── ETFList.vue              # ETF列表页面
    │   ├── ETFMarket.vue            # ETF市场概览
    │   ├── Index.vue                # 指数行情页面
    │   ├── IndexBoard.vue           # 指数板块页面
    │   ├── IndexDetail.vue          # 指数详情页面
    │   ├── IndexList.vue            # 指数列表页面
    │   ├── IndustryStrength.vue     # 行业强度分析
    │   ├── StockDetail.vue          # 个股详情页面
    │   └── StockList.vue            # 股票列表页面
    │
    ├── Performance/                 # 绩效分析页面
    │   ├── AccountPerformance.vue   # 账户绩效页面
    │   ├── PerformanceComparison.vue # 绩效对比分析
    │   └── StrategyPerformance.vue  # 策略绩效页面
    │
    ├── Research/                    # 量化研究页面
    │   └── FactorResearch.vue       # 因子研究分析页面
    │
    ├── Risk/                        # 风险管理页面
    │   ├── BlacklistManagement.vue  # 黑名单管理
    │   ├── RiskEvents.vue           # 风险事件查看
    │   └── RiskRules.vue            # 风控规则配置
    │
    ├── Signal/                      # 信号监控页面
    │   ├── SignalHistory.vue        # 信号历史记录
    │   ├── SignalMonitor.vue        # 实时信号监控
    │   └── SignalTimeline.vue       # 信号时间轴
    │
    ├── Strategy/                    # 策略管理页面
    │   ├── RiskManagement.vue       # 策略风控配置
    │   ├── StrategyEditor.vue       # 策略编辑器页面（三屏布局）
    │   └── StrategyList.vue         # 策略列表页面
    │
    ├── System/                      # 系统管理页面
    │   ├── DataSync.vue             # 数据同步设置
    │   ├── LogViewer.vue            # 系统日志查看
    │   ├── Monitor.vue              # 系统监控面板
    │   ├── Settings.vue             # 系统设置
    │   └── UserManagement.vue       # 用户管理
    │
    └── Trade/                       # 交易执行页面
        ├── AccountManagement.vue    # 账户管理
        ├── OrderHistory.vue         # 订单历史
        ├── OrderManagement.vue      # 订单管理
        ├── Position.vue             # 持仓查看
        ├── PositionManagement.vue   # 持仓管理
        ├── TradeExecution.vue       # 交易执行
        └── TradingCockpit.vue       # 交易驾驶舱主页面
```