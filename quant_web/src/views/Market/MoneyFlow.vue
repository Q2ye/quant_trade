<!-- MoneyFlow.vue - 资金流向分析页面 - Naive UI 实现 -->
<template>
  <n-layout class="money-flow-page">
    <!-- 页面标题区域 -->
    <n-layout-header class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">资金流向分析</h1>
          <p class="page-description">实时追踪主力资金动向与市场资金分布</p>
        </div>
        <div class="header-actions">
          <!-- 时间周期选择 -->
          <n-radio-group v-model:value="activePeriod" size="small" class="period-selector">
            <n-radio-button
              v-for="period in periodOptions"
              :key="period.value"
              :value="period.value"
              :label="period.label"
            />
          </n-radio-group>
          <n-button
            :loading="loading"
            @click="refreshData"
            class="refresh-btn"
          >
            <template #icon>
              <n-icon>
                <RefreshIcon />
              </n-icon>
            </template>
            {{ loading ? '刷新中...' : '刷新' }}
          </n-button>
          <n-button @click="handleBack" class="back-btn">
            <template #icon>
              <n-icon>
                <ArrowBackIcon />
              </n-icon>
            </template>
            返回
          </n-button>
        </div>
      </div>
    </n-layout-header>

    <!-- 主要内容区域 -->
    <n-layout-content class="main-content">
      <!-- 资金流向概览 -->
      <section class="flow-overview">
        <n-grid :cols="4" :x-gap="16">
          <n-gi>
            <n-card class="flow-card inflow">
              <n-statistic label="主力净流入" :value="formatAmount(flowData.mainInflow)">
                <template #prefix>
                  <n-icon class="flow-icon" :component="ArrowDownwardIcon" />
                </template>
                <template #suffix>
                  <div class="flow-change">
                    <n-text type="success">+{{ flowData.mainChange }}%</n-text>
                    <span> 较昨日</span>
                  </div>
                </template>
              </n-statistic>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card class="flow-card outflow">
              <n-statistic label="主力净流出" :value="formatAmount(flowData.mainOutflow)">
                <template #prefix>
                  <n-icon class="flow-icon" :component="ArrowUpwardIcon" />
                </template>
                <template #suffix>
                  <div class="flow-change">
                    <n-text type="error">-{{ flowData.outflowChange }}%</n-text>
                    <span> 较昨日</span>
                  </div>
                </template>
              </n-statistic>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card class="flow-card total">
              <n-statistic
                label="净流入总额"
                :value="formatAmount(flowData.netFlow, true)"
                :value-style="getNetFlowStyle(flowData.netFlow)"
              >
                <template #prefix>
                  <n-icon class="flow-icon" :component="TrendingUpIcon" />
                </template>
                <template #suffix>
                  <div class="flow-change">
                    <n-text :type="flowData.netFlowChange >= 0 ? 'success' : 'error'">
                      {{ formatAmount(flowData.netFlowChange, true) }}
                    </n-text>
                    <span> 较昨日</span>
                  </div>
                </template>
              </n-statistic>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card class="flow-card turnover">
              <n-statistic label="成交总额" :value="formatAmount(flowData.turnover)">
                <template #prefix>
                  <n-icon class="flow-icon" :component="SwapHorizIcon" />
                </template>
                <template #suffix>
                  <div class="flow-change">
                    <n-text type="success">+{{ flowData.turnoverChange }}%</n-text>
                    <span> 较昨日</span>
                  </div>
                </template>
              </n-statistic>
            </n-card>
          </n-gi>
        </n-grid>
      </section>

      <!-- 资金流向图表 -->
      <section class="flow-charts">
        <n-grid :cols="2" :x-gap="16">
          <n-gi>
            <n-card title="资金流向趋势">
              <template #header-extra>
                <n-radio-group v-model:value="chartType" size="small">
                  <n-radio-button value="line" label="折线图" />
                  <n-radio-button value="bar" label="柱状图" />
                </n-radio-group>
              </template>
              <div class="chart-container">
                <div class="chart-placeholder">
                  <n-icon class="placeholder-icon" :component="LineChartIcon" />
                  <p>资金流向趋势图表</p>
                </div>
              </div>
            </n-card>
          </n-gi>
          <n-gi>
            <n-card title="行业资金分布">
              <div class="chart-container">
                <div class="chart-placeholder">
                  <n-icon class="placeholder-icon" :component="PieChartIcon" />
                  <p>行业资金分布图表</p>
                </div>
              </div>
            </n-card>
          </n-gi>
        </n-grid>
      </section>

      <!-- 资金流向明细 -->
      <section class="flow-details">
        <n-card title="资金流向明细">
          <template #header-extra>
            <div class="header-tools">
              <n-input
                v-model:value="searchQuery"
                placeholder="搜索股票代码或名称"
                clearable
                class="search-input"
              >
                <template #prefix>
                  <n-icon :component="SearchIcon" />
                </template>
              </n-input>
              <n-select
                v-model:value="filterIndustry"
                :options="industryOptions"
                placeholder="全部行业"
                clearable
                style="width: 150px;"
              />
            </div>
          </template>

          <n-data-table
            :columns="columns"
            :data="filteredFlowData"
            :pagination="paginationConfig"
            :loading="loading"
            :bordered="false"
          />

          <template #footer>
            <div class="pagination-info">
              共 {{ totalCount }} 条数据
            </div>
          </template>
        </n-card>
      </section>
    </n-layout-content>
  </n-layout>
</template>

<script setup>
import { h, computed, onMounted, ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import {
  NLayout,
  NLayoutHeader,
  NLayoutContent,
  NCard,
  NButton,
  NIcon,
  NGrid,
  NGi,
  NStatistic,
  NDataTable,
  NInput,
  NSelect,
  NRadioGroup,
  NRadioButton,
  NText,
  NTag,
  useMessage
} from 'naive-ui'
import {
  RefreshRound as RefreshIcon,
  ArrowBackFilled as ArrowBackIcon,
  SearchFilled as SearchIcon,
  ArrowDownwardFilled as ArrowDownwardIcon,
  ArrowUpwardFilled as ArrowUpwardIcon,
  TrendingUpFilled as TrendingUpIcon,
  SwapHorizFilled as SwapHorizIcon,
  MultilineChartFilled as LineChartIcon,
  PieChartFilled as PieChartIcon
} from '@vicons/material'

const router = useRouter()
const message = useMessage()

// 响应式数据
const activePeriod = ref('today')
const chartType = ref('line')
const searchQuery = ref('')
const filterIndustry = ref('')
const loading = ref(false)

// 时间周期选项
const periodOptions = [
  { label: '今日', value: 'today' },
  { label: '5日', value: '5d' },
  { label: '10日', value: '10d' }
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

// 行业选项
const industryOptions = computed(() => [
  { label: '全部行业', value: '' },
  ...industries.value.map(industry => ({ label: industry, value: industry }))
])

// 分页配置
const paginationConfig = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page) => {
    paginationConfig.page = page
  },
  onUpdatePageSize: (pageSize) => {
    paginationConfig.pageSize = pageSize
    paginationConfig.page = 1
  }
})

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

  paginationConfig.itemCount = data.length

  // 分页
  const start = (paginationConfig.page - 1) * paginationConfig.pageSize
  const end = start + paginationConfig.pageSize
  return data.slice(start, end)
})

const totalCount = computed(() => paginationConfig.itemCount)

// 表格列定义
const columns = computed(() => [
  {
    title: '代码',
    key: 'code',
    render: (row) => {
      return h('div', { class: 'code-cell' }, [
        h('div', { class: 'code' }, row.code),
        h(NTag, {
          size: 'small',
          type: getExchangeType(row.exchange)
        }, { default: () => getExchangeText(row.exchange) })
      ])
    }
  },
  {
    title: '名称',
    key: 'name',
    render: (row) => {
      return h('div', { class: 'name-cell' }, [
        h('span', { class: 'name' }, row.name),
        row.is_st && h(NTag, {
          size: 'small',
          type: 'error'
        }, { default: () => 'ST' })
      ])
    }
  },
  {
    title: '行业',
    key: 'industry',
    render: (row) => h(NTag, { type: 'info' }, { default: () => row.industry })
  },
  {
    title: '主力净流入(万)',
    key: 'mainInflow',
    align: 'right',
    render: (row) => h('span', {
      class: getFlowClass(row.mainInflow)
    }, formatAmount(row.mainInflow, true))
  },
  {
    title: '散户净流入(万)',
    key: 'retailInflow',
    align: 'right',
    render: (row) => h('span', {
      class: getFlowClass(row.retailInflow)
    }, formatAmount(row.retailInflow, true))
  },
  {
    title: '总净流入(万)',
    key: 'totalInflow',
    align: 'right',
    render: (row) => h('span', {
      class: getFlowClass(row.totalInflow)
    }, formatAmount(row.totalInflow, true))
  },
  {
    title: '净流入率',
    key: 'inflowRate',
    align: 'right',
    render: (row) => h('span', {
      class: getFlowClass(row.inflowRate)
    }, `${row.inflowRate > 0 ? '+' : ''}${row.inflowRate.toFixed(2)}%`)
  },
  {
    title: '成交额(万)',
    key: 'turnover',
    align: 'right',
    render: (row) => formatAmount(row.turnover)
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) => h(NButton, {
      size: 'small',
      type: 'primary',
      onClick: () => viewStockDetail(row)
    }, { default: () => '详情' })
  }
])

// 方法
const handleBack = () => {
  router.go(-1)
}

const refreshData = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('数据刷新成功')
  } finally {
    loading.value = false
  }
}

const getExchangeType = (exchange) => {
  const types = {
    'SSE': 'error',
    'SZSE': 'primary',
    'BSE': 'warning'
  }
  return types[exchange] || 'default'
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

const getNetFlowStyle = (value) => {
  return {
    color: value >= 0 ? '#52c41a' : '#f5222d'
  }
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
@use '@/assets/scss/mixins' as mixin;
@use '@/assets/scss/variables' as *;
@use 'sass:map';
@use 'sass:color' as scssColor;

// ============================================================================
// 资金流向页面主容器
// ============================================================================
.market-dashboard-page {
  @include mixin.content-with-base;

  .main-content {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容区域混入
    margin: 0 auto; // 水平居中
  }
}

// ============================================================================
// 页面头部样式 - 使用混入统一管理
// ============================================================================
// 使用专门为 Naive UI 优化的混入
.page-header {
  @include mixin.page-header-base;
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
    margin-top: map.get($spacers, 5); // 顶部外边距：使用spacers映射中的第6个值
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

</style>