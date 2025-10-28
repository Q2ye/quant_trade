<!--MarketOverview.vue-->
<!--重构后的市场概览页面 - 基于交易系统主题实现-->
<!--移除了重复样式，统一使用主题样式系统-->
<template>
  <div class="market-overview-page sidebar-layout-container no-bleed-through">
    <!-- 页面标题和状态 - 使用全局主题样式 -->
    <div class="market-page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场概览</h1>
          <p class="page-description">实时监控市场指数、资金流向和热点板块，掌握市场动态</p>
        </div>
        <div class="header-actions">
          <el-button class="refresh-btn" @click="refreshData">
            <Icon icon="ant-design:reload-outlined"/>
            <span class="btn-text">刷新数据</span>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 市场指数概览 - 使用状态卡片布局 -->
      <div class="index-overview">
        <h2 class="market-section-title">
          <Icon icon="mdi:chart-line" class="title-icon"/>
          主要指数
        </h2>
        <div class="market-index-grid">
          <el-card class="market-index-card" shadow="hover">
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">上证指数</div>
                <div class="index-code">000001</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.shanghai)">
                  <Icon icon="mdi:trending-up"/>
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.shanghai.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.shanghai)">
                    <span class="change-value">{{ formatChange(indexData.shanghai.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.shanghai.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </el-card>

          <el-card class="market-index-card" shadow="hover">
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">深证成指</div>
                <div class="index-code">399001</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.shenzhen)">
                  <Icon icon="mdi:chart-areaspline"/>
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.shenzhen.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.shenzhen)">
                    <span class="change-value">{{ formatChange(indexData.shenzhen.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.shenzhen.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </el-card>

          <el-card class="market-index-card" shadow="hover">
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">创业板指</div>
                <div class="index-code">399006</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.chuangye)">
                  <Icon icon="mdi:rocket-launch"/>
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.chuangye.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.chuangye)">
                    <span class="change-value">{{ formatChange(indexData.chuangye.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.chuangye.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </el-card>

          <el-card class="market-index-card" shadow="hover">
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">科创50</div>
                <div class="index-code">000688</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.kechuang50)">
                  <Icon icon="mdi:chip"/>
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.kechuang50.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.kechuang50)">
                    <span class="change-value">{{ formatChange(indexData.kechuang50.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.kechuang50.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 功能导航卡片 - 使用核心功能网格布局 -->
      <div class="function-nav">
        <h2 class="market-section-title">
          <Icon icon="mdi:apps" class="title-icon"/>
          功能导航
        </h2>

        <div class="function-grid">
          <!-- 股票市场 -->
          <el-card class="function-nav-card" shadow="hover" @click="navigateTo('/market/stocks')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon accent">
                  <Icon icon="mdi:chart-bar"/>
                </div>
                <h3 class="function-title">股票市场</h3>
              </div>
              <div class="function-info">
                <p class="function-description">A股全市场股票行情数据</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">上涨:</span>
                    <span class="stat-value up">{{ stockStats.riseCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">下跌:</span>
                    <span class="stat-value down">{{ stockStats.fallCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">平盘:</span>
                    <span class="stat-value flat">{{ stockStats.flatCount }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">更新: {{ stockStats.updateTime }}</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>

          <!-- ETF基金 -->
          <el-card class="function-nav-card" shadow="hover" @click="navigateTo('/market/etfs')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon success">
                  <Icon icon="mdi:finance"/>
                </div>
                <h3 class="function-title">ETF基金</h3>
              </div>
              <div class="function-info">
                <p class="function-description">交易所交易基金数据</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">股票ETF:</span>
                    <span class="stat-value">{{ etfStats.stockETF }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">债券ETF:</span>
                    <span class="stat-value">{{ etfStats.bondETF }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">商品ETF:</span>
                    <span class="stat-value">{{ etfStats.commodityETF }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">总规模: {{ etfStats.totalAmount }}亿</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 指数行情 -->
          <el-card class="function-nav-card" shadow="hover" @click="navigateTo('/market/indexes')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon warning">
                  <Icon icon="mdi:chart-timeline"/>
                </div>
                <h3 class="function-title">指数行情</h3>
              </div>
              <div class="function-info">
                <p class="function-description">主要市场指数表现</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">宽基指数:</span>
                    <span class="stat-value">{{ indexStats.broadIndex }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">行业指数:</span>
                    <span class="stat-value">{{ indexStats.industryIndex }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">策略指数:</span>
                    <span class="stat-value">{{ indexStats.strategyIndex }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">{{ indexStats.riseCount }}/{{ indexStats.totalCount }}上涨</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 行业强弱 -->
          <el-card class="function-nav-card" shadow="hover" @click="navigateTo('/market/industry-strength')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon purple">
                  <Icon icon="mdi:chart-tree"/>
                </div>
                <h3 class="function-title">行业强弱</h3>
              </div>
              <div class="function-info">
                <p class="function-description">行业强弱与趋势分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">领涨行业:</span>
                    <span class="stat-value up">{{ industryStats.topIndustry.name }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">涨幅:</span>
                    <span class="stat-value up">{{ industryStats.topIndustry.change }}%</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">领跌行业:</span>
                    <span class="stat-value down">{{ industryStats.bottomIndustry.name }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">{{ industryStats.riseCount }}/{{ industryStats.totalCount }}行业上涨</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 资金流向 -->
          <el-card class="function-nav-card" shadow="hover" @click="navigateTo('/market/money-flow')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon info">
                  <Icon icon="mdi:cash-multiple"/>
                </div>
                <h3 class="function-title">资金流向</h3>
              </div>
              <div class="function-info">
                <p class="function-description">主力资金流向分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">主力净流入:</span>
                    <span class="stat-value up">{{ formatAmount(moneyFlowStats.mainNetInflow) }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">北向资金:</span>
                    <span class="stat-value" :class="getFlowClass(moneyFlowStats.northbound)">
                      {{ formatAmount(moneyFlowStats.northbound, true) }}
                    </span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">成交额:</span>
                    <span class="stat-value">{{ formatAmount(moneyFlowStats.turnover) }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">更新: {{ moneyFlowStats.updateTime }}</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>

          <!-- 涨跌停分析 -->
          <el-card class="function-nav-card" shadow="hover" @click="navigateTo('/market/limit-analysis')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon danger">
                  <Icon icon="mdi:trending-up"/>
                </div>
                <h3 class="function-title">涨跌停分析</h3>
              </div>
              <div class="function-info">
                <p class="function-description">涨跌停股票统计分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">涨停:</span>
                    <span class="stat-value up">{{ limitStats.upLimitCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">跌停:</span>
                    <span class="stat-value down">{{ limitStats.downLimitCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">炸板率:</span>
                    <span class="stat-value">{{ limitStats.explosionRate }}%</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">连板高度: {{ limitStats.maxConsecutive }}板</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 市场热点与实时数据 -->
      <div class="market-hotspots">
        <h2 class="market-section-title">
          <Icon icon="mdi:fire" class="title-icon"/>
          市场热点
        </h2>
        <div class="hotspot-grid">
          <!-- 实时涨幅榜卡片 -->
          <el-card class="hotspot-card" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <Icon icon="mdi:trending-up" class="card-title-icon"/>
                  实时涨幅榜
                </div>
                <el-button type="text" @click="navigateTo('/market/stocks')">
                  查看更多
                </el-button>
              </div>
            </template>
            <div class="hotspot-list">
              <div
                  v-for="(stock, index) in topRisingStocks"
                  :key="stock.code"
                  class="hotspot-item"
                  @click="viewStockDetail(stock)"
              >
                <div class="item-icon">
                  <Icon icon="mdi:trending-up" class="trend-icon up"/>
                </div>
                <div class="stock-info">
                  <div class="stock-name">{{ stock.name }}</div>
                  <div class="stock-code">{{ stock.code }}</div>
                </div>
                <div class="hotspot-change up">
                  +{{ stock.change.toFixed(2) }}%
                </div>
                <div class="hotspot-price flat">
                  ¥{{ stock.price.toFixed(2) }}
                </div>
              </div>
            </div>
          </el-card>

          <!-- 资金流入榜卡片 -->
          <el-card class="hotspot-card" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <Icon icon="mdi:cash-plus" class="card-title-icon"/>
                  资金流入榜
                </div>
                <el-button type="text" @click="navigateTo('/market/money-flow')">
                  查看更多
                </el-button>
              </div>
            </template>
            <div class="money-flow-list">
              <div
                  v-for="flow in topMoneyFlow"
                  :key="flow.code"
                  class="flow-item"
                  @click="viewStockDetail(flow)"
              >
                <div class="item-icon">
                  <Icon icon="mdi:cash-plus" class="flow-icon up"/>
                </div>
                <div class="stock-info">
                  <div class="stock-name">{{ flow.name }}</div>
                  <div class="stock-code">{{ flow.code }}</div>
                </div>
                <div class="flow-bar">
                  <div
                      class="flow-progress inflow"
                      :style="{ width: Math.min(flow.percentage, 100) + '%' }"
                  ></div>
                </div>
                <div class="flow-amount up">
                  +{{ formatAmount(flow.amount) }}
                </div>
              </div>
            </div>
          </el-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'
import {ElButton, ElMessage} from 'element-plus'

const router = useRouter()

// 响应式数据
const indexData = ref({
  shanghai: {close: 3254.32, change: 12.45, pct_chg: 0.38},
  shenzhen: {close: 11982.15, change: -23.67, pct_chg: -0.20},
  chuangye: {close: 2572.89, change: 18.92, pct_chg: 0.74},
  kechuang50: {close: 1056.78, change: 8.34, pct_chg: 0.79}
})

// 股票市场统计数据
const stockStats = ref({
  totalCount: 4856,
  riseCount: 2345,
  fallCount: 1876,
  flatCount: 635,
  updateTime: '15:00'
})

// ETF基金统计数据
const etfStats = ref({
  stockETF: 456,
  bondETF: 89,
  commodityETF: 45,
  totalAmount: 15678.90
})

// 指数行情统计数据
const indexStats = ref({
  broadIndex: 45,
  industryIndex: 156,
  strategyIndex: 33,
  totalCount: 234,
  riseCount: 156
})

// 行业强弱统计数据
const industryStats = ref({
  topIndustry: {name: '计算机', change: 3.2},
  bottomIndustry: {name: '房地产', change: -2.1},
  totalCount: 28,
  riseCount: 18
})

// 资金流向统计数据
const moneyFlowStats = ref({
  mainNetInflow: 1256700,
  northbound: 456700,
  turnover: 8456700,
  updateTime: '15:00'
})

// 涨跌停分析统计数据
const limitStats = ref({
  upLimitCount: 45,
  downLimitCount: 12,
  explosionRate: 23.4,
  maxConsecutive: 7
})

// 实时涨幅榜数据
const topRisingStocks = ref([
  {code: '300624', name: '万兴科技', change: 10.02, price: 156.78},
  {code: '002230', name: '科大讯飞', change: 9.98, price: 67.45},
  {code: '300059', name: '东方财富', change: 8.76, price: 23.89},
  {code: '600570', name: '恒生电子', change: 7.45, price: 45.67},
  {code: '000977', name: '浪潮信息', change: 6.89, price: 56.78}
])

// 资金流入榜数据
const topMoneyFlow = ref([
  {code: '300750', name: '宁德时代', amount: 125670, percentage: 85},
  {code: '000858', name: '五粮液', amount: 89234, percentage: 72},
  {code: '600519', name: '贵州茅台', amount: 78456, percentage: 68},
  {code: '002594', name: '比亚迪', amount: 67345, percentage: 65},
  {code: '601888', name: '中国中免', amount: 56789, percentage: 58}
])


// 方法
const navigateTo = (path) => {
  router.push(path)
}

const viewStockDetail = (stock) => {
  router.push(`/market/stock/${stock.code}`)
}

const getChangeClass = (data) => {
  if (data.change > 0) return 'up'
  if (data.change < 0) return 'down'
  return 'flat'
}

const getStatusClass = (data) => {
  if (data.change > 0) return 'running'
  if (data.change < 0) return 'remaining'
  return 'time'
}

const getFlowClass = (value) => {
  return value >= 0 ? 'up' : 'down'
}

const formatChange = (change) => {
  if (change === null || change === undefined) return '-'
  const sign = change > 0 ? '+' : ''
  return sign + change.toFixed(2)
}

const formatPercent = (pct) => {
  if (pct === null || pct === undefined) return '-'
  const sign = pct > 0 ? '+' : ''
  return sign + pct.toFixed(2) + '%'
}

const formatAmount = (amount, showSign = false) => {
  if (amount === null || amount === undefined) return '-'
  const absAmount = Math.abs(amount)
  const sign = showSign ? (amount > 0 ? '+' : amount < 0 ? '-' : '') : ''

  if (absAmount >= 100000000) {
    return sign + (absAmount / 100000000).toFixed(2) + '亿'
  } else if (absAmount >= 10000) {
    return sign + (absAmount / 10000).toFixed(2) + '万'
  } else {
    return sign + absAmount.toFixed(2)
  }
}

// 刷新数据方法
const refreshData = () => {
  // 模拟数据刷新
  simulateDataUpdate()
  ElMessage.success('数据已刷新')
}

// 模拟数据更新
const simulateDataUpdate = () => {
  // 随机更新指数数据
  Object.keys(indexData.value).forEach(key => {
    const item = indexData.value[key]
    const change = (Math.random() - 0.45) * 5 // 轻微偏向上涨
    item.close = parseFloat((item.close + change).toFixed(2))
    item.change = parseFloat(change.toFixed(2))
    item.pct_chg = parseFloat(((change / item.close) * 100).toFixed(2))
  })

  // 更新时间戳
  const now = new Date()
  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
  stockStats.value.updateTime = timeStr
  moneyFlowStats.value.updateTime = timeStr
}

// 生命周期钩子
onMounted(() => {
  // 初始加载时刷新数据
  refreshData()
})

</script>

<style lang="scss" scoped>
// 市场概览页面专用样式 - 基于交易系统主题实现
// 主要使用主题变量和混入，仅定义组件特有样式

@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as lmix;
@use 'sass:map';

// 引入市场概览专用样式
@use '@/assets/scss/market/market-overview';

// ============================================================================
// 组件特有响应式调整
// 仅保留无法通过全局样式覆盖的特殊调整
// ============================================================================

@include lmix.media-breakpoint-down(sm) {
  // 移动端隐藏股票代码 - 组件特有调整
  .hotspot-item,
  .flow-item {
    .stock-code {
      display: none;
    }
  }

  // 移动端简化资金流向显示 - 组件特有调整
  .flow-item {
    .flow-bar {
      display: none;
    }
  }
}
</style>