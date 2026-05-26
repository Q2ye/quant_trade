<!--
  IndexDetail.vue — 重设计版本
  方案1：页头 + 快速统计 + K线图 + 选项卡（基本信息 / 成分股）
  背景由 MainLayout 全局提供：bg-gradient-mesh + bg-noise
-->
<template>
  <div class="index-detail-page">
    <!-- ========== A. 页头栏 ========== -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">{{ indexInfo?.name || '--' }} <span class="index-code-tag">{{ code }}</span></h1>
          <p v-if="indexInfo" class="page-description">
            <span class="index-price">{{ formatPrice(indexInfo.current_point) }}</span>
            <span class="index-change" :class="changeClass">{{ formatChange(indexInfo.change) }}</span>
            <span class="index-change-pct" :class="changeClass">({{ formatPercent(indexInfo.change_percent) }})</span>
            <span class="index-update">{{ updateTime }}</span>
            <n-tag :type="marketStatus === 'open' ? 'success' : 'default'" size="small" :bordered="false" class="index-status-tag">
              {{ marketStatus === 'open' ? '交易中' : '已收盘' }}
            </n-tag>
          </p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="router.back()" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content scrollbar-hide">
      <!-- ========== Loading ========== -->
      <template v-if="loading">
        <div class="section">
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item v-for="i in 4" :key="i">
              <n-card><n-skeleton :text="true" :repeat="2" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
        <div class="section">
          <n-card>
            <template #header><n-skeleton :text="true" width="120px" /></template>
            <n-skeleton style="height: 420px" width="100%" />
          </n-card>
        </div>
        <div class="section">
          <n-card><n-skeleton :text="true" :repeat="8" /></n-card>
        </div>
      </template>

      <!-- ========== Error ========== -->
      <n-result
        v-else-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <!-- ========== Data ========== -->
      <template v-else>
        <!-- B. 快速统计行 -->
        <div class="section">
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item
              v-for="(stat, idx) in quickStats"
              :key="stat.label"
              :class="tokens.motion.stagger"
              :style="{ animationDelay: `${idx * 0.06}s` }"
            >
              <n-card :class="tokens.motion.hover">
                <div class="stat-card-inner">
                  <span class="stat-label">{{ stat.label }}</span>
                  <span class="stat-value" :class="stat.colorClass">{{ stat.value }}</span>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- C. K线图 -->
        <div class="section">
          <n-card>
            <template #header>
              <div class="chart-header">
                <h3 class="chart-title">
                  <SmartIcon name="BarChart" class="title-icon" />K线图
                </h3>
                <n-button-group size="small">
                  <n-button
                    v-for="p in periods"
                    :key="p.value"
                    :type="selectedPeriod === p.value ? 'primary' : 'default'"
                    @click="selectedPeriod = p.value"
                  >
                    {{ p.label }}
                  </n-button>
                </n-button-group>
              </div>
            </template>
            <div class="chart-body">
              <KLineChart
                :key="`${code}-${selectedPeriod}`"
                :symbol="code"
                :period="selectedPeriod"
                :indicators="['MA5', 'MA10', 'MA20', 'VOL']"
              />
            </div>
          </n-card>
        </div>

        <!-- D. 选项卡 -->
        <div class="section">
          <n-card>
            <n-tabs v-model:value="activeTab" type="line" animated>
              <!-- D1. 基本信息 -->
              <n-tab-pane name="basic" tab="基本信息">
                <n-empty v-if="!indexInfo" description="暂无指数信息" />
                <n-descriptions
                  v-else
                  label-placement="left"
                  :column="2"
                  bordered
                  class="info-descriptions"
                >
                  <n-descriptions-item label="指数全称">
                    <span :title="indexInfo.fullname">{{ indexInfo.fullname || '--' }}</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="市场">
                    <n-tag :bordered="false" type="info" size="small">{{ indexInfo.market }}</n-tag>
                  </n-descriptions-item>
                  <n-descriptions-item label="发布机构">{{ indexInfo.publisher || '--' }}</n-descriptions-item>
                  <n-descriptions-item label="分类">{{ indexInfo.category || '--' }}</n-descriptions-item>
                  <n-descriptions-item label="基日">{{ indexInfo.base_date || '--' }}</n-descriptions-item>
                  <n-descriptions-item label="基点">{{ formatNumber(indexInfo.base_point) }}</n-descriptions-item>
                  <n-descriptions-item label="成分股数量">{{ indexInfo.components_count ?? '--' }} 只</n-descriptions-item>
                  <n-descriptions-item label="上市日期">{{ indexInfo.list_date || '--' }}</n-descriptions-item>
                  <n-descriptions-item label="市盈率 (PE)">
                    <span :class="getValueClass(indexInfo.pe)">{{ formatNumber(indexInfo.pe) }}</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="市净率 (PB)">
                    <span :class="getValueClass(indexInfo.pb)">{{ formatNumber(indexInfo.pb) }}</span>
                  </n-descriptions-item>
                  <n-descriptions-item label="成交额">
                    {{ indexInfo.amount != null ? formatAmount(indexInfo.amount) : '--' }}
                  </n-descriptions-item>
                  <n-descriptions-item label="成交量">
                    {{ indexInfo.volume != null ? formatVolume(indexInfo.volume) : '--' }}
                  </n-descriptions-item>
                </n-descriptions>
              </n-tab-pane>

              <!-- D2. 成分股 -->
              <n-tab-pane name="components" :tab="componentsTabLabel">
                <div class="components-toolbar">
                  <n-input
                    v-model:value="componentSearch"
                    placeholder="搜索代码或名称..."
                    clearable
                    class="search-input"
                  >
                    <template #prefix><SmartIcon name="Search" /></template>
                  </n-input>
                </div>
                <n-empty
                  v-if="filteredComponents.length === 0"
                  description="暂无成分股数据"
                />
                <n-data-table
                  v-else
                  :columns="componentColumns"
                  :data="filteredComponents"
                  :virtual-scroll="true"
                  :max-height="420"
                  :row-props="componentRowProps"
                  :row-class-name="componentRowClass"
                  striped
                  size="small"
                />
              </n-tab-pane>
            </n-tabs>
          </n-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NButton, NCard, NGrid, NGridItem, NSkeleton, NEmpty, NResult,
  NTabs, NTabPane, NDescriptions, NDescriptionsItem, NTag,
  NButtonGroup, NInput, NDataTable, useMessage,
} from 'naive-ui'
import type { DataTableColumns, DataTableRowKey } from 'naive-ui'
import SmartIcon from '@/components/common/SmartIcon.vue'
import KLineChart from '@/components/charts/KLineChart.vue'
import { tokens } from '@/styles/design-tokens'
import marketApi from '@/api/market'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const code = computed(() => (route.params.code as string) || '')

// ---- 状态 ----
const loading = ref(true)
const error = ref(false)
const activeTab = ref('basic')
const selectedPeriod = ref('daily')
const componentSearch = ref('')

const periods = [
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
]

// ---- 指数详情数据（扩展接口，包含行情字段） ----
interface IndexDetailData {
  ts_code: string
  name: string
  fullname: string
  market: string
  publisher: string
  category: string
  base_date: string
  base_point: number
  list_date: string
  current_point: number
  change: number
  change_percent: number
  open: number
  high: number
  low: number
  pre_close: number
  volume: number
  amount: number
  pe: number
  pb: number
  components_count: number
}

interface ComponentStock {
  code: string
  name: string
  price: number
  change_pct: number
  weight: number
  market_cap: number
}

const indexInfo = ref<IndexDetailData | null>(null)
const components = ref<ComponentStock[]>([])

// ---- 计算属性 ----
const updateTime = computed(() => {
  const now = new Date()
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
})

const marketStatus = computed<'open' | 'closed'>(() => {
  const h = new Date().getHours()
  const m = new Date().getMinutes()
  const t = h * 60 + m
  return (t >= 570 && t <= 900) ? 'open' : 'closed'
})

const changeClass = computed(() => {
  if (!indexInfo.value) return ''
  const v = indexInfo.value.change
  if (v > 0) return 'text-up'
  if (v < 0) return 'text-down'
  return ''
})

const quickStats = computed(() => {
  const d = indexInfo.value
  if (!d) return []
  return [
    { label: '开盘', value: d.open != null ? d.open.toFixed(2) : '--', colorClass: getCompareClass(d.open, d.pre_close) },
    { label: '最高', value: d.high != null ? d.high.toFixed(2) : '--', colorClass: getCompareClass(d.high, d.pre_close) },
    { label: '最低', value: d.low != null ? d.low.toFixed(2) : '--', colorClass: getCompareClass(d.low, d.pre_close) },
    { label: '昨收', value: d.pre_close != null ? d.pre_close.toFixed(2) : '--', colorClass: '' },
  ]
})

const filteredComponents = computed(() => {
  const kw = componentSearch.value.trim().toLowerCase()
  if (!kw) return components.value
  return components.value.filter(c =>
    c.code.toLowerCase().includes(kw) || c.name.toLowerCase().includes(kw),
  )
})

const componentsTabLabel = computed(() => `成分股 (${components.value.length})`)

// ---- 表格列定义 ----
const componentColumns: DataTableColumns<ComponentStock> = [
  { title: '代码', key: 'code', width: 100, ellipsis: true },
  { title: '名称', key: 'name', width: 120, ellipsis: true },
  { title: '最新价', key: 'price', width: 100, align: 'right',
    render(row) { return row.price != null ? row.price.toFixed(2) : '--' },
  },
  { title: '涨跌幅', key: 'change_pct', width: 100, align: 'right', sortOrder: false,
    sorter: (a: ComponentStock, b: ComponentStock) => (a.change_pct || 0) - (b.change_pct || 0),
    render(row) {
      const v = row.change_pct
      if (v == null) return '--'
      const cls = v > 0 ? 'text-up' : v < 0 ? 'text-down' : ''
      return h('span', { class: cls }, (v > 0 ? '+' : '') + v.toFixed(2) + '%')
    },
  },
  { title: '权重', key: 'weight', width: 100, align: 'right',
    render(row) { return row.weight != null ? row.weight.toFixed(2) + '%' : '--' },
  },
  { title: '总市值', key: 'market_cap', width: 130, align: 'right',
    render(row) { return row.market_cap != null ? formatAmount(row.market_cap) : '--' },
  },
]

// ---- 行点击 ----
function componentRowProps(row: ComponentStock) {
  return { style: 'cursor: pointer;' }
}
function componentRowClass(row: ComponentStock) {
  return 'component-row'
}

// ---- 方法 ----
function pad(n: number) { return n.toString().padStart(2, '0') }

function formatPrice(v: number | null | undefined) {
  if (v == null) return '--'
  return v.toFixed(2)
}

function formatChange(v: number | null | undefined) {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2)
}

function formatPercent(v: number | null | undefined) {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}

function formatNumber(v: number | null | undefined) {
  if (v == null) return '--'
  return v.toFixed(2)
}

function formatAmount(v: number) {
  const abs = Math.abs(v)
  if (abs >= 1e8) return (abs / 1e8).toFixed(2) + '亿'
  if (abs >= 1e4) return (abs / 1e4).toFixed(2) + '万'
  return abs.toFixed(2)
}

function formatVolume(v: number) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿手'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '万手'
  return v.toFixed(0) + '手'
}

function getCompareClass(value: number, base: number) {
  if (value > base) return 'text-up'
  if (value < base) return 'text-down'
  return ''
}

function getValueClass(v: number | null | undefined) {
  if (v == null) return ''
  return v > 0 ? 'text-up' : 'text-down'
}

// ---- 模拟数据 ----
function buildMockIndexDetail(idxCode: string): IndexDetailData {
  const nameMap: Record<string, { name: string; fullname: string; market: string }> = {
    '000001': { name: '上证指数', fullname: '上证综合指数', market: '上海证券交易所' },
    '399001': { name: '深证成指', fullname: '深证成份指数', market: '深圳证券交易所' },
    '399006': { name: '创业板指', fullname: '创业板指数', market: '深圳证券交易所' },
    '000688': { name: '科创50', fullname: '上证科创板50成份指数', market: '上海证券交易所' },
  }
  const meta = nameMap[idxCode] || { name: idxCode, fullname: idxCode, market: '--' }
  const base = 3000 + Math.random() * 500
  const preClose = base + (Math.random() - 0.5) * 50
  const cur = preClose + (Math.random() - 0.48) * 80
  const chg = cur - preClose
  return {
    ts_code: idxCode,
    name: meta.name,
    fullname: meta.fullname,
    market: meta.market,
    publisher: idxCode === '000001' || idxCode === '000688' ? '中证指数有限公司' : '深圳证券信息有限公司',
    category: '规模指数',
    base_date: idxCode === '000001' ? '1990-12-19' : idxCode === '399006' ? '2010-05-31' : '2000-01-01',
    base_point: idxCode === '000001' ? 100 : 1000,
    list_date: idxCode === '000001' ? '1990-12-19' : '2000-01-01',
    current_point: parseFloat(cur.toFixed(2)),
    change: parseFloat(chg.toFixed(2)),
    change_percent: parseFloat(((chg / preClose) * 100).toFixed(2)),
    open: parseFloat((preClose + (Math.random() - 0.5) * 30).toFixed(2)),
    high: parseFloat((cur + Math.abs(chg) * 0.5).toFixed(2)),
    low: parseFloat((cur - Math.abs(chg) * 0.6).toFixed(2)),
    pre_close: parseFloat(preClose.toFixed(2)),
    volume: Math.floor(1e9 + Math.random() * 5e9),
    amount: Math.floor(3e10 + Math.random() * 1e11),
    pe: parseFloat((12 + Math.random() * 20).toFixed(2)),
    pb: parseFloat((1 + Math.random() * 4).toFixed(2)),
    components_count: idxCode === '000688' ? 50 : idxCode === '000001' ? 1500 : 300,
  }
}

function buildMockComponents(count: number): ComponentStock[] {
  const names = [
    '贵州茅台', '宁德时代', '五粮液', '比亚迪', '中国中免', '恒瑞医药', '中信证券',
    '海康威视', '立讯精密', '迈瑞医疗', '招商银行', '隆基绿能', '药明康德', '片仔癀',
    '中国平安', '兴业银行', '伊利股份', '万华化学', '牧原股份', '泸州老窖',
    '东方财富', '恒生电子', '科大讯飞', '浪潮信息', '中芯国际', '长江电力',
    '美的集团', '格力电器', '海尔智家', '韦尔股份', '北方华创', '三一重工',
  ]
  const stocks: ComponentStock[] = []
  for (let i = 0; i < count; i++) {
    const name = names[i % names.length] + (i >= names.length ? `-${Math.floor(i / names.length)}` : '')
    stocks.push({
      code: (600000 + i).toString(),
      name,
      price: parseFloat((10 + Math.random() * 300).toFixed(2)),
      change_pct: parseFloat(((Math.random() - 0.45) * 8).toFixed(2)),
      weight: parseFloat((0.1 + Math.random() * 8).toFixed(2)),
      market_cap: Math.floor(5e9 + Math.random() * 1e12),
    })
  }
  return stocks.sort((a, b) => b.weight - a.weight)
}

// ---- 数据加载 ----
async function loadData() {
  loading.value = true
  error.value = false

  try {
    const idxCode = code.value
    // 尝试调用后端 API，失败时使用模拟数据
    let detail: IndexDetailData
    try {
      const result = await marketApi.getIndexDetail(idxCode)
      detail = { ...result } as unknown as IndexDetailData
    } catch {
      detail = buildMockIndexDetail(idxCode)
    }
    indexInfo.value = detail
    components.value = buildMockComponents(detail.components_count || 50)
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function refreshData() {
  loadData()
  message.success('数据已刷新')
}

// 监听代码变化（同一页面切换指数时重新加载）
watch(code, () => {
  if (code.value) {
    activeTab.value = 'basic'
    componentSearch.value = ''
    loadData()
  }
})

onMounted(() => { loadData() })
</script>

<style lang="scss" scoped>
/* ============================================================
   IndexDetail — 指数详情页
   - 全局背景由 MainLayout 提供，本页 transparent
   - 所有卡片半透明，透出 3D 粒子背景
   - CSS 变量驱动颜色
   ============================================================ */

.index-detail-page {
  height: 100%;
  overflow-y: auto;
  background: transparent;
  animation: fadeIn 0.3s ease-out;
}

/* ---- 半透明卡片 ---- */
:deep(.n-card) {
  --n-color: transparent !important;
  background: var(--color-bg-card, rgba(12, 18, 32, 0.72)) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);

  > .n-card-header,
  > .n-card__content,
  > .n-card-footer {
    background: transparent !important;
  }

  > .n-card__content {
    overflow: hidden;
  }
}

/* ---- 页头内价格展示 ---- */
.index-code-tag {
  font-size: 12px;
  font-weight: 500;
  color: var(--n-text-color-3);
  background: var(--color-bg-secondary, rgba(255, 255, 255, 0.06));
  padding: 2px 8px;
  border-radius: 8px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  margin-left: 8px;
  vertical-align: middle;
}

.index-price {
  font-size: 15px;
  font-weight: 700;
  color: var(--n-text-color-1);
  font-variant-numeric: tabular-nums;
}

.index-change {
  font-weight: 600;
  margin-left: 6px;
}

.index-change-pct {
  font-weight: 500;
  margin-left: 2px;
}

.index-update {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-left: 10px;
}

.index-status-tag {
  margin-left: 6px;
  vertical-align: middle;
}

/* ============================================================
   内容区
   ============================================================ */
.main-content {
  padding: 0;
}

.section {
  padding: 8px 24px;
  margin-bottom: 8px;

  &:first-child { padding-top: 20px; }
  &:last-child { padding-bottom: 24px; }
}

/* ============================================================
   B. 快速统计
   ============================================================ */
.stat-card-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;

  .stat-label {
    font-size: 13px;
    color: var(--n-text-color-3);
  }

  .stat-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--n-text-color-1);
    font-variant-numeric: tabular-nums;
  }
}

/* ============================================================
   C. K线图
   ============================================================ */
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.chart-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0;

  .title-icon {
    font-size: 16px;
    color: var(--color-primary, #448AFF);
  }
}

.chart-body {
  min-height: 420px;
}

/* ============================================================
   D. 选项卡
   ============================================================ */
.info-descriptions {
  margin-top: 4px;
}

/* ---- 成分股工具栏 ---- */
.components-toolbar {
  margin-bottom: 12px;
}

.search-input {
  max-width: 300px;
}

/* ---- 成分股表格 ---- */
:deep(.component-row) {
  cursor: pointer;

  &:hover {
    background: var(--color-bg-hover, rgba(68, 138, 255, 0.05)) !important;
  }
}

/* ============================================================
   状态色工具类
   ============================================================ */
.text-up {
  color: var(--color-stock-up, #FF5252);
  font-weight: 500;
}

.text-down {
  color: var(--color-stock-down, #00E676);
  font-weight: 500;
}


/* ---- 响应式 ---- */
@media (max-width: 1024px) {
  .page-header .header-content {
    flex-wrap: wrap;
  }
  .index-price { font-size: 14px; }
}

@media (max-width: 768px) {
  .section {
    padding-left: 12px;
    padding-right: 12px;
  }

  .chart-body {
    min-height: 300px;
  }

  .search-input {
    max-width: 100%;
  }
}

/* ---- 入场动画 ---- */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
</style>
