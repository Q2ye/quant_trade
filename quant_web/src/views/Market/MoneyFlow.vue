<!-- MoneyFlow.vue - 资金流向分析页面 -->
<!-- 基于全局主题样式系统重构，统一使用主题变量和混入 -->
<template>
  <div class="money-flow-page">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">资金流向分析</h1>
          <p class="page-description">实时追踪主力资金动向与市场资金分布</p>
        </div>
        <div class="header-actions">
          <!-- 时间周期选择 -->
          <div class="period-selector">
            <button
                v-for="period in periodOptions"
                :key="period.value"
                :class="['period-btn', { active: activePeriod === period.value }]"
                @click="activePeriod = period.value"
            >
              {{ period.label }}
            </button>
          </div>
          <button class="refresh-btn" @click="refreshData" :disabled="loading">
            <Icon icon="ant-design:reload-outlined" class="refresh-icon" :class="{ refreshing: loading }"/>
            <span class="btn-text">{{ loading ? '刷新中...' : '刷新' }}</span>
          </button>
          <button class="back-btn" @click="handleBack">
            <Icon icon="ant-design:arrow-left-outlined"/>
            <span class="btn-text">返回</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content-with-sidebar">
      <!-- 资金流向概览 -->
      <section class="flow-overview">
        <div class="stats-grid">
          <!-- 主力净流入 -->
          <div class="flow-card card inflow">
            <div class="flow-content">
              <div class="flow-icon">
                <Icon icon="mdi:arrow-down"/>
              </div>
              <div class="flow-info">
                <div class="flow-value">+{{ formatAmount(flowData.mainInflow) }}</div>
                <div class="flow-label">主力净流入</div>
                <div class="flow-change">
                  <span class="positive">+{{ flowData.mainChange }}%</span>
                  较昨日
                </div>
              </div>
            </div>
          </div>

          <!-- 主力净流出 -->
          <div class="flow-card card outflow">
            <div class="flow-content">
              <div class="flow-icon">
                <Icon icon="mdi:arrow-up"/>
              </div>
              <div class="flow-info">
                <div class="flow-value">-{{ formatAmount(flowData.mainOutflow) }}</div>
                <div class="flow-label">主力净流出</div>
                <div class="flow-change">
                  <span class="negative">-{{ flowData.outflowChange }}%</span>
                  较昨日
                </div>
              </div>
            </div>
          </div>

          <!-- 净流入总额 -->
          <div class="flow-card card total">
            <div class="flow-content">
              <div class="flow-icon">
                <Icon icon="mdi:chart-line"/>
              </div>
              <div class="flow-info">
                <div class="flow-value" :class="getNetFlowClass(flowData.netFlow)">
                  {{ formatAmount(flowData.netFlow, true) }}
                </div>
                <div class="flow-label">净流入总额</div>
                <div class="flow-change">
                  <span :class="getNetFlowClass(flowData.netFlow)">
                    {{ formatAmount(flowData.netFlowChange, true) }}
                  </span>
                  较昨日
                </div>
              </div>
            </div>
          </div>

          <!-- 成交总额 -->
          <div class="flow-card card turnover">
            <div class="flow-content">
              <div class="flow-icon">
                <Icon icon="mdi:swap-horizontal"/>
              </div>
              <div class="flow-info">
                <div class="flow-value">{{ formatAmount(flowData.turnover) }}</div>
                <div class="flow-label">成交总额</div>
                <div class="flow-change">
                  <span class="positive">+{{ flowData.turnoverChange }}%</span>
                  较昨日
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 资金流向图表 -->
      <section class="flow-charts">
        <div class="charts-grid">
          <!-- 资金流向趋势 -->
          <div class="chart-card card">
            <div class="card-header">
              <h3 class="card-title">资金流向趋势</h3>
              <div class="chart-controls">
                <div class="chart-type-selector">
                  <button
                      v-for="type in chartTypeOptions"
                      :key="type.value"
                      :class="['chart-type-btn', { active: chartType === type.value }]"
                      @click="chartType = type.value"
                  >
                    {{ type.label }}
                  </button>
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="chart-container">
                <div class="chart-placeholder">
                  <Icon icon="mdi:chart-line" class="placeholder-icon"/>
                  <p>资金流向趋势图表</p>
                </div>
              </div>
            </div>
          </div>

          <!-- 行业资金分布 -->
          <div class="chart-card card">
            <div class="card-header">
              <h3 class="card-title">行业资金分布</h3>
            </div>
            <div class="card-body">
              <div class="chart-container">
                <div class="chart-placeholder">
                  <Icon icon="mdi:chart-pie" class="placeholder-icon"/>
                  <p>行业资金分布图表</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 资金流向明细 -->
      <section class="flow-details">
        <div class="data-card card">
          <div class="card-header">
            <h3 class="card-title">资金流向明细</h3>
            <div class="header-actions">
              <!-- 搜索框 -->
              <div class="search-box">
                <Icon icon="mdi:magnify" class="search-icon"/>
                <input
                    v-model="searchQuery"
                    type="text"
                    placeholder="搜索股票代码或名称"
                    class="search-input"
                />
              </div>
              <!-- 行业筛选 -->
              <select v-model="filterIndustry" class="filter-select">
                <option value="">全部行业</option>
                <option
                    v-for="industry in industries"
                    :key="industry"
                    :value="industry"
                >
                  {{ industry }}
                </option>
              </select>
            </div>
          </div>
          <div class="card-body">
            <!-- 数据表格 -->
            <div class="table-container">
              <table class="data-table">
                <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>行业</th>
                  <th>主力净流入(万)</th>
                  <th>散户净流入(万)</th>
                  <th>总净流入(万)</th>
                  <th>净流入率</th>
                  <th>成交额(万)</th>
                  <th>操作</th>
                </tr>
                </thead>
                <tbody>
                <tr
                    v-for="item in filteredFlowData"
                    :key="item.code"
                    class="table-row"
                >
                  <td class="code-cell">
                    <div class="code">{{ item.code }}</div>
                    <span :class="['exchange-tag', getExchangeClass(item.exchange)]">
                        {{ getExchangeText(item.exchange) }}
                      </span>
                  </td>
                  <td class="name-cell">
                    <span class="name">{{ item.name }}</span>
                    <span v-if="item.is_st" class="st-tag">ST</span>
                  </td>
                  <td>
                    <span class="industry-tag">{{ item.industry }}</span>
                  </td>
                  <td class="amount-cell">
                      <span :class="getFlowClass(item.mainInflow)">
                        {{ formatAmount(item.mainInflow, true) }}
                      </span>
                  </td>
                  <td class="amount-cell">
                      <span :class="getFlowClass(item.retailInflow)">
                        {{ formatAmount(item.retailInflow, true) }}
                      </span>
                  </td>
                  <td class="amount-cell">
                      <span :class="getFlowClass(item.totalInflow)">
                        {{ formatAmount(item.totalInflow, true) }}
                      </span>
                  </td>
                  <td class="rate-cell">
                      <span :class="getFlowClass(item.inflowRate)">
                        {{ item.inflowRate > 0 ? '+' : '' }}{{ item.inflowRate.toFixed(2) }}%
                      </span>
                  </td>
                  <td class="amount-cell">
                    {{ formatAmount(item.turnover) }}
                  </td>
                  <td class="action-cell">
                    <button class="detail-btn" @click="viewStockDetail(item)">
                      详情
                    </button>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>

            <!-- 加载状态 -->
            <div v-if="loading" class="loading-state">
              <div class="loading-spinner"></div>
              <p>数据加载中...</p>
            </div>

            <!-- 分页控件 -->
            <div class="pagination-container">
              <div class="pagination">
                <button
                    class="pagination-btn"
                    :disabled="currentPage === 1"
                    @click="currentPage--"
                >
                  上一页
                </button>
                <span class="pagination-info">
                  第 {{ currentPage }} 页，共 {{ Math.ceil(totalCount / pageSize) }} 页
                </span>
                <button
                    class="pagination-btn"
                    :disabled="currentPage * pageSize >= totalCount"
                    @click="currentPage++"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import {computed, onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'

const router = useRouter()

// 响应式数据
const activePeriod = ref('today')
const chartType = ref('line')
const searchQuery = ref('')
const filterIndustry = ref('')
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

// 时间周期选项
const periodOptions = [
  {label: '今日', value: 'today'},
  {label: '5日', value: '5d'},
  {label: '10日', value: '10d'}
]

// 图表类型选项
const chartTypeOptions = [
  {label: '折线图', value: 'line'},
  {label: '柱状图', value: 'bar'}
]

// 资金流向数据
const flowData = ref({
  mainInflow: 1256700,
  mainOutflow: 892300,
  netFlow: 364400,
  turnover: 8456700,
  mainChange: 12.5,
  outflowChange: 8.3,
  netFlowChange: 123400,
  turnoverChange: 15.2
})

// 资金流向明细数据
const flowDetails = ref([
  {
    code: '000001',
    name: '平安银行',
    exchange: 'SZSE',
    industry: '银行',
    mainInflow: 12567,
    retailInflow: -2345,
    totalInflow: 10222,
    inflowRate: 2.34,
    turnover: 156789,
    is_st: false
  },
  {
    code: '300750',
    name: '宁德时代',
    exchange: 'SZSE',
    industry: '电气设备',
    mainInflow: 89234,
    retailInflow: 12345,
    totalInflow: 101579,
    inflowRate: 3.45,
    turnover: 234567,
    is_st: false
  },
  {
    code: '600036',
    name: '招商银行',
    exchange: 'SSE',
    industry: '银行',
    mainInflow: -4567,
    retailInflow: 2345,
    totalInflow: -2222,
    inflowRate: -1.23,
    turnover: 123456,
    is_st: false
  }
])

const industries = ref(['银行', '证券', '保险', '电子', '计算机', '医药生物', '电气设备'])

// 计算属性
const filteredFlowData = computed(() => {
  let data = flowDetails.value

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    data = data.filter(item =>
        item.code.toLowerCase().includes(query) ||
        item.name.toLowerCase().includes(query)
    )
  }

  // 行业过滤
  if (filterIndustry.value) {
    data = data.filter(item => item.industry === filterIndustry.value)
  }

  totalCount.value = data.length

  // 分页
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return data.slice(start, end)
})

// 方法
const handleBack = () => {
  router.go(-1)
}

const refreshData = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
  } finally {
    loading.value = false
  }
}

const getExchangeClass = (exchange) => {
  const classes = {
    'SSE': 'exchange-sh',
    'SZSE': 'exchange-sz',
    'BSE': 'exchange-bj'
  }
  return classes[exchange] || ''
}

const getExchangeText = (exchange) => {
  const texts = {
    'SSE': '沪',
    'SZSE': '深',
    'BSE': '京'
  }
  return texts[exchange] || exchange
}

const getFlowClass = (value) => {
  if (value > 0) return 'flow-positive'
  if (value < 0) return 'flow-negative'
  return 'flow-neutral'
}

const getNetFlowClass = (value) => {
  return value >= 0 ? 'flow-positive' : 'flow-negative'
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

const viewStockDetail = (row) => {
  router.push(`/market/stock/${row.code}`)
}

// 生命周期
onMounted(() => {
  // 初始化数据
})
</script>

<style scoped lang="scss">
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color' as scssColor;


.money-flow-page {
  min-height: 100vh;
  background: $primary-bg;
  transition: all $transition-normal; // 所有属性使用标准过渡时间

  .main-content-with-sidebar {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容区域混入
    margin: 0 auto; // 水平居中
  }
}

// ============================================================================
// 页面头部样式 - 使用混入统一管理
// ============================================================================
.page-header {
  @include mixin.page-header-base; // 应用页面头部基础样式混入
  margin-bottom: map.get($spacers, 6); // 底部外边距使用间距映射中的第6个值
}

// 时间周期选择器
.period-selector {
  display: flex;
  background: $secondary-bg;
  border-radius: $border-radius;
  padding: 2px;

  .period-btn {
    @include mixin.button-base(transparent, $text-primary);
    padding: map.get($spacers, 1) map.get($spacers, 2);
    border-radius: calc($border-radius - 2px);
    font-size: calc($font-size-base - 2px);
    transition: all $transition-fast;

    &.active {
      background: $accent-color;
      color: white;
    }

    &:hover:not(.active) {
      background: $hover-bg;
    }
  }
}

// 资金流向概览
.flow-overview {
  margin-bottom: map.get($spacers, 4);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: map.get($spacers, 3);
}

.flow-card {
  @include mixin.card-base;
  padding: map.get($spacers, 3);
  border-left: 4px solid transparent;

  &.inflow {
    border-left-color: $success-color;
  }

  &.outflow {
    border-left-color: $danger-color;
  }

  &.total {
    border-left-color: $accent-color;
  }

  &.turnover {
    border-left-color: $warning-color;
  }

  .flow-content {
    display: flex;
    align-items: center;
    gap: map.get($spacers, 3);
  }

  .flow-icon {
    font-size: 2rem;
    opacity: 0.8;

    .inflow & {
      color: $success-color;
    }

    .outflow & {
      color: $danger-color;
    }

    .total & {
      color: $accent-color;
    }

    .turnover & {
      color: $warning-color;
    }
  }

  .flow-info {
    flex: 1;

    .flow-value {
      font-size: 1.5rem;
      font-weight: $font-weight-bold;
      color: $text-primary;
      margin-bottom: map.get($spacers, 1);

      &.flow-positive {
        color: $success-color;
      }

      &.flow-negative {
        color: $danger-color;
      }
    }

    .flow-label {
      font-size: calc($font-size-base - 2px);
      color: $text-secondary;
      margin-bottom: map.get($spacers, 1);
    }

    .flow-change {
      font-size: calc($font-size-base - 4px);
      color: $text-secondary;

      .positive {
        color: $success-color;
        font-weight: $font-weight-semibold
      }

      .negative {
        color: $danger-color;
        font-weight: $font-weight-semibold
      }
    }
  }
}

// 图表区域
.flow-charts {
  margin-bottom: map.get($spacers, 4);
}

.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: map.get($spacers, 4);
}

.chart-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: map.get($spacers, 3);
    border-bottom: 1px solid $border-color;
  }

  .chart-controls {
    .chart-type-selector {
      display: flex;
      background: $secondary-bg;
      border-radius: $border-radius-sm;
      padding: 2px;

      .chart-type-btn {
        @include mixin.button-base(transparent, $text-primary);
        padding: map.get($spacers, 1) map.get($spacers, 2);
        border-radius: calc($border-radius-sm - 2px);
        font-size: calc($font-size-base - 4px);

        &.active {
          background: $accent-color;
          color: white;
        }
      }
    }
  }

  .chart-container {
    height: 300px;
    @include mixin.flex-center(column);
    background: $secondary-bg;
    border-radius: $border-radius;
  }

  .chart-placeholder {
    text-align: center;
    color: $text-secondary;

    .placeholder-icon {
      font-size: 3rem;
      margin-bottom: map.get($spacers, 2);
      opacity: 0.5;
    }
  }
}

// 资金流向明细
.flow-details {
  .data-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: map.get($spacers, 3);
      border-bottom: 1px solid $border-color;
    }

    .header-actions {
      display: flex;
      gap: map.get($spacers, 3);
      align-items: center;
    }
  }
}

// 搜索框
.search-box {
  position: relative;
  display: flex;
  align-items: center;

  .search-icon {
    position: absolute;
    left: map.get($spacers, 2);
    color: $text-secondary;
    font-size: 1rem;
  }

  .search-input {
    padding: map.get($spacers, 2) map.get($spacers, 2) map.get($spacers, 2) map.get($spacers, 5);
    border: 1px solid $border-color;
    border-radius: $border-radius;
    background: $input-bg;
    color: $text-primary;
    font-size: $font-size-base;
    width: 200px;

    &:focus {
      outline: none;
      border-color: $accent-color;
    }
  }
}

// 筛选选择器
.filter-select {
  padding: map.get($spacers, 2);
  border: 1px solid $border-color;
  border-radius: $border-radius;
  background: $input-bg;
  color: $text-primary;
  font-size: $font-size-base;

  &:focus {
    outline: none;
    border-color: $accent-color;
  }
}

// 数据表格
.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: $card-bg;

  th, td {
    padding: map.get($spacers, 3);
    text-align: left;
    border-bottom: 1px solid $border-color;
  }

  th {
    background: $card-header-bg;
    font-weight: $font-weight-semibold;
    color: $text-primary;
  }

  td {
    color: $text-primary;
  }
}

.table-row {
  transition: background-color $transition-fast;

  &:hover {
    background: $hover-bg;
  }
}

// 表格单元格样式
.code-cell {
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 1);

  .code {
    font-weight: $font-weight-semibold;
    color: $text-primary;
    font-family: $font-family;
  }
}

.exchange-tag {
  font-size: calc($font-size-base - 4px);
  padding: 2px 6px;
  border-radius: $border-radius-sm;
  text-align: center;
  width: fit-content;
  font-weight: $font-weight-medium;

  &.exchange-sh {
    background: scssColor.adjust($danger-color, $alpha: -0.9);
    color: $danger-color;
    border: 1px solid scssColor.adjust($danger-color, $alpha: -0.7);
  }

  &.exchange-sz {
    background: scssColor.adjust($accent-color, $alpha: -0.9);
    color: $accent-color;
    border: 1px solid scssColor.adjust($accent-color, $alpha: -0.7);
  }

  &.exchange-bj {
    background: scssColor.adjust($warning-color, $alpha: -0.9);
    color: $warning-color;
    border: 1px solid scssColor.adjust($warning-color, $alpha: -0.7);
  }
}

.name-cell {
  display: flex;
  align-items: center;
  gap: map.get($spacers, 2);

  .st-tag {
    background: $danger-color;
    color: white;
    padding: 1px 4px;
    border-radius: $border-radius-sm;
    font-size: calc($font-size-base - 4px);
    font-weight: $font-weight-semibold
  }
}

.industry-tag {
  background: scssColor.adjust($accent-color, $alpha: -0.9);
  color: $accent-color;
  padding: map.get($spacers, 1) map.get($spacers, 2);
  border-radius: $border-radius-sm;
  font-size: calc($font-size-base - 2px);
  border: 1px solid scssColor.adjust($accent-color, $alpha: -0.7);
}

.amount-cell,
.rate-cell {
  text-align: right;
  font-family: $font-family;
}

.flow-positive {
  color: $success-color;
  font-weight: $font-weight-semibold
}

.flow-negative {
  color: $danger-color;
  font-weight: $font-weight-semibold
}

.flow-neutral {
  color: $text-secondary;
  font-weight: $font-weight-medium;
}

.action-cell .detail-btn {
  @include mixin.button-base($accent-color, white);
  padding: map.get($spacers, 1) map.get($spacers, 2);
  font-size: calc($font-size-base - 2px);

  &:hover {
    background: scssColor.adjust($accent-color, $lightness: -10%);
  }
}

// 分页样式
.pagination-container {
  margin-top: map.get($spacers, 3);
  padding-top: map.get($spacers, 3);
  border-top: 1px solid $border-color;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: map.get($spacers, 3);
}

.pagination-btn {
  @include mixin.button-base(transparent, $text-primary);
  border: 1px solid $border-color;
  padding: map.get($spacers, 2) map.get($spacers, 3);

  &:hover:not(:disabled) {
    background: $accent-color;
    color: white;
    border-color: $accent-color;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.pagination-info {
  color: $text-secondary;
  font-size: calc($font-size-base - 2px);
}

// 响应式设计
@include mixin.media-breakpoint-down(lg) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@include mixin.media-breakpoint-down(md) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .data-card .card-header {
    flex-direction: column;
    gap: map.get($spacers, 2);
    align-items: flex-start;
  }

  .header-actions {
    flex-direction: column;
    width: 100%;

    .search-box .search-input {
      width: 100%;
    }

    .filter-select {
      width: 100%;
    }
  }

  .data-table {
    font-size: calc($font-size-base - 2px);

    th, td {
      padding: map.get($spacers, 2);
    }
  }
}

@include mixin.media-breakpoint-down(sm) {
  .period-selector {
    flex-wrap: wrap;
  }

  .table-container {
    .data-table {
      min-width: 800px;
    }
  }

  .pagination {
    flex-direction: column;
    gap: map.get($spacers, 2);
  }
}
</style>