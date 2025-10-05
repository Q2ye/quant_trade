<script setup lang="ts">
import { ref, reactive, onMounted, computed, h } from 'vue'
import type { ColumnsType } from 'ant-design-vue/es/table'

interface PerformanceData {
  date: string
  total_asset: number
  cash: number
  market_value: number
  daily_pnl: number
  daily_return: number
  cumulative_return: number
}

interface Position {
  symbol: string
  name: string
  volume: number
  cost_price: number
  current_price: number
  market_value: number
  pnl: number
  pnl_ratio: number
  weight: number
}

const loading = ref(false)
const performanceData = ref<PerformanceData[]>([])
const positions = ref<Position[]>([])
const dateRange = ref<string[]>([])
const selectedPeriod = ref('1m')

const performanceMetrics = reactive({
  totalReturn: 0.156,
  annualizedReturn: 0.234,
  sharpeRatio: 1.89,
  maxDrawdown: -0.089,
  volatility: 0.156,
  winRate: 0.712
})

const columns: ColumnsType<Position> = [
  {
    title: '代码',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 100
  },
  {
    title: '名称',
    dataIndex: 'name',
    key: 'name',
    width: 120
  },
  {
    title: '持仓数量',
    dataIndex: 'volume',
    key: 'volume',
    width: 100,
    customRender: ({ text: volume }) => volume?.toLocaleString() || '0'
  },
  {
    title: '成本价',
    dataIndex: 'cost_price',
    key: 'cost_price',
    width: 100,
    customRender: ({ text: price }) => `¥${(price || 0).toFixed(2)}`
  },
  {
    title: '当前价',
    dataIndex: 'current_price',
    key: 'current_price',
    width: 100,
    customRender: ({ text: price }) => `¥${(price || 0).toFixed(2)}`
  },
  {
    title: '市值',
    dataIndex: 'market_value',
    key: 'market_value',
    width: 120,
    customRender: ({ text: value }) => `¥${((value || 0) / 10000).toFixed(2)}万`
  },
  {
    title: '盈亏',
    dataIndex: 'pnl',
    key: 'pnl',
    width: 100,
    customRender: ({ text: pnl }) => {
      const color = (pnl || 0) >= 0 ? '#f5222d' : '#52c41a'
      return h('span', { style: { color } }, [
        (pnl || 0) >= 0 ? '+' : '',
        '¥',
        (pnl || 0).toFixed(2)
      ])
    }
  },
  {
    title: '盈亏率',
    dataIndex: 'pnl_ratio',
    key: 'pnl_ratio',
    width: 100,
    customRender: ({ text: ratio }) => {
      const color = (ratio || 0) >= 0 ? '#f5222d' : '#52c41a'
      return h('span', { style: { color } }, [
        (ratio || 0) >= 0 ? '+' : '',
        ((ratio || 0) * 100).toFixed(2),
        '%'
      ])
    }
  },
  {
    title: '权重',
    dataIndex: 'weight',
    key: 'weight',
    width: 80,
    customRender: ({ text: weight }) => `${((weight || 0) * 100).toFixed(1)}%`
  }
]

const loadPerformanceData = async () => {
  loading.value = true
  try {
    // 模拟API调用
    const response = await fetch('/api/performance/account')
    const data = await response.json()
    performanceData.value = data.performance || []
    positions.value = data.positions || []
  } catch (error) {
    console.error('加载绩效数据失败:', error)
    performanceData.value = []
    positions.value = []
  } finally {
    loading.value = false
  }
}

// 修复：添加空值检查
const currentStats = computed(() => {
  if (!performanceData.value || performanceData.value.length === 0) return null
  return performanceData.value[performanceData.value.length - 1]
})

onMounted(() => {
  loadPerformanceData()
})
</script>

<template>
  <div class="account-performance-page">
    <a-card title="账户绩效分析">
      <template #extra>
        <a-space>
          <a-select v-model:value="selectedPeriod" style="width: 120px">
            <a-select-option value="1w">近1周</a-select-option>
            <a-select-option value="1m">近1月</a-select-option>
            <a-select-option value="3m">近3月</a-select-option>
            <a-select-option value="1y">近1年</a-select-option>
            <a-select-option value="all">全部</a-select-option>
          </a-select>
          <a-range-picker v-model:value="dateRange" />
        </a-space>
      </template>

      <a-row :gutter="16" style="margin-bottom: 24px;">
        <a-col :span="4">
          <a-statistic
            title="总资产"
            :value="currentStats?.total_asset || 0"
            :precision="2"
            prefix="¥"
          />
        </a-col>
        <a-col :span="4">
          <a-statistic
            title="现金"
            :value="currentStats?.cash || 0"
            :precision="2"
            prefix="¥"
          />
        </a-col>
        <a-col :span="4">
          <a-statistic
            title="持仓市值"
            :value="currentStats?.market_value || 0"
            :precision="2"
            prefix="¥"
          />
        </a-col>
        <a-col :span="4">
          <a-statistic
            title="当日盈亏"
            :value="currentStats?.daily_pnl || 0"
            :precision="2"
            prefix="¥"
            :value-style="{ color: ((currentStats?.daily_pnl || 0) >= 0) ? '#f5222d' : '#52c41a' }"
          />
        </a-col>
        <a-col :span="4">
          <a-statistic
            title="当日收益率"
            :value="((currentStats?.daily_return || 0) * 100)"
            :precision="2"
            suffix="%"
            :value-style="{ color: ((currentStats?.daily_return || 0) >= 0) ? '#f5222d' : '#52c41a' }"
          />
        </a-col>
        <a-col :span="4">
          <a-statistic
            title="累计收益率"
            :value="((currentStats?.cumulative_return || 0) * 100)"
            :precision="2"
            suffix="%"
            :value-style="{ color: ((currentStats?.cumulative_return || 0) >= 0) ? '#f5222d' : '#52c41a' }"
          />
        </a-col>
      </a-row>

      <a-tabs>
        <a-tab-pane key="metrics" tab="绩效指标">
          <a-row :gutter="16">
            <a-col :span="8">
              <a-card size="small">
                <a-statistic
                  title="总收益率"
                  :value="performanceMetrics.totalReturn * 100"
                  :precision="2"
                  suffix="%"
                  :value-style="{ color: performanceMetrics.totalReturn >= 0 ? '#f5222d' : '#52c41a' }"
                />
              </a-card>
            </a-col>
            <a-col :span="8">
              <a-card size="small">
                <a-statistic
                  title="年化收益率"
                  :value="performanceMetrics.annualizedReturn * 100"
                  :precision="2"
                  suffix="%"
                  :value-style="{ color: performanceMetrics.annualizedReturn >= 0 ? '#f5222d' : '#52c41a' }"
                />
              </a-card>
            </a-col>
            <a-col :span="8">
              <a-card size="small">
                <a-statistic
                  title="夏普比率"
                  :value="performanceMetrics.sharpeRatio"
                  :precision="2"
                />
              </a-card>
            </a-col>
          </a-row>

          <a-row :gutter="16" style="margin-top: 16px;">
            <a-col :span="8">
              <a-card size="small">
                <a-statistic
                  title="最大回撤"
                  :value="performanceMetrics.maxDrawdown * 100"
                  :precision="2"
                  suffix="%"
                  :value-style="{ color: '#52c41a' }"
                />
              </a-card>
            </a-col>
            <a-col :span="8">
              <a-card size="small">
                <a-statistic
                  title="波动率"
                  :value="performanceMetrics.volatility * 100"
                  :precision="2"
                  suffix="%"
                />
              </a-card>
            </a-col>
            <a-col :span="8">
              <a-card size="small">
                <a-statistic
                  title="胜率"
                  :value="performanceMetrics.winRate * 100"
                  :precision="2"
                  suffix="%"
                />
              </a-card>
            </a-col>
          </a-row>
        </a-tab-pane>

        <a-tab-pane key="positions" tab="持仓分析">
          <a-table
            :columns="columns"
            :data-source="positions"
            :pagination="false"
            row-key="symbol"
            size="small"
          />
        </a-tab-pane>

        <a-tab-pane key="chart" tab="净值曲线">
          <div style="height: 400px; background: #f5f5f5; display: flex; align-items: center; justify-content: center;">
            <div style="color: #999;">净值曲线图表区域</div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<style scoped>
.account-performance-page {
  padding: 24px;
}
</style>