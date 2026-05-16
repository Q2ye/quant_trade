<!--
  MarketOverview.vue — 新方案重写
  去除所有 SCSS mixin 依赖，使用 n-card + tokens + 直接 CSS 变量
  MainLayout 已全局提供：bg-gradient-mesh + bg-noise + ParticleBackground
-->
<template>
  <div class="market-overview-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场概览</h1>
          <p class="page-description">实时监控市场指数、资金流向和热点板块，掌握市场动态</p>
        </div>
        <div class="header-actions">
          <n-button class="refresh-btn" @click="refreshData">
            <template #icon><SmartIcon name="Refresh" /></template>
            <span class="btn-text">刷新数据</span>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <template v-if="loading">
        <div class="section">
          <h2 class="section-title"><SmartIcon name="TrendingUp" class="title-icon" />主要指数</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item v-for="i in 4" :key="i" :class="tokens.motion.stagger" :style="{ animationDelay: `${(i - 1) * 0.08}s` }">
              <n-card><n-skeleton :text="true" :repeat="3" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
        <div class="section">
          <h2 class="section-title"><SmartIcon name="Apps" class="title-icon" />功能导航</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
            <n-grid-item v-for="i in 4" :key="i" :class="tokens.motion.stagger" :style="{ animationDelay: `${0.32 + (i - 1) * 0.08}s` }">
              <n-card><n-skeleton :text="true" :repeat="4" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
        <div class="section">
          <h2 class="section-title"><SmartIcon name="Fire" class="title-icon" />市场热点</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
            <n-grid-item v-for="i in 2" :key="i" :class="tokens.motion.stagger" :style="{ animationDelay: `${0.64 + (i - 1) * 0.08}s` }">
              <n-card><n-skeleton :text="true" :repeat="5" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
      </template>

      <!-- Error -->
      <n-result v-else-if="error" status="500" title="数据加载失败" description="请检查网络连接后重试">
        <template #footer><n-button type="primary" @click="loadData">重试</n-button></template>
      </n-result>

      <!-- Data -->
      <template v-else>
        <!-- ========== 主要指数 ========== -->
        <div class="section">
          <h2 class="section-title"><SmartIcon name="TrendingUp" class="title-icon" />主要指数</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item
              v-for="(item, idx) in indexList"
              :key="item.code"
              :class="tokens.motion.stagger"
              :style="{ animationDelay: `${idx * 0.08}s` }"
            >
              <n-card :class="[tokens.motion.hover, 'index-card']">
                <div class="index-card-inner">
                  <div class="index-header">
                    <span class="index-name">{{ item.name }}</span>
                    <span class="index-code">{{ item.code }}</span>
                  </div>
                  <div class="index-body">
                    <div class="index-status-icon" :class="item.statusClass">
                      <SmartIcon :name="item.icon" />
                    </div>
                    <div class="index-info">
                      <div class="index-value">{{ item.data.close.toFixed(2) }}</div>
                      <div class="index-change" :class="item.changeClass">
                        <span class="change-value">{{ formatChange(item.data.change) }}</span>
                        <span class="change-percent">({{ formatPercent(item.data.pct_chg) }})</span>
                      </div>
                    </div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- ========== 功能导航 ========== -->
        <div class="section">
          <h2 class="section-title"><SmartIcon name="Apps" class="title-icon" />功能导航</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
            <!-- 市场仪表盘 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.32s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="goToDashboard">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon accent"><SmartIcon name="Dashboard" /></div>
                    <h3 class="function-title">市场仪表盘</h3>
                  </div>
                  <p class="function-desc">股票/ETF/指数一站式分析</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">股票:</span><span class="stat-value">{{ dashboardStats.stocks }}</span></div>
                    <div class="stat-item"><span class="stat-label">ETF:</span><span class="stat-value">{{ dashboardStats.etfs }}</span></div>
                    <div class="stat-item"><span class="stat-label">指数:</span><span class="stat-value">{{ dashboardStats.indexes }}</span></div>
                  </div>
                  <div class="function-foot">统一视图分析</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 行业强弱 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.40s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="navigateTo('/market/industry-strength')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon purple"><SmartIcon name="TreeChart" /></div>
                    <h3 class="function-title">行业强弱</h3>
                  </div>
                  <p class="function-desc">行业强弱与趋势分析</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">领涨行业:</span><span class="stat-value text-up">{{ industryStats.topIndustry.name }}</span></div>
                    <div class="stat-item"><span class="stat-label">涨幅:</span><span class="stat-value text-up">{{ industryStats.topIndustry.change }}%</span></div>
                    <div class="stat-item"><span class="stat-label">领跌行业:</span><span class="stat-value text-down">{{ industryStats.bottomIndustry.name }}</span></div>
                  </div>
                  <div class="function-foot">{{ industryStats.riseCount }}/{{ industryStats.totalCount }}行业上涨</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 资金流向 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.48s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="navigateTo('/market/money-flow')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon info"><SmartIcon name="CashMultiple" /></div>
                    <h3 class="function-title">资金流向</h3>
                  </div>
                  <p class="function-desc">主力资金流向分析</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">主力净流入:</span><span class="stat-value text-up">{{ formatAmount(moneyFlowStats.mainNetInflow) }}</span></div>
                    <div class="stat-item"><span class="stat-label">北向资金:</span><span class="stat-value" :class="getFlowClass(moneyFlowStats.northbound)">{{ formatAmount(moneyFlowStats.northbound, true) }}</span></div>
                    <div class="stat-item"><span class="stat-label">成交额:</span><span class="stat-value">{{ formatAmount(moneyFlowStats.turnover) }}</span></div>
                  </div>
                  <div class="function-foot">更新: {{ moneyFlowStats.updateTime }}</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 涨跌停分析 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.56s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="navigateTo('/market/limit-events')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon danger"><SmartIcon name="TrendingUp" /></div>
                    <h3 class="function-title">涨跌停分析</h3>
                  </div>
                  <p class="function-desc">涨跌停股票统计分析</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">涨停:</span><span class="stat-value text-up">{{ limitStats.upLimitCount }}</span></div>
                    <div class="stat-item"><span class="stat-label">跌停:</span><span class="stat-value text-down">{{ limitStats.downLimitCount }}</span></div>
                    <div class="stat-item"><span class="stat-label">炸板率:</span><span class="stat-value">{{ limitStats.explosionRate }}%</span></div>
                  </div>
                  <div class="function-foot">连板高度: {{ limitStats.maxConsecutive }}板</div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- ========== 市场热点 ========== -->
        <div class="section">
          <h2 class="section-title"><SmartIcon name="Fire" class="title-icon" />市场热点</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
            <!-- 实时涨幅榜 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.64s">
              <n-card class="hotspot-card">
                <template #header>
                  <div class="hotspot-header">
                    <div class="hotspot-title"><SmartIcon name="TrendingUp" class="hotspot-title-icon" />实时涨幅榜</div>
                    <n-button text class="more-btn" @click="navigateTo('/market/stocks')">
                      查看更多
                      <template #icon><SmartIcon name="ArrowRight" /></template>
                    </n-button>
                  </div>
                </template>
                <n-empty v-if="topRisingStocks.length === 0" description="暂无涨幅数据" />
                <div v-else class="hotspot-list">
                  <div v-for="stock in topRisingStocks" :key="stock.code" class="hotspot-item" @click="viewStockDetail(stock)">
                    <div class="item-icon"><SmartIcon name="TrendingUp" class="icon-up" /></div>
                    <div class="item-info">
                      <div class="item-name">{{ stock.name }}</div>
                      <div class="item-code">{{ stock.code }}</div>
                    </div>
                    <div class="item-change text-up">+{{ stock.change.toFixed(2) }}%</div>
                    <div class="item-price">¥{{ stock.price.toFixed(2) }}</div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 资金流入榜 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.72s">
              <n-card class="hotspot-card">
                <template #header>
                  <div class="hotspot-header">
                    <div class="hotspot-title"><SmartIcon name="CashPlus" class="hotspot-title-icon" />资金流入榜</div>
                    <n-button text class="more-btn" @click="navigateTo('/market/money-flow')">
                      查看更多
                      <template #icon><SmartIcon name="ArrowRight" /></template>
                    </n-button>
                  </div>
                </template>
                <n-empty v-if="topMoneyFlow.length === 0" description="暂无资金流数据" />
                <div v-else class="hotspot-list">
                  <div v-for="flow in topMoneyFlow" :key="flow.code" class="hotspot-item" @click="viewStockDetail(flow)">
                    <div class="item-icon"><SmartIcon name="CashPlus" class="icon-up" /></div>
                    <div class="item-info">
                      <div class="item-name">{{ flow.name }}</div>
                      <div class="item-code">{{ flow.code }}</div>
                    </div>
                    <div class="flow-bar">
                      <n-progress type="line" :percentage="Math.min(flow.percentage, 100)" :height="6" :border-radius="3" :show-indicator="false" status="success" />
                    </div>
                    <div class="item-change text-up">+{{ formatAmount(flow.amount) }}</div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NGrid, NGridItem, NProgress, NSkeleton, NEmpty, NResult, useMessage } from 'naive-ui'
import SmartIcon from '@/components/common/SmartIcon.vue'
import { tokens } from '@/styles/design-tokens'

const router = useRouter()
const message = useMessage()

const loading = ref(false)
const error = ref(false)

// ---- 指数数据 ----
const indexData = ref({
  shanghai:   { close: 3254.32, change: 12.45,  pct_chg: 0.38 },
  shenzhen:   { close: 11982.15, change: -23.67, pct_chg: -0.20 },
  chuangye:   { close: 2572.89, change: 18.92,  pct_chg: 0.74 },
  kechuang50: { close: 1056.78, change: 8.34,   pct_chg: 0.79 },
})

const indexList = computed(() => [
  { name: '上证指数', code: '000001', icon: 'TrendingUp', data: indexData.value.shanghai,
    statusClass: getStatusClass(indexData.value.shanghai), changeClass: getChangeClass(indexData.value.shanghai) },
  { name: '深证成指', code: '399001', icon: 'BarChart',   data: indexData.value.shenzhen,
    statusClass: getStatusClass(indexData.value.shenzhen), changeClass: getChangeClass(indexData.value.shenzhen) },
  { name: '创业板指', code: '399006', icon: 'Rocket',     data: indexData.value.chuangye,
    statusClass: getStatusClass(indexData.value.chuangye), changeClass: getChangeClass(indexData.value.chuangye) },
  { name: '科创50',  code: '000688', icon: 'Chip',       data: indexData.value.kechuang50,
    statusClass: getStatusClass(indexData.value.kechuang50), changeClass: getChangeClass(indexData.value.kechuang50) },
])

// ---- 行业 ----
const industryStats = ref({
  topIndustry:    { name: '计算机', change: 3.2 },
  bottomIndustry: { name: '房地产', change: -2.1 },
  totalCount: 28, riseCount: 18,
})

// ---- 资金 ----
const moneyFlowStats = ref({
  mainNetInflow: 1256700, northbound: 456700, turnover: 8456700, updateTime: '15:00',
})

// ---- 涨跌停 ----
const limitStats = ref({
  upLimitCount: 45, downLimitCount: 12, explosionRate: 23.4, maxConsecutive: 7,
})

// ---- 仪表盘统计 ----
const dashboardStats = ref({ stocks: 4856, etfs: 589, indexes: 234 })

// ---- 涨幅榜 ----
const topRisingStocks = ref([
  { code: '300624', name: '万兴科技', change: 10.02, price: 156.78 },
  { code: '002230', name: '科大讯飞', change: 9.98,  price: 67.45 },
  { code: '300059', name: '东方财富', change: 8.76,  price: 23.89 },
  { code: '600570', name: '恒生电子', change: 7.45,  price: 45.67 },
  { code: '000977', name: '浪潮信息', change: 6.89,  price: 56.78 },
])

// ---- 资金流入榜 ----
const topMoneyFlow = ref([
  { code: '300750', name: '宁德时代', amount: 125670, percentage: 85 },
  { code: '000858', name: '五粮液',   amount: 89234,  percentage: 72 },
  { code: '600519', name: '贵州茅台', amount: 78456,  percentage: 68 },
  { code: '002594', name: '比亚迪',   amount: 67345,  percentage: 65 },
  { code: '601888', name: '中国中免', amount: 56789,  percentage: 58 },
])

// ---- 方法 ----
const navigateTo = (path: string) => router.push(path)
const goToDashboard = () => router.push('/market/mkDashboard')
const viewStockDetail = (stock: any) => router.push(`/market/stock/${stock.code}`)

const getChangeClass = (d: any) => d.change > 0 ? 'text-up' : d.change < 0 ? 'text-down' : ''
const getStatusClass = (d: any) => d.change > 0 ? 'status-up' : d.change < 0 ? 'status-down' : 'status-flat'
const getFlowClass = (v: number) => v >= 0 ? 'text-up' : 'text-down'

const formatChange = (v: number | null | undefined) => {
  if (v == null) return '-'
  return (v > 0 ? '+' : '') + v.toFixed(2)
}
const formatPercent = (v: number | null | undefined) => {
  if (v == null) return '-'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}
const formatAmount = (v: number | null | undefined, showSign = false) => {
  if (v == null) return '-'
  const abs = Math.abs(v)
  const sign = showSign ? (v > 0 ? '+' : v < 0 ? '-' : '') : ''
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(2) + '万'
  return sign + abs.toFixed(2)
}

const simulateDataUpdate = () => {
  for (const key of Object.keys(indexData.value) as Array<keyof typeof indexData.value>) {
    const item = indexData.value[key]
    const chg = parseFloat(((Math.random() - 0.45) * 5).toFixed(2))
    item.close = parseFloat((item.close + chg).toFixed(2))
    item.change = chg
    item.pct_chg = parseFloat(((chg / item.close) * 100).toFixed(2))
  }
  const now = new Date()
  moneyFlowStats.value.updateTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
}

const refreshData = async () => {
  loading.value = true
  error.value = false
  try {
    simulateDataUpdate()
    message.success('数据已刷新')
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}
const loadData = () => refreshData()

onMounted(() => { loadData() })
</script>

<style lang="scss" scoped>
/* ============================================================
   MarketOverview — 零 mixin 依赖，纯 CSS 变量
   n-card 原生提供: background, border, border-radius, box-shadow
   ============================================================ */

.market-overview-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 16px;
  animation: fadeIn 0.3s ease-out;
}

/* ---- 页面头部 ---- */
.page-header {
  margin-bottom: 24px;
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }
  .page-title {
    font-size: 24px;
    font-weight: 700;
    color: var(--n-text-color-1);
    margin: 0 0 4px;
  }
  .page-description {
    font-size: 13px;
    color: var(--n-text-color-3);
    margin: 0;
  }
  .refresh-btn {
    // inherit Naive UI default button styling
  }
}

/* ---- 区块 ---- */
.section {
  margin-bottom: 28px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0 0 16px;
  .title-icon {
    font-size: 18px;
    color: var(--n-primary-color);
  }
}

/* ---- 指数卡片 ---- */
.index-card {
  overflow: hidden;
  background-color: var(--color-bg-card, #161B22);
  :deep(.n-card__content) { padding: 20px; }
}
.index-card-inner {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.index-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  .index-name { font-size: 14px; font-weight: 600; color: var(--n-text-color-1); }
  .index-code {
    font-size: 11px;
    color: var(--n-text-color-3);
    background: var(--color-bg-secondary, rgba(255,255,255,0.05));
    padding: 3px 10px;
    border-radius: 10px;
  }
}
.index-body {
  display: flex;
  align-items: center;
  gap: 12px;
}
.index-status-icon {
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  &.status-up   { background: rgba(245,108,108,0.1); color: var(--color-stock-up, #f56c6c); }
  &.status-down { background: rgba(103,194,58,0.1); color: var(--color-stock-down, #67c23a); }
  &.status-flat { background: rgba(139,148,158,0.1); color: var(--n-text-color-3); }
}
.index-info {
  flex: 1;
  min-width: 0;
  .index-value {
    font-size: 22px;
    font-weight: 700;
    color: var(--n-text-color-1);
    line-height: 1.2;
    margin-bottom: 4px;
  }
  .index-change {
    font-size: 13px;
    font-weight: 500;
    .change-percent { opacity: 0.85; }
  }
}

/* ---- 功能卡片 ---- */
.function-card {
  cursor: pointer;
  background-color: var(--color-bg-card, #161B22);
  :deep(.n-card__content) { padding: 20px; }
}
.function-inner {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.function-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.function-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  &.accent  { background: rgba(33,150,243,0.12); color: var(--n-primary-color); }
  &.purple  { background: rgba(156,39,176,0.12); color: var(--color-purple, #9c27b0); }
  &.info    { background: rgba(23,162,184,0.12); color: var(--color-info, #17a2b8); }
  &.danger  { background: rgba(245,108,108,0.12); color: var(--color-stock-up, #f56c6c); }
}
.function-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0;
}
.function-desc {
  font-size: 13px;
  color: var(--n-text-color-3);
  margin: 0;
  line-height: 1.4;
}
.function-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  .stat-label { color: var(--n-text-color-3); }
  .stat-value { font-weight: 600; color: var(--n-text-color-1); }
}
.function-foot {
  font-size: 12px;
  color: var(--n-text-color-3);
  padding-top: 10px;
  border-top: 1px solid var(--n-border-color);
}

/* ---- 热点卡片 ---- */
.hotspot-card {
  background-color: var(--color-bg-card, #161B22);
  :deep(.n-card__content) { padding: 0; }
}
.hotspot-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}
.hotspot-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--n-text-color-1);
  .hotspot-title-icon { font-size: 16px; color: var(--n-primary-color); }
}
.more-btn {
  font-size: 13px;
}
.hotspot-list {
  max-height: 280px;
  overflow-y: auto;
}
.hotspot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--n-border-color);
  cursor: pointer;
  transition: background 0.15s ease;
  min-height: 48px;
  &:last-child { border-bottom: none; }
  &:hover { background: var(--n-color-hover, rgba(255,255,255,0.04)); }
  .item-icon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    .icon-up { color: var(--color-stock-up, #f56c6c); }
  }
  .item-info {
    flex: 1;
    min-width: 0;
    .item-name { font-size: 13px; color: var(--n-text-color-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .item-code { font-size: 11px; color: var(--n-text-color-3); }
  }
  .item-change { font-size: 13px; font-weight: 600; white-space: nowrap; }
  .item-price  { font-size: 13px; color: var(--n-text-color-3); white-space: nowrap; }
  .flow-bar {
    flex: 1;
    min-width: 60px;
  }
}

/* ---- 全局工具类补充（scoped 内补几个简单状态色） ---- */
.text-up   { color: var(--color-stock-up, #f56c6c); font-weight: 500; }
.text-down { color: var(--color-stock-down, #67c23a); font-weight: 500; }

/* ---- 响应式 ---- */
@media (max-width: 768px) {
  .page-header .header-content { flex-direction: column; }
  .index-body { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 576px) {
  .market-overview-page { padding: 12px 8px; }
  .hotspot-item { flex-wrap: wrap; .item-change, .item-price, .flow-bar { width: 100%; margin-left: 34px; } }
}

/* ---- 入场动画 ---- */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
