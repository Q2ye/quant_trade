<template>
  <!--
    根容器 — 透明背景，让 MainLayout 的 bg-gradient-mesh 和 3D 粒子背景透出
  -->
  <div class="dashboard-overview scrollbar-hide">

    <!-- ========================================================================
        状态一：Loading（数据加载中）
        使用 Naive UI n-skeleton 展示 4 列占位骨架卡片
        tokens.motion.stagger → stagger-item：fadeInUp 入场动画，每卡片递增 delay
    ============================================================================ -->
    <template v-if="loading">
      <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="4"
          responsive="screen"
          class="overview-grid"
      >
        <n-grid-item
            v-for="i in 4"
            :key="i"
            :class="tokens.motion.stagger"
            :style="{ animationDelay: `${(i - 1) * 0.08}s` }"
        >
          <n-card>
            <n-skeleton :text="true" :repeat="3"/>
          </n-card>
        </n-grid-item>
      </n-grid>
    </template>

    <!-- ========================================================================
        状态二：Error（数据加载失败）
        Naive UI n-result 展示 500 错误页 + 重试按钮
    ============================================================================ -->
    <n-result
        v-else-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
    >
      <template #footer>
        <n-button type="primary" @click="retry">重试</n-button>
      </template>
    </n-result>

    <!-- ========================================================================
        状态三：Data（正常数据展示）
        由上到下分为三个区域：顶部概览指标 / 中部图表+信号 / 底部列表
    ============================================================================ -->
    <template v-else>

      <!-- =====================================================================
          Page Header — 统一页面头部（与 MarketOverview 共享 .page-header 模式）
      ====================================================================== -->
      <div class="page-header">
        <div class="header-content">
          <div class="title-section">
            <h1 class="page-title">总览</h1>
            <p class="page-description">量化交易驾驶舱 — 资产概览、实时信号、持仓与成交监控</p>
          </div>
        </div>
      </div>

      <div class="main-content">

      <!-- =====================================================================
          区域一：顶部概览区 —— 4 列指标卡片
          tokens.motion.stagger：每卡片递增 0.08s 的 fadeInUp 入场动画
          tokens.surface.card → card-surface：Naive UI CSS 变量驱动的卡片背景/边框/阴影
          tokens.motion.hover → hover-lift：hover 时 scale(1.02)
      ====================================================================== -->
      <div class="content-section">
      <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="4"
          responsive="screen"
          class="overview-grid"
      >
        <!-- 卡片 1：总资产（含日盈亏） -->
        <n-grid-item
            :class="tokens.motion.stagger"
            :style="{ animationDelay: '0s' }"
        >
          <n-card
              :class="[tokens.surface.card, tokens.motion.hover, 'metric-card']"
          >
            <div class="metric-value">
              ¥ {{ formatNumber(accountInfo.totalAsset) }}
            </div>
            <div class="metric-label">总资产</div>
            <div
                class="metric-change"
                :class="getChangeClass(accountInfo.dailyPnl)"
            >
              {{
                accountInfo.dailyPnl > 0 ? "+" : ""
              }}{{ formatNumber(accountInfo.dailyPnl) }} ({{
                accountInfo.dailyReturn
              }}%)
            </div>
          </n-card>
        </n-grid-item>

        <!-- 卡片 2：可用资金 -->
        <n-grid-item
            :class="tokens.motion.stagger"
            :style="{ animationDelay: '0.08s' }"
        >
          <n-card
              :class="[tokens.surface.card, tokens.motion.hover, 'metric-card']"
          >
            <div class="metric-value">
              ¥ {{ formatNumber(accountInfo.cash) }}
            </div>
            <div class="metric-label">可用资金</div>
          </n-card>
        </n-grid-item>

        <!-- 卡片 3：持仓品种数 -->
        <n-grid-item
            :class="tokens.motion.stagger"
            :style="{ animationDelay: '0.16s' }"
        >
          <n-card
              :class="[tokens.surface.card, tokens.motion.hover, 'metric-card']"
          >
            <div class="metric-value">
              {{ formatNumber(accountInfo.positionsCount) }}
            </div>
            <div class="metric-label">持仓品种</div>
          </n-card>
        </n-grid-item>

        <!-- 卡片 4：运行中策略数 -->
        <n-grid-item
            :class="tokens.motion.stagger"
            :style="{ animationDelay: '0.24s' }"
        >
          <n-card
              :class="[tokens.surface.card, tokens.motion.hover, 'metric-card']"
          >
            <div class="metric-value">
              {{ formatNumber(accountInfo.activeStrategies) }}
            </div>
            <div class="metric-label">运行中策略</div>
          </n-card>
        </n-grid-item>
      </n-grid>
      </div>

      <!-- =====================================================================
          区域二：中部图表 + 信号区 —— 3 列网格（图表占 2 列，信号占 1 列）
          图表：ECharts 初始化在 equityChartRef 绑定的 div 上
          信号列表：最近交易信号，买卖方向区分颜色和图标
      ====================================================================== -->
      <div class="content-section">
      <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="3"
          responsive="screen"
          class="dashboard-widgets"
      >
        <!-- 左：组合绩效图表（占 2/3 宽度），带日/周/月/年切换 -->
        <n-grid-item :span="2" :class="tokens.motion.stagger" :style="{ animationDelay: '0.32s' }">
          <n-card :class="[tokens.surface.card, 'widget-card']">
            <template #header>
              <div class="widget-header">
                <span>组合绩效</span>
                <!-- 图表时间范围切换：Naive UI n-radio-group -->
                <n-radio-group v-model:value="chartRange" size="small">
                  <n-radio-button value="1D" label="日"/>
                  <n-radio-button value="1W" label="周"/>
                  <n-radio-button value="1M" label="月"/>
                  <n-radio-button value="1Y" label="年"/>
                </n-radio-group>
              </div>
            </template>
            <!-- ECharts 挂载点，通过 ref 绑定 -->
            <div ref="equityChartRef" class="chart-container"></div>
          </n-card>
        </n-grid-item>

        <!-- 右：实时信号列表（占 1/3 宽度） -->
        <n-grid-item :span="1" :class="tokens.motion.stagger" :style="{ animationDelay: '0.40s' }">
          <n-card :class="[tokens.surface.card, 'widget-card']">
            <template #header><span>实时信号</span></template>
            <!-- 空状态 -->
            <n-empty v-if="recentSignals.length === 0" description="暂无信号"/>
            <!-- 信号列表 -->
            <div v-else class="signal-list scrollbar-hide">
              <div
                  v-for="(signal, index) in recentSignals"
                  :key="index"
                  class="signal-item"
              >
                <!-- 方向图标：buy → 红色向上箭头，sell → 绿色向下箭头 -->
                <div class="signal-icon" :class="signal.direction">
                  <Icon
                      :icon="
                      signal.direction === 'buy'
                        ? 'ant-design:arrow-up-outlined'
                        : 'ant-design:arrow-down-outlined'
                    "
                  />
                </div>
                <div class="signal-content">
                  <div class="signal-name">{{ signal.name }}</div>
                  <div class="signal-symbol">{{ signal.symbol }}</div>
                </div>
                <div class="signal-price" :class="signal.direction">
                  {{ signal.price }}
                </div>
              </div>
            </div>
          </n-card>
        </n-grid-item>
      </n-grid>
      </div>

      <!-- =====================================================================
          区域三：底部列表区 —— 2 列（持仓列表 | 今日成交）
          空数据时展示 n-empty，有数据时渲染 n-data-table
      ====================================================================== -->
      <div class="content-section">
      <n-grid
          :x-gap="20"
          :y-gap="20"
          :cols="2"
          responsive="screen"
          class="dashboard-tables"
      >
        <!-- 左：持仓列表，含盈亏颜色渲染和权重百分比 -->
        <n-grid-item :class="tokens.motion.stagger" :style="{ animationDelay: '0.48s' }">
          <n-card title="持仓列表" :class="[tokens.surface.card, 'table-card']">
            <n-empty v-if="positions.length === 0" description="暂无持仓"/>
            <n-data-table
                v-else
                :columns="positionColumns"
                :data="positions"
                :max-height="250"
                :bordered="false"
                size="small"
            />
          </n-card>
        </n-grid-item>

        <!-- 右：今日成交，方向列用 n-tag 红/绿区分买卖 -->
        <n-grid-item :class="tokens.motion.stagger" :style="{ animationDelay: '0.56s' }">
          <n-card title="今日成交" :class="[tokens.surface.card, 'table-card']">
            <n-empty v-if="todayTrades.length === 0" description="今日无成交"/>
            <n-data-table
                v-else
                :columns="tradeColumns"
                :data="todayTrades"
                :max-height="250"
                :bordered="false"
                size="small"
            />
          </n-card>
        </n-grid-item>
      </n-grid>
      </div>

      </div><!-- .main-content -->

    </template>
  </div>
</template>

<script setup lang="ts">
// ============================================================================
// 依赖导入
// ============================================================================

// Vue 3 Composition API：响应式核心 + 生命周期钩子
import {h, onMounted, onUnmounted, reactive, ref} from "vue";
// Naive UI 组件：NTag 用于表格中"买/卖"标签渲染
import {NTag} from "naive-ui";
// Iconify 图标组件（全局注册为 <Icon>，buy/sell 箭头）
import {Icon} from "@iconify/vue";
// ECharts 图表库：用于组合绩效曲线
import * as echarts from "echarts";
// API 层：获取仪表盘数据和绩效图表数据
import {getDashboardData, getPerformanceChart} from "@/api/dashboard";
// 工具函数：数字格式化（千分位 + 小数位数）
import {formatNumber} from "@/utils/number";
// 设计 Token：surface（背景/卡片）、motion（动效）等 class 映射
import {tokens} from "@/styles/design-tokens";

// ============================================================================
// Mock 开关 —— 设为 true 使用模拟数据预览 UI，false 走真实 API
// ============================================================================

/** 开发调试：true=使用模拟数据（无需后端），false=调用真实 API */
const USE_MOCK = true;

/**
 * 生成模拟账户概览数据
 * 模拟一个 ~100 万的中等规模量化组合
 */
const getMockAccountInfo = () => ({
  totalAsset: 1234567.89,    // 总资产 ~123 万
  cash: 345678.90,           // 可用资金 ~34.5 万（仓位约 72%）
  dailyPnl: 12580.50,        // 当日盈利 +1.25 万
  dailyReturn: 1.25,         // 当日收益率 +1.25%
  positionsCount: 8,         // 持仓 8 只
  activeStrategies: 3,       // 运行中策略：CTA趋势 / 均值回归 / AI选股
});

/**
 * 生成模拟实时信号
 * 包含买入/卖出两类，覆盖不同策略和品种
 */
const getMockSignals = () => [
  { name: "均线金叉突破",   symbol: "000001.SZ", direction: "buy",  price: 13.45 },
  { name: "RSI超卖反弹",    symbol: "600519.SH", direction: "buy",  price: 1856.00 },
  { name: "MACD顶背离",     symbol: "300750.SZ", direction: "sell", price: 208.50 },
  { name: "布林带上轨触及", symbol: "000858.SZ", direction: "sell", price: 168.80 },
  { name: "放量突破前高",   symbol: "002594.SZ", direction: "buy",  price: 268.00 },
];

/**
 * 生成模拟持仓列表
 * 权重总和 ≈ 100%，含正负盈亏
 */
const getMockPositions = () => [
  { symbol: "600519.SH", name: "贵州茅台",   quantity: 200,   price: 1856.00, pnl: 12400.00,  weight: 0.30 },
  { symbol: "000858.SZ", name: "五粮液",     quantity: 1500,  price: 168.80,  pnl: -3200.00,  weight: 0.20 },
  { symbol: "300750.SZ", name: "宁德时代",   quantity: 800,   price: 208.50,  pnl: 5600.00,   weight: 0.13 },
  { symbol: "002594.SZ", name: "比亚迪",     quantity: 500,   price: 268.00,  pnl: 8500.00,   weight: 0.11 },
  { symbol: "000001.SZ", name: "平安银行",   quantity: 3000,  price: 13.45,   pnl: -1500.00,  weight: 0.08 },
  { symbol: "601318.SH", name: "中国平安",   quantity: 1200,  price: 52.30,   pnl: 2400.00,   weight: 0.07 },
  { symbol: "600036.SH", name: "招商银行",   quantity: 1800,  price: 42.15,   pnl: -890.00,   weight: 0.06 },
  { symbol: "300059.SZ", name: "东方财富",   quantity: 2000,  price: 24.80,   pnl: 3200.00,   weight: 0.05 },
];

/**
 * 生成模拟今日成交
 * 买卖混合，时间分布在 9:30-15:00 交易时段
 */
const getMockTrades = () => [
  { time: "09:32:15", symbol: "600519.SH", direction: "buy",  price: 1851.50, volume: 100, amount: 185150.00 },
  { time: "10:15:42", symbol: "000858.SZ", direction: "sell", price: 169.20,  volume: 300, amount: 50760.00  },
  { time: "11:05:18", symbol: "300750.SZ", direction: "buy",  price: 207.80,  volume: 200, amount: 41560.00  },
  { time: "13:08:33", symbol: "002594.SZ", direction: "buy",  price: 266.50,  volume: 100, amount: 26650.00  },
  { time: "14:22:07", symbol: "000001.SZ", direction: "sell", price: 13.52,   volume: 500, amount: 6760.00   },
  { time: "14:55:29", symbol: "300059.SZ", direction: "buy",  price: 24.75,   volume: 500, amount: 12375.00  },
];

/**
 * 生成模拟绩效图表数据
 * 生成 30 个交易日（约 1 月）的策略 vs 基准累计收益率
 * 模拟策略略跑赢基准的场景
 */
const getMockChartData = () => {
  const dates: string[] = [];
  const strategyReturns: number[] = [];
  const benchmarkReturns: number[] = [];

  // 从 30 天前开始，排除周末生成约 22 个交易日
  const tradingDays = 22;
  let strategyCum = 0;
  let benchmarkCum = 0;

  for (let i = 0; i < tradingDays; i++) {
    // 日期回溯
    const d = new Date();
    d.setDate(d.getDate() - (tradingDays - 1 - i) * 1.4); // 1.4 天间隔模拟跳过周末
    dates.push(`${d.getMonth() + 1}/${d.getDate()}`);

    // 每日随机波动 ±2%，策略有 0.05% 的 alpha 优势
    const marketMove = (Math.random() - 0.48) * 1.5;       // 基准波动，略微偏正
    const alpha = 0.05 + (Math.random() - 0.5) * 0.1;       // 策略超额收益
    benchmarkCum += marketMove;
    strategyCum += marketMove + alpha;

    benchmarkReturns.push(parseFloat(benchmarkCum.toFixed(2)));
    strategyReturns.push(parseFloat(strategyCum.toFixed(2)));
  }

  return { dates, strategyReturns, benchmarkReturns };
};

// ============================================================================
// 状态定义
// ============================================================================

/** 页面级 Loading 状态，true 时展示骨架屏 */
const loading = ref(true);
/** 页面级 Error 状态，true 时展示 500 错误结果页 */
const error = ref(false);
/** 图表时间范围：1D | 1W | 1M | 1Y，绑定到 n-radio-group */
const chartRange = ref("1M");

/**
 * 账户概览信息 —— 顶部 4 张指标卡片的数据源
 * 使用 reactive 而非 ref，方便 loadDashboardData 中 Object.assign 整包覆盖
 */
const accountInfo = reactive({
  totalAsset: 0,       // 总资产（元）
  cash: 0,             // 可用资金（元）
  dailyPnl: 0,         // 当日盈亏（元）
  dailyReturn: 0,      // 当日收益率（%）
  positionsCount: 0,   // 持仓品种数量
  activeStrategies: 0, // 运行中策略数量
});

/** 实时信号列表：名称、代码、买卖方向、价格 */
const recentSignals = ref<
    { name: string; symbol: string; direction: string; price: number }[]
>([]);
/** 持仓列表，渲染到 n-data-table */
const positions = ref<any[]>([]);
/** 今日成交列表，渲染到 n-data-table */
const todayTrades = ref<any[]>([]);

// ============================================================================
// ECharts 图表
// ============================================================================

/** ECharts 挂载 DOM 元素的模板引用 */
const equityChartRef = ref<HTMLElement | null>(null);
/** ECharts 实例，onUnmounted 时 dispose */
let equityChart: echarts.ECharts | null = null;
/** 窗口 resize 时重新计算图表尺寸，避免变形 */
const handleEquityResize = () => equityChart?.resize();

// ============================================================================
// 表格列定义
// ============================================================================

/**
 * 持仓列表列定义
 * 盈亏列：正数红色（var(--color-stock-up)），负数绿色（var(--color-stock-down)）
 * 权重列：小数 → 百分比显示
 */
const positionColumns = [
  {title: "代码", key: "symbol", width: 90},
  {title: "名称", key: "name", width: 130},
  {title: "数量", key: "quantity", width: 80, align: "right" as const},
  {
    title: "当前价",
    key: "price",
    width: 100,
    align: "right" as const,
    render: (row: any) => formatNumber(row.price, 2),
  },
  {
    title: "盈亏",
    key: "pnl",
    width: 100,
    align: "right" as const,
    // 盈亏列自定义渲染：使用 h() 创建 span，根据正负值动态着色
    render: (row: any) =>
        h(
            "span",
            {
              style: {
                color:
                    row.pnl >= 0
                        ? "var(--color-stock-up)"   // 盈利：红色（中国习惯红涨）
                        : "var(--color-stock-down)", // 亏损：绿色（中国习惯绿跌）
              },
            },
            `${row.pnl >= 0 ? "+" : ""}${formatNumber(row.pnl, 2)}`,
        ),
  },
  {
    title: "权重",
    key: "weight",
    width: 80,
    align: "right" as const,
    // 权重存储为小数（0.25），展示为百分比（25.0%）
    render: (row: any) => `${formatNumber(row.weight * 100, 1)}%`,
  },
];

/**
 * 今日成交列定义
 * 方向列：用 Naive UI n-tag 组件渲染，"买"→红色(error)，"卖"→绿色(success)
 * 金额列：formatNumber 千分位保留 2 位小数
 */
const tradeColumns = [
  {title: "时间", key: "time", width: 100},
  {title: "代码", key: "symbol", width: 90},
  {
    title: "方向",
    key: "direction",
    width: 60,
    // 方向列自定义渲染：使用 h() 创建 NTag 组件
    render: (row: any) =>
        h(
            NTag,
            {
              type: row.direction === "buy" ? "error" : "success", // error=红, success=绿
              size: "small",
              bordered: false,
            },
            {default: () => (row.direction === "buy" ? "买" : "卖")},
        ),
  },
  {
    title: "价格",
    key: "price",
    width: 90,
    align: "right" as const,
    render: (row: any) => formatNumber(row.price, 2), // 保留 2 位小数
  },
  {
    title: "数量",
    key: "volume",
    width: 80,
    align: "right" as const,
    render: (row: any) => formatNumber(row.volume), // 整数千分位
  },
  {
    title: "金额",
    key: "amount",
    width: 100,
    align: "right" as const,
    render: (row: any) => formatNumber(row.amount, 2), // 保留 2 位小数
  },
];

// ============================================================================
// 方法
// ============================================================================

/**
 * 初始化 ECharts 组合绩效图表
 * 配置：
 *   - tooltip: 十字准星交叉指示器
 *   - xAxis: 类目轴（日期），无边界间隙
 *   - yAxis: 数值轴，百分比格式化
 *   - series: 两条堆叠面积线（策略收益 / 基准收益）
 * 异常处理：chart init 失败为非致命错误，仅静默吞掉
 */
const initChart = async () => {
  if (!equityChartRef.value) return;
  // 在绑定的 DOM 元素上初始化 ECharts 实例
  equityChart = echarts.init(equityChartRef.value);
  try {
    // 请求后端图表数据（dates[], strategyReturns[], benchmarkReturns[]）
    // USE_MOCK 时使用本地生成的模拟收益率曲线
    const response = USE_MOCK
        ? getMockChartData()
        : await getPerformanceChart(chartRange.value);
    // 设置 ECharts 配置项
    equityChart.setOption({
      tooltip: {
        trigger: "axis",                                        // 坐标轴触发
        axisPointer: {type: "cross", label: {backgroundColor: "#6a7985"}}, // 十字准星 + 深灰标签背景
      },
      grid: {left: "3%", right: "4%", bottom: "3%", containLabel: true}, // 网格边距，containLabel 防止标签溢出
      xAxis: {
        type: "category",                                       // 类目轴（日期字符串）
        boundaryGap: false,                                     // 无边界间隙，折线贴边
        data: response.dates,                                   // 横轴日期数组
      },
      yAxis: {type: "value", axisLabel: {formatter: "{value}%"}}, // 数值轴 + 百分号后缀
      series: [
        {
          name: "策略收益",
          type: "line",
          stack: "总量",                                        // 堆叠分组名，两条线共享此分组
          areaStyle: {},                                        // 填充面积区域
          data: response.strategyReturns,                       // 策略收益率数组
        },
        {
          name: "基准收益",
          type: "line",
          stack: "总量",                                        // 同堆叠组，便于对比
          areaStyle: {},
          data: response.benchmarkReturns,                      // 基准收益率数组
        },
      ],
    });
  } catch {
    /* chart init failure is non-fatal — 图表失败不影响其他数据展示 */
  }
};

/**
 * 加载仪表盘全部数据
 * 调用 getDashboardData API，将返回数据填充到 accountInfo / recentSignals / positions / todayTrades
 * 异常：设置 error=true，触发全局 n-result 错误页
 */
const loadDashboardData = async () => {
  loading.value = true;
  error.value = false;
  try {
    // USE_MOCK 时直接使用本地模拟数据，方便前端独立开发调试
    if (USE_MOCK) {
      // 模拟网络延迟 400-800ms，让骨架屏有短暂的可见时间
      await new Promise(r => setTimeout(r, 400 + Math.random() * 400));
      Object.assign(accountInfo, getMockAccountInfo());
      recentSignals.value = getMockSignals();
      positions.value = getMockPositions();
      todayTrades.value = getMockTrades();
    } else {
      const response = await getDashboardData();
      Object.assign(accountInfo, response.accountInfo);
      recentSignals.value = response.recentSignals;
      positions.value = response.positions;
      todayTrades.value = response.todayTrades;
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

/** 重试按钮回调：重新加载全部数据 */
const retry = () => loadDashboardData();

/**
 * 根据盈亏数值返回 CSS class 名称
 * @param value 盈亏数值
 * @returns "positive"（红涨）或 "negative"（绿跌）
 */
const getChangeClass = (value: number) =>
    value >= 0 ? "positive" : "negative";

// ============================================================================
// 生命周期
// ============================================================================

onMounted(() => {
  loadDashboardData();                                  // 页面挂载：加载仪表盘数据
  initChart();                                          // 初始化 ECharts 图表
  window.addEventListener("resize", handleEquityResize); // 监听窗口大小变化以重绘图表
});

onUnmounted(() => {
  window.removeEventListener("resize", handleEquityResize); // 移除 resize 监听
  equityChart?.dispose();                                   // 销毁 ECharts 实例释放内存
});
</script>

<style lang="scss" scoped>
/*
 * ============================================================================
 * Dashboard Overview 页面样式
 *
 * 样式分层：
 *   第一层 — 页面容器（dashboard-overview）
 *   第二层 — 顶部概览指标卡片（overview-grid / metric-card）
 *   第三层 — 中部图表+信号区（dashboard-widgets / widget-card / chart-container / signal-list）
 *   第四层 — 底部数据表格区（dashboard-tables / table-card）
 *
 * 系统样式使用说明：
 *   - 模板中已通过 tokens.surface.* / tokens.motion.* 引用全局 class（bg-gradient-mesh,
 *     card-surface, hover-lift, stagger-item），对应 CSS 定义在 styles/global.scss
 *     的"设计Token CSS落地层"
 *   - 颜色值优先使用 Naive UI CSS 变量（var(--n-*)）和项目 CSS 变量（var(--color-*)）
 *   - 以下 style 中的自定义规则仅用于系统 class 无法覆盖的布局/尺寸/微调场景
 * ============================================================================
 */

/* ==========================================================================
   第一层：页面容器
   ========================================================================== */

.dashboard-overview {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;

  /*
   * Naive UI n-card 半透明背景
   *
   * --n-color 是 n-card 背景色的 CSS 变量源，内联注入在 <div class="n-card"> 上。
   * 必须用 !important 覆盖内联 style，让组件自身的 background-color 失效，
   * 再铺上项目自定义的半透明背景。
   *
   * 同时覆盖 header/content/footer/action 区域，防止这些子区域持有独立的实色背景。
   */
  :deep(.n-card) {
    --n-color: transparent !important;
    background: var(--color-bg-card, rgba(12, 18, 32, 0.72)) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);

    > .n-card-header,
    > .n-card__content,
    > .n-card-footer,
    > .n-card-action {
      background: transparent !important;
    }

    /* 卡片内容区裁剪溢出，防止表格超出卡片边界 */
    > .n-card__content {
      overflow: hidden;
    }
  }
}

/* ==========================================================================
   第二层：顶部概览区 —— 4 列指标卡片
   ========================================================================== */

/*
 * 概览网格底部间距
 * 20px = spacer(5)，与 n-grid 的 y-gap="20" 保持一致
 * 系统等效：mb-5 工具类，但此处与 n-grid 组件级 gap 配合，直接在容器上设置更清晰
 */
.overview-grid {
  /* margin-bottom 由父级 .content-section 提供 */
}

/*
 * 指标卡片内部样式
 * 模板中已通过 tokens.surface.card + tokens.motion.hover 引用全局卡片表面和 hover 动效
 * 此处仅补充指标卡特有的文本布局和颜色
 */
.metric-card {
  text-align: center;   /* 所有内容水平居中（等价于全局 text-center 工具类） */

  /*
   * 指标数值（如"¥ 1,234,567"）
   * 24px 粗体，使用 Naive UI 一级文字色，确保主题切换时颜色自动适配
   */
  .metric-value {
    font-size: 24px;                  /* 大号字体，突出展示核心数据 */
    font-weight: bold;                /* 粗体强调 */
    margin-bottom: 8px;               /* spacer(2)：数值与标签之间的标准小间距 */
    color: var(--n-text-color-1);     /* 系统：Naive UI 一级文字色，跟随主题切换 */
  }

  /*
   * 指标标签（如"总资产"、"可用资金"）
   * 使用 Naive UI 三级文字色（次级信息色），字号跟随全局基础字体大小
   */
  .metric-label {
    color: var(--n-text-color-3);     /* 系统：Naive UI 三级文字色（次要信息） */
    margin-bottom: 8px;               /* spacer(2)：标签与涨跌幅之间的标准小间距 */
  }

  /*
   * 涨跌幅（仅总资产卡片显示）
   * 14px = $font-size-base，全局基础字号
   */
  .metric-change {
    font-size: 14px;                  /* 系统等效：$font-size-base，全局基础字体大小 */

    /*
     * positive（盈利）/ negative（亏损）颜色
     * 映射关系（中国股市习惯）：
     *   positive → 红色 #f56c6c → var(--color-stock-up)    → 上涨
     *   negative → 绿色 #67c23a → var(--color-stock-down)  → 下跌
     * 注意：此处使用硬编码 fallback 值，确保 JS 注入 CSS 变量失败时仍有可用颜色
     */
    &.positive {
      color: var(--color-stock-up, #f56c6c);    /* 系统变量 + 硬编码 fallback */
    }

    &.negative {
      color: var(--color-stock-down, #67c23a);  /* 系统变量 + 硬编码 fallback */
    }
  }
}

/* ==========================================================================
   第三层：中部图表 + 信号区
   ========================================================================== */

/*
 * dashboard-widgets 区域底部间距
 * 20px = spacer(5)，与 overview-grid 保持一致
 */
.dashboard-widgets {
  /* margin-bottom 由父级 .content-section 提供 */
}

/*
 * 图表/信号卡片（widget-card）
 * 模板中已通过 tokens.surface.card 引用 card-surface 全局 class
 * 此处补充 widget 卡片特有的头部布局和图表容器尺寸
 */
.widget-card {
  /*
   * 卡片头部：标题在左，操作控件（如时间范围 radio-group）在右
   * 等价于全局 flex-between 工具类，但因嵌套在 n-card header slot 中，直接定义更精确
   */
  .widget-header {
    display: flex;                  /* 弹性布局 */
    justify-content: space-between; /* 两端对齐：标题左、控件右 */
    align-items: center;            /* 垂直居中 */
  }

  /*
   * ECharts 图表容器
   * 高度 250px 为固定值，与右侧信号列表高度一致，保持视觉对齐
   */
  .chart-container {
    height: 250px;  /* 固定高度，与信号列表 .signal-list 的 250px 对齐 */
    width: 100%;    /* 填满卡片内容区宽度 */
  }
}

/*
 * 信号列表容器
 * 固定高度 + 垂直滚动，与左侧图表高度保持一致
 */
.signal-list {
  height: 250px;      /* 固定高度，与图表 .chart-container 的 250px 对齐 */
  overflow-y: auto;   /* 信号超出可滚动（等价于全局 overflow-y-auto 工具类） */

  /*
   * 单条信号项
   * Flex 行布局：方向图标 | 信号名称+代码 | 价格
   */
  .signal-item {
    display: flex;        /* 弹性布局：图标、内容、价格水平排列 */
    align-items: center;  /* 垂直居中对齐 */
    padding: 10px 0;      /* 上下 10px 内边距，左右无内边距（由父容器控制） */
    border-bottom: 1px solid var(--n-border-color); /* 系统：Naive UI 边框色，底部分割线 */

    /* 最后一项不显示底部分割线 */
    &:last-child {
      border-bottom: none;
    }

    /*
     * 方向图标容器（圆形背景）
     * 32×32px 圆形，flex 居中图标，右侧 12px 间距
     */
    .signal-icon {
      width: 32px;              /* 图标容器宽 */
      height: 32px;             /* 图标容器高 */
      border-radius: 50%;       /* 正圆形 */
      display: flex;            /* Flex 居中图标 */
      align-items: center;
      justify-content: center;
      margin-right: 12px;       /* spacer(3)：图标与文本内容的间距 */

      /*
       * buy 方向样式：红色系的半透明背景 + 红色图标
       * rgba(245,108,108,0.1) = 10% 不透明度的红色背景
       * #f56c6c = 红色前景图标 → 映射 var(--color-stock-up)
       */
      &.buy {
        background: rgba(245, 108, 108, 0.1); /* 10% 红色背景，系统等效：color-with-opacity(var(--color-stock-up), 0.1) */
        color: #f56c6c;                       /* 红色图标 → var(--color-stock-up) 对应值 */
      }

      /*
       * sell 方向样式：绿色系的半透明背景 + 绿色图标
       * rgba(103,194,58,0.1) = 10% 不透明度的绿色背景
       * #67c23a = 绿色前景图标 → 映射 var(--color-stock-down)
       */
      &.sell {
        background: rgba(103, 194, 58, 0.1); /* 10% 绿色背景，系统等效：color-with-opacity(var(--color-stock-down), 0.1) */
        color: #67c23a;                      /* 绿色图标 → var(--color-stock-down) 对应值 */
      }
    }

    /*
     * 信号文字内容区（flex: 1 占满剩余空间）
     */
    .signal-content {
      flex: 1;  /* 弹性填充，占据图标和价格之间的剩余宽度 */

      /*
       * 信号名称（如"均线金叉"、"MACD底背离"）
       * 14px 一级文字色
       */
      .signal-name {
        font-size: 14px;                  /* 系统等效：$font-size-base */
        color: var(--n-text-color-1);     /* 系统：Naive UI 一级文字色 */
        margin-bottom: 4px;               /* spacer(1)：名称与代码之间的最小间距 */
      }

      /*
       * 信号对应股票代码（如"000001.SZ"）
       * 12px 三级文字色（次要信息）
       */
      .signal-symbol {
        font-size: 12px;                  /* 小号字体 */
        color: var(--n-text-color-3);     /* 系统：Naive UI 三级文字色（次要） */
      }
    }

    /*
     * 信号价格（右对齐，加粗）
     * 颜色跟随买卖方向
     */
    .signal-price {
      font-weight: bold;  /* 加粗强调价格 */

      &.buy {
        color: #f56c6c;   /* 红色 → var(--color-stock-up) */
      }

      &.sell {
        color: #67c23a;   /* 绿色 → var(--color-stock-down) */
      }
    }
  }
}

/* ==========================================================================
   第四层：底部数据表格区 —— 2 列（持仓列表 | 今日成交）
   ========================================================================== */

/*
 * Naive UI n-data-table 透明化 + 隐藏内部滚动条
 * n-data-table 自身有 --n-td-color / --n-th-color 等 CSS 变量控制背景色，
 * 必须穿透覆盖才能与半透明卡片融合。
 */
:deep(.n-data-table) {
  --n-td-color: transparent !important;
  --n-th-color: transparent !important;
  --n-merged-th-color: transparent !important;
  background: transparent !important;

  /* n-data-table 的 max-height 会在内部创建一个滚动容器（.n-data-table-base-table-body），隐藏其滚动条 */
  .n-data-table-base-table-body {
    scrollbar-width: none;
    -ms-overflow-style: none;
    &::-webkit-scrollbar {
      display: none;
    }
  }
}

/*
 * Naive UI n-empty 透明化（卡片内的空状态提示）
 * n-empty 使用 --n-color 或自身背景，重置为透明让卡片背景透出。
 */
:deep(.n-empty) {
  --n-color: transparent !important;
  background: transparent !important;
}

.dashboard-tables {
  /*
   * 表格卡片固定高度
   * 320px = 表头(~36px) + 250px 数据区(max-height) + padding
   * 保证两张表底部对齐
   */
  .table-card {
    height: 320px;
    overflow: hidden;
  }
}
</style>
