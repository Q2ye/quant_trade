<script setup lang="ts">
import { ref, reactive, onMounted, computed, h } from 'vue'
import { useRoute } from 'vue-router'
import {
  Card,
  Row,
  Col,
  Statistic,
  Tabs,
  Table,
  Tag,
  Space
} from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import {
  RiseOutlined,
  FallOutlined,
  SettingOutlined
} from '@ant-design/icons-vue'

const route = useRoute()
const strategyId = ref(route.params.id as string)

interface TradeRecord {
  id: string
  trade_time: string
  symbol: string
  direction: 'buy' | 'sell'
  price: number
  volume: number
  amount: number
  commission: number
  pnl: number
}

interface PerformanceMetric {
  period: string
  return: number
  benchmark_return: number
  alpha: number
  beta: number
  sharpe: number
  max_drawdown: number
}

const loading = ref(false)
const strategyInfo = ref<any>(null)
const tradeRecords = ref<TradeRecord[]>([])
const performanceMetrics = ref<PerformanceMetric[]>([])
const activeTab = ref('overview')

const columns: ColumnsType<TradeRecord> = [
  {
    title: '时间',
    dataIndex: 'trade_time',
    key: 'trade_time',
    width: 180
  },
  {
    title: '代码',
    dataIndex: 'symbol',
    key: 'symbol',
    width: 100
  },
  {
    title: '方向',
    dataIndex: 'direction',
    key: 'direction',
    width: 80,
    customRender: ({ text: direction }) => {
      return h(Tag, { color: direction === 'buy' ? 'red' : 'green' }, () => direction === 'buy' ? '买入' : '卖出')
    }
  },
  {
    title: '价格',
    dataIndex: 'price',
    key: 'price',
    width: 100,
    customRender: ({ text: price }) => `¥${price.toFixed(2)}`
  },
  {
    title: '数量',
    dataIndex: 'volume',
    key: 'volume',
    width: 100,
    customRender: ({ text: volume }) => volume.toLocaleString()
  },
  {
    title: '金额',
    dataIndex: 'amount',
    key: 'amount',
    width: 120,
    customRender: ({ text: amount }) => `¥${(amount / 10000).toFixed(2)}万`
  },
  {
    title: '盈亏',
    dataIndex: 'pnl',
    key: 'pnl',
    width: 100,
    customRender: ({ text: pnl }) => {
      const color = pnl >= 0 ? '#f5222d' : '#52c41a'
      return h('span', { style: { color } }, [
        pnl >= 0 ? '+' : '',
        '¥',
        pnl.toFixed(2)
      ])
    }
  }
]

const loadStrategyPerformance = async () => {
  loading.value = true
  try {
    const response = await fetch(`/api/performance/strategy/${strategyId.value}`)
    const data = await response.json()
    strategyInfo.value = data.info
    tradeRecords.value = data.trades
    performanceMetrics.value = data.metrics
  } catch (error) {
    console.error('加载策略绩效失败:', error)
  } finally {
    loading.value = false
  }
}

const currentMetrics = computed(() => {
  if (performanceMetrics.value.length === 0) return null
  return performanceMetrics.value[performanceMetrics.value.length - 1]
})

onMounted(() => {
  loadStrategyPerformance()
})
</script>

<template>
  <div class="strategy-performance-page">
    <a-card :loading="loading">
      <template #title>
        <div class="page-header">
          <h2 style="margin: 0;">
            {{ strategyInfo?.name || '策略绩效' }}
            <span style="font-size: 16px; color: #666; margin-left: 8px;">
              {{ strategyInfo?.id }}
            </span>
          </h2>
          <a-space>
            <a-tag v-if="strategyInfo?.status" :color="strategyInfo.status === 'running' ? 'green' : 'orange'">
              {{ strategyInfo.status === 'running' ? '运行中' : '已停止' }}
            </a-tag>
            <a-button type="link" :icon="h(SettingOutlined)">策略设置</a-button>
          </a-space>
        </div>
      </template>

      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="overview" tab="绩效概览">
          <div v-if="currentMetrics" class="performance-overview">
            <a-row :gutter="16">
              <a-col :span="6">
                <a-statistic
                  title="累计收益率"
                  :value="currentMetrics.return * 100"
                  :precision="2"
                  suffix="%"
                  :value-style="{ color: currentMetrics.return >= 0 ? '#f5222d' : '#52c41a' }"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="超额收益(Alpha)"
                  :value="currentMetrics.alpha * 100"
                  :precision="2"
                  suffix="%"
                  :value-style="{ color: currentMetrics.alpha >= 0 ? '#f5222d' : '#52c41a' }"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="夏普比率"
                  :value="currentMetrics.sharpe"
                  :precision="2"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="最大回撤"
                  :value="currentMetrics.max_drawdown * 100"
                  :precision="2"
                  suffix="%"
                  :value-style="{ color: '#52c41a' }"
                />
              </a-col>
            </a-row>

            <a-row :gutter="16" style="margin-top: 24px;">
              <a-col :span="6">
                <a-statistic
                  title="基准收益"
                  :value="currentMetrics.benchmark_return * 100"
                  :precision="2"
                  suffix="%"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="Beta系数"
                  :value="currentMetrics.beta"
                  :precision="2"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="交易次数"
                  :value="tradeRecords.length"
                />
              </a-col>
              <a-col :span="6">
                <a-statistic
                  title="胜率"
                  :value="(tradeRecords.filter(t => t.pnl > 0).length / tradeRecords.length * 100) || 0"
                  :precision="1"
                  suffix="%"
                />
              </a-col>
            </a-row>
          </div>
        </a-tab-pane>

        <a-tab-pane key="trades" tab="交易记录">
          <a-table
            :columns="columns"
            :data-source="tradeRecords"
            :pagination="{ pageSize: 20 }"
            row-key="id"
            size="small"
          />
        </a-tab-pane>

        <a-tab-pane key="analysis" tab="深度分析">
          <div style="height: 400px; background: #f5f5f5; display: flex; align-items: center; justify-content: center;">
            <div style="color: #999;">策略深度分析图表区域</div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<style scoped>
.strategy-performance-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.performance-overview {
  padding: 16px 0;
}
</style>