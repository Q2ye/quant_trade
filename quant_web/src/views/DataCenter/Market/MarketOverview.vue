<!--
  MarketOverview.vue — 新方案重写
  去除所有 SCSS mixin 依赖，使用 n-card + tokens + 直接 CSS 变量
  MainLayout 已全局提供：bg-gradient-mesh + bg-noise + ParticleBackground
-->
<template>
  <div class="market-overview-page scrollbar-hide">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场概览</h1>
          <p class="page-description">实时监控市场指数、资金流向和热点板块，掌握市场动态</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <template v-if="loading">
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="TrendingUp" class="title-icon" />主要指数</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item v-for="i in 4" :key="i" :class="tokens.motion.stagger" :style="{ animationDelay: `${(i - 1) * 0.08}s` }">
              <n-card><n-skeleton :text="true" :repeat="3" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="Apps" class="title-icon" />功能导航</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="3" responsive="screen">
            <n-grid-item v-for="i in 3" :key="i" :class="tokens.motion.stagger" :style="{ animationDelay: `${0.32 + (i - 1) * 0.08}s` }">
              <n-card><n-skeleton :text="true" :repeat="4" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
        <div class="content-section">
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
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="TrendingUp" class="title-icon" />主要指数</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item
              v-for="(item, idx) in indexList"
              :key="item.code"
              :class="tokens.motion.stagger"
              :style="{ animationDelay: `${idx * 0.08}s` }"
            >
              <n-card :class="[tokens.motion.hover, 'index-card']" @click="router.push('/market/index/' + item.code)">
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
                      <div class="index-value">{{ item.close != null ? item.close.toFixed(2) : '--' }}</div>
                      <div class="index-change" :class="item.changeClass">
                        <span class="change-value">{{ formatChange(item.change) }}</span>
                        <span class="change-percent">({{ formatPercent(item.pct_chg) }})</span>
                      </div>
                    </div>
                  </div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- ========== 功能导航 ========== -->
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="Apps" class="title-icon" />功能导航</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="3" responsive="screen">
            <!-- 行业强弱 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.32s">
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
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.40s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="navigateTo('/market/money-flow')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon info"><SmartIcon name="CashMultiple" /></div>
                    <h3 class="function-title">资金流向</h3>
                  </div>
                  <p class="function-desc">主力资金流向分析</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">主力净流入:</span><span class="stat-value text-up">{{ formatAmount(moneyFlowStats.mainNetInflow) }}</span></div>
                    <div class="stat-item"><span class="stat-label">北向资金:</span><span class="stat-value" :class="moneyFlowStats.northbound >= 0 ? 'text-up' : 'text-down'">{{ formatAmount(moneyFlowStats.northbound, true) }}</span></div>
                    <div class="stat-item"><span class="stat-label">成交额:</span><span class="stat-value">{{ formatAmount(moneyFlowStats.turnover) }}</span></div>
                  </div>
                  <div class="function-foot">更新: {{ moneyFlowStats.updateTime }}</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 涨跌停分析 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.48s">
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
        <div class="content-section">
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
import marketAPI from '@/api/market'
import type { IndexInfo, SectorInfo } from '@/types'

const router = useRouter()
const message = useMessage()

const loading = ref(true)
const error = ref(false)

// ---- 指数数据（来自 API） ----
const indexes = ref<IndexInfo[]>([])
const sectors = ref<SectorInfo[]>([])

// 四大指数配置
const MAJOR_INDEX_CODES = ['000001.SH', '399001.SZ', '399006.SZ', '000688.SH']
const MAJOR_INDEX_CONFIG: Record<string, { name: string; code: string; icon: string }> = {
  '000001.SH': { name: '上证指数', code: '000001', icon: 'TrendingUp' },
  '399001.SZ': { name: '深证成指', code: '399001', icon: 'BarChart' },
  '399006.SZ': { name: '创业板指', code: '399006', icon: 'Rocket' },
  '000688.SH': { name: '科创50',   code: '000688', icon: 'Chip' },
}

interface IndexDisplayItem {
  name: string
  code: string
  icon: string
  close: number | null
  change: number | null
  pct_chg: number | null
  statusClass: string
  changeClass: string
}

const indexList = computed<IndexDisplayItem[]>(() => {
  return MAJOR_INDEX_CODES.map((tsCode) => {
    const cfg = MAJOR_INDEX_CONFIG[tsCode]
    const found = indexes.value.find((idx) => idx.code === tsCode)
    const close = null as number | null
    const change = null as number | null
    const pct_chg = null as number | null
    const statusClass = 'status-flat'
    const changeClass = ''
    return { ...cfg, close, change, pct_chg, statusClass, changeClass }
  })
})

// ---- 行业（来自 API） ----
const industryStats = computed(() => {
  const list = sectors.value
  return {
    totalCount: list.length || 0,
    riseCount: 0,
    topIndustry: { name: '--', change: 0 },
    bottomIndustry: { name: '--', change: 0 },
  }
})

// ---- 资金 / 涨跌停（暂无实时 API） ----
const moneyFlowStats = ref({ mainNetInflow: 0, northbound: 0, turnover: 0, updateTime: '--' })
const limitStats = ref({ upLimitCount: 0, downLimitCount: 0, explosionRate: 0, maxConsecutive: 0 })

// ---- 涨幅榜 / 资金流入榜（暂无实时 API） ----
const topRisingStocks = ref<any[]>([])
const topMoneyFlow = ref<any[]>([])

// ---- 方法 ----
const navigateTo = (path: string) => router.push(path)
const viewStockDetail = (stock: any) => router.push(`/market/stock/${stock.code}`)

const formatChange = (v: number | null | undefined) => {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2)
}
const formatPercent = (v: number | null | undefined) => {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}
const formatAmount = (v: number | null | undefined, showSign = false) => {
  if (v == null) return '--'
  const abs = Math.abs(v)
  const sign = showSign ? (v > 0 ? '+' : v < 0 ? '-' : '') : ''
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(2) + '万'
  return sign + abs.toFixed(2)
}

const refreshData = async () => {
  loading.value = true
  error.value = false
  try {
    const [idxResult, secResult] = await Promise.all([
      marketAPI.getIndexes().catch(() => [] as IndexInfo[]),
      marketAPI.getSectors().catch(() => [] as SectorInfo[]),
    ])
    indexes.value = idxResult
    sectors.value = secResult
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
   MarketOverview — 遵循 Dashboard 模式的优化版本
   - :deep(.n-card) 半透明卡片，透出 3D 粒子背景
   - CSS 变量驱动所有颜色
   - 统一 .page-header 标准模式
   - scrollbar-hide 隐藏滚动条
   ============================================================ */

.market-overview-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;

  /* ---- 页面入场 ---- */
  animation: fadeIn 0.3s ease-out;

  /* ---- 半透明卡片（跟随 Dashboard 模式） ---- */
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

    > .n-card__content {
      overflow: hidden;
    }
  }
}

/* ---- 区块（左右内边距由全局 .content-section 提供） ---- */
.content-section {
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
    color: var(--color-primary, #448AFF);
  }
}

/* ---- 指数卡片 ---- */
.index-card {
  cursor: pointer;
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

  .index-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--n-text-color-1);
  }

  .index-code {
    font-size: 11px;
    color: var(--n-text-color-3);
    background: var(--color-bg-secondary, rgba(255, 255, 255, 0.05));
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

  &.status-up {
    background: rgba(255, 82, 82, 0.1);
    color: var(--color-stock-up, #FF5252);
  }

  &.status-down {
    background: rgba(0, 230, 118, 0.1);
    color: var(--color-stock-down, #00E676);
  }

  &.status-flat {
    background: rgba(136, 152, 184, 0.1);
    color: var(--n-text-color-3);
  }
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

/* ---- 功能导航卡片 ---- */
.function-card {
  cursor: pointer;

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

  &.accent  { background: rgba(68, 138, 255, 0.12); color: var(--color-primary, #448AFF); }
  &.purple  { background: rgba(124, 111, 247, 0.12); color: var(--color-purple, #7C6FF7); }
  &.info    { background: rgba(64, 196, 255, 0.12); color: var(--color-info, #40C4FF); }
  &.danger  { background: rgba(255, 82, 82, 0.12);   color: var(--color-error, #FF5252); }
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

  .hotspot-title-icon {
    font-size: 16px;
    color: var(--color-primary, #448AFF);
  }
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

  &:hover { background: var(--color-bg-hover, rgba(68, 138, 255, 0.05)); }

  .item-icon {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;

    .icon-up { color: var(--color-stock-up, #FF5252); }
  }

  .item-info {
    flex: 1;
    min-width: 0;

    .item-name {
      font-size: 13px;
      color: var(--n-text-color-1);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .item-code { font-size: 11px; color: var(--n-text-color-3); }
  }

  .item-change {
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
  }

  .item-price {
    font-size: 13px;
    color: var(--n-text-color-3);
    white-space: nowrap;
  }

  .flow-bar {
    flex: 1;
    min-width: 60px;
  }
}

/* ---- 状态色工具类 ---- */
.text-up {
  color: var(--color-stock-up, #FF5252);
  font-weight: 500;
}

.text-down {
  color: var(--color-stock-down, #00E676);
  font-weight: 500;
}

/* ---- 响应式 ---- */
@media (max-width: 768px) {
  .index-body {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 576px) {
  .hotspot-item {
    flex-wrap: wrap;

    .item-change, .item-price, .flow-bar {
      width: 100%;
      margin-left: 34px;
    }
  }
}

/* ---- 入场动画 ---- */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
