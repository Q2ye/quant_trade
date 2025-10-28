<template>
  <div class="money-flow-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">资金流向分析</h1>
          <p class="page-description">实时追踪主力资金动向与市场资金分布</p>
        </div>
        <div class="header-actions-right">
          <a-button-group class="period-buttons">
            <a-button
                :type="activePeriod === 'today' ? 'primary' : 'default'"
                @click="activePeriod = 'today'"
                size="small"
            >
              今日
            </a-button>
            <a-button
                :type="activePeriod === '5d' ? 'primary' : 'default'"
                @click="activePeriod = '5d'"
                size="small"
            >
              5日
            </a-button>
            <a-button
                :type="activePeriod === '10d' ? 'primary' : 'default'"
                @click="activePeriod = '10d'"
                size="small"
            >
              10日
            </a-button>
          </a-button-group>
          <a-button type="primary" @click="refreshData" size="small" class="action-btn">
            <template #icon>
              <ReloadOutlined/>
            </template>
            刷新
          </a-button>
          <a-button class="back-btn" @click="handleBack">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>
    <!-- 资金流向概览 -->
    <div class="flow-overview">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card class="flow-card inflow" shadow="hover">
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
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="flow-card outflow" shadow="hover">
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
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="flow-card total" shadow="hover">
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
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="flow-card turnover" shadow="hover">
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
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 资金流向图表 -->
    <div class="flow-charts">
      <el-row :gutter="16">
        <el-col :span="16">
          <el-card class="chart-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="card-title">资金流向趋势</span>
                <div class="chart-controls">
                  <el-radio-group v-model="chartType" size="small">
                    <el-radio-button label="line">折线图</el-radio-button>
                    <el-radio-button label="bar">柱状图</el-radio-button>
                  </el-radio-group>
                </div>
              </div>
            </template>
            <div class="chart-container">
              <!-- 这里可以接入ECharts图表 -->
              <div class="chart-placeholder">
                <Icon icon="mdi:chart-line" class="placeholder-icon"/>
                <p>资金流向趋势图表</p>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="chart-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="card-title">行业资金分布</span>
              </div>
            </template>
            <div class="chart-container">
              <!-- 这里可以接入ECharts饼图 -->
              <div class="chart-placeholder">
                <Icon icon="mdi:chart-pie" class="placeholder-icon"/>
                <p>行业资金分布图表</p>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 资金流向明细 -->
    <div class="flow-details">
      <el-card class="data-card" shadow="never">
        <template #header>
          <div class="card-header">
            <span class="card-title">资金流向明细</span>
            <div class="header-actions">
              <el-input
                  v-model="searchQuery"
                  placeholder="搜索股票代码或名称"
                  style="width: 200px"
                  clearable
                  size="small"
                  prefix-icon="Search"
              />
              <el-select v-model="filterIndustry" placeholder="行业" clearable size="small">
                <el-option
                    v-for="industry in industries"
                    :key="industry"
                    :label="industry"
                    :value="industry"
                />
              </el-select>
            </div>
          </div>
        </template>

        <el-table
            :data="filteredFlowData"
            v-loading="loading"
            style="width: 100%"
            stripe
            size="small"
        >
          <el-table-column prop="code" label="代码" width="120">
            <template #default="scope">
              <div class="code-cell">
                <span class="code">{{ scope.row.code }}</span>
                <span class="exchange" :class="getExchangeClass(scope.row.exchange)">
                  {{ getExchangeText(scope.row.exchange) }}
                </span>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="name" label="名称" min-width="150">
            <template #default="scope">
              <div class="name-cell">
                <span class="name">{{ scope.row.name }}</span>
                <el-tag
                    v-if="scope.row.is_st"
                    size="small"
                    type="danger"
                    effect="plain"
                >
                  ST
                </el-tag>
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="industry" label="行业" width="120">
            <template #default="scope">
              <el-tag size="small" effect="plain" class="industry-tag">
                {{ scope.row.industry }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column prop="mainInflow" label="主力净流入(万)" width="140" align="right" sortable>
            <template #default="scope">
              <span :class="getFlowClass(scope.row.mainInflow)">
                {{ formatAmount(scope.row.mainInflow, true) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column prop="retailInflow" label="散户净流入(万)" width="140" align="right" sortable>
            <template #default="scope">
              <span :class="getFlowClass(scope.row.retailInflow)">
                {{ formatAmount(scope.row.retailInflow, true) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column prop="totalInflow" label="总净流入(万)" width="140" align="right" sortable>
            <template #default="scope">
              <span :class="getFlowClass(scope.row.totalInflow)">
                {{ formatAmount(scope.row.totalInflow, true) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column prop="inflowRate" label="净流入率" width="120" align="right" sortable>
            <template #default="scope">
              <span :class="getFlowClass(scope.row.inflowRate)">
                {{ scope.row.inflowRate > 0 ? '+' : '' }}{{ scope.row.inflowRate.toFixed(2) }}%
              </span>
            </template>
          </el-table-column>

          <el-table-column prop="turnover" label="成交额(万)" width="140" align="right" sortable>
            <template #default="scope">
              {{ formatAmount(scope.row.turnover) }}
            </template>
          </el-table-column>

          <el-table-column label="操作" width="100" fixed="right">
            <template #default="scope">
              <el-button
                  size="small"
                  @click="viewStockDetail(scope.row)"
                  class="detail-btn"
              >
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-container">
          <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[20, 50, 100]"
              :total="totalCount"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
              size="small"
          />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import {computed, onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {ElMessage} from 'element-plus'
import {Icon} from '@iconify/vue'
import {ArrowLeftOutlined, ReloadOutlined} from '@ant-design/icons-vue'

const router = useRouter()
// 返回按钮处理
const handleBack = () => {
  router.go(-1)
}

// 响应式数据
const activePeriod = ref('today')
const chartType = ref('line')
const searchQuery = ref('')
const filterIndustry = ref('')
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

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
const refreshData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    ElMessage.success('数据刷新成功')
  } catch (error) {
    ElMessage.error('数据刷新失败')
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

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page) => {
  currentPage.value = page
}

// 生命周期
onMounted(() => {
  // 初始化数据
})
</script>

<style lang="scss" scoped>
.money-flow-page {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100%;

  .page-header {
    background: var(--page-header-bg, linear-gradient(135deg, var(--accent-color) 0%, color-mix(in srgb, var(--accent-color) 60%, #6f42c1) 100%));
    color: white;
    padding: 20px 0;
    margin-bottom: 20px;

    .header-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      max-width: 1400px;
      margin: 0 auto;
      padding: 0 var(--spacer-4);
      position: relative;

      .header-actions-right {
        display: flex;
        align-items: center;
        gap: 8px; /* 减小间距，使按钮更紧凑 */
        flex-shrink: 0;
      }
    }

    .title-section {
      flex: 1;

      .page-title {
        margin: 0;
        font-size: 24px;
        font-weight: 600;
        color: white;
      }

      .page-description {
        margin: 6px 0 0 0;
        opacity: 0.9;
        font-size: 13px;
      }
    }
  }

  // 周期按钮组样式
  .period-buttons {
    :deep(.ant-btn) {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: white;

      &:hover {
        background: rgba(255, 255, 255, 0.2);
        border-color: rgba(255, 255, 255, 0.5);
        color: white;
      }

      &.ant-btn-primary {
        background: rgba(255, 255, 255, 0.3);
        border-color: rgba(255, 255, 255, 0.5);
      }
    }
  }

  // 操作按钮样式
  .action-btn {
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: white;
    border-radius: var(--border-radius, 6px);
    font-weight: 500;
    transition: all var(--transition-fast, 0.3s);
    backdrop-filter: blur(10px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    height: 32px;
    display: flex;
    align-items: center;
    gap: 6px;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
      border-color: rgba(255, 255, 255, 0.5);
      color: white;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    &:active {
      transform: translateY(0);
    }
  }

  // 返回按钮样式 - 与StockList保持一致
  .back-btn {
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: white;
    border-radius: var(--border-radius, 6px);
    font-weight: 500;
    transition: all var(--transition-fast, 0.3s);
    backdrop-filter: blur(10px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    height: 32px;
    display: flex;
    align-items: center;
    gap: 6px;

    &:hover {
      background: rgba(255, 255, 255, 0.25);
      border-color: rgba(255, 255, 255, 0.5);
      color: white;
      transform: translateY(-1px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }

    &:active {
      transform: translateY(0);
    }
  }

  .flow-overview {
    margin-bottom: var(--spacer-4);

    .flow-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);
      transition: all var(--transition-normal);

      &:hover {
        transform: var(--hover-transform);
        box-shadow: var(--hover-shadow);
      }

      &.inflow {
        border-left: 4px solid var(--success-color, #28a745);
      }

      &.outflow {
        border-left: 4px solid var(--danger-color, #dc3545);
      }

      &.total {
        border-left: 4px solid var(--accent-color);
      }

      &.turnover {
        border-left: 4px solid var(--warning-color, #ffc107);
      }

      .flow-content {
        display: flex;
        align-items: center;
        padding: var(--spacer-3);

        .flow-icon {
          font-size: 2.5rem;
          margin-right: var(--spacer-3);
          opacity: 0.8;
        }

        .flow-info {
          .flow-value {
            font-size: 1.5rem;
            font-weight: var(--font-weight-bold);
            color: var(--text-primary);
            margin-bottom: var(--spacer-1);

            &.flow-positive {
              color: var(--success-color, #28a745);
            }

            &.flow-negative {
              color: var(--danger-color, #dc3545);
            }
          }

          .flow-label {
            font-size: calc(var(--font-size-base) - 2px);
            color: var(--text-secondary);
            margin-bottom: var(--spacer-1);
          }

          .flow-change {
            font-size: calc(var(--font-size-base) - 4px);
            color: var(--text-secondary);

            .positive {
              color: var(--success-color, #28a745);
              font-weight: var(--font-weight-semibold);
            }

            .negative {
              color: var(--danger-color, #dc3545);
              font-weight: var(--font-weight-semibold);
            }
          }
        }
      }
    }
  }

  .flow-charts {
    margin-bottom: var(--spacer-4);

    .chart-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);

      :deep(.el-card__header) {
        background: var(--secondary-bg);
        border-bottom: 1px solid var(--border-color);
        padding: var(--spacer-3);
      }

      :deep(.el-card__body) {
        padding: var(--spacer-3);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .chart-container {
        height: 300px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--chart-bg);
        border-radius: var(--border-radius-sm);

        .chart-placeholder {
          text-align: center;
          color: var(--text-secondary);

          .placeholder-icon {
            font-size: 3rem;
            margin-bottom: var(--spacer-2);
            opacity: 0.5;
          }

          p {
            margin: 0;
            font-size: calc(var(--font-size-base) - 2px);
          }
        }
      }
    }
  }

  .flow-details {
    .data-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);

      :deep(.el-card__header) {
        background: var(--secondary-bg);
        border-bottom: 1px solid var(--border-color);
        padding: var(--spacer-3);
      }

      :deep(.el-card__body) {
        padding: var(--spacer-3);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .header-actions {
        display: flex;
        gap: var(--spacer-2);
        align-items: center;
      }
    }

    :deep(.el-table) {
      background: var(--card-bg);
      color: var(--text-primary);

      .el-table__header {
        th {
          background: var(--secondary-bg);
          color: var(--text-primary);
          font-weight: var(--font-weight-semibold);
          border-bottom: 1px solid var(--border-color);
        }
      }

      .el-table__body {
        tr {
          background: var(--card-bg);

          &:hover > td {
            background: var(--hover-bg) !important;
          }

          td {
            border-bottom: 1px solid var(--border-color);
            background: var(--card-bg);
          }
        }
      }
    }

    .code-cell {
      display: flex;
      flex-direction: column;
      gap: var(--spacer-1);

      .code {
        font-weight: var(--font-weight-semibold);
        color: var(--text-primary);
        font-family: var(--font-family-mono, monospace);
      }

      .exchange {
        font-size: calc(var(--font-size-base) - 4px);
        padding: 2px 6px;
        border-radius: var(--border-radius-sm);
        text-align: center;
        width: fit-content;
        font-weight: var(--font-weight-medium);

        &.exchange-sh {
          background: color-mix(in srgb, var(--danger-color, #dc3545) 10%, transparent);
          color: var(--danger-color, #dc3545);
          border: 1px solid color-mix(in srgb, var(--danger-color, #dc3545) 30%, transparent);
        }

        &.exchange-sz {
          background: color-mix(in srgb, var(--accent-color) 10%, transparent);
          color: var(--accent-color);
          border: 1px solid color-mix(in srgb, var(--accent-color) 30%, transparent);
        }

        &.exchange-bj {
          background: color-mix(in srgb, var(--warning-color, #ffc107) 10%, transparent);
          color: var(--warning-color, #ffc107);
          border: 1px solid color-mix(in srgb, var(--warning-color, #ffc107) 30%, transparent);
        }
      }
    }

    .name-cell {
      display: flex;
      align-items: center;
      gap: var(--spacer-1);
    }

    .flow-positive {
      color: var(--success-color, #28a745);
      font-weight: var(--font-weight-semibold);
    }

    .flow-negative {
      color: var(--danger-color, #dc3545);
      font-weight: var(--font-weight-semibold);
    }

    .flow-neutral {
      color: var(--text-secondary);
      font-weight: var(--font-weight-medium);
    }

    .industry-tag {
      background: color-mix(in srgb, var(--accent-color) 8%, transparent);
      color: var(--accent-color);
      border-color: color-mix(in srgb, var(--accent-color) 20%, transparent);
      font-size: calc(var(--font-size-base) - 2px);
    }

    .detail-btn {
      background: color-mix(in srgb, var(--accent-color) 8%, transparent);
      color: var(--accent-color);
      border-color: color-mix(in srgb, var(--accent-color) 20%, transparent);
      font-size: calc(var(--font-size-base) - 2px);

      &:hover {
        background: var(--accent-color);
        color: white;
        border-color: var(--accent-color);
      }
    }

    .pagination-container {
      display: flex;
      justify-content: flex-end;
      margin-top: var(--spacer-3);
      padding-top: var(--spacer-3);
      border-top: 1px solid var(--border-color);
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .money-flow-page {
    padding: var(--spacer-2);

    .page-header .header-content {
      flex-direction: column;
      gap: var(--spacer-2);
      align-items: flex-start;
    }

    .flow-overview .flow-card .flow-content {
      flex-direction: column;
      text-align: center;

      .flow-icon {
        margin-right: 0;
        margin-bottom: var(--spacer-2);
      }
    }

    .card-header {
      flex-direction: column;
      gap: var(--spacer-2);
      align-items: flex-start;
    }

    .header-actions {
      flex-direction: column;
      width: 100%;

      .el-input,
      .el-select {
        width: 100% !important;
      }
    }
  }
}

// 主题过渡支持
.money-flow-page {
  transition: background-color var(--transition-normal),
  color var(--transition-normal),
  border-color var(--transition-normal);
}
</style>