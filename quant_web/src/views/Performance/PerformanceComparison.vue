<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Card, Select, DatePicker, Table, Tabs } from 'ant-design-vue'
import { Line } from '@antv/g2plot'
import { onMounted as onDomMounted } from 'vue'

interface PerformanceMetric {
  name: string
  strategy1: number
  strategy2: number
  benchmark: number
}

const comparisonData = ref<PerformanceMetric[]>([])
const selectedStrategies = ref<string[]>([])
const dateRange = ref<string[]>([])

const metrics = [
  { name: '年化收益率', strategy1: 0.156, strategy2: 0.234, benchmark: 0.089 },
  { name: '夏普比率', strategy1: 1.23, strategy2: 1.89, benchmark: 0.76 },
  { name: '最大回撤', strategy1: -0.156, strategy2: -0.089, benchmark: -0.234 },
  { name: '波动率', strategy1: 0.189, strategy2: 0.156, benchmark: 0.201 },
  { name: '胜率', strategy1: 0.623, strategy2: 0.712, benchmark: 0.534 },
  { name: '盈亏比', strategy1: 1.45, strategy2: 1.89, benchmark: 1.23 }
]

const loadComparisonData = async () => {
  // 模拟API调用
  comparisonData.value = metrics
}

const renderChart = () => {
  const data = [
    { period: '2023-01', strategy1: 1.0, strategy2: 1.0, benchmark: 1.0 },
    { period: '2023-02', strategy1: 1.056, strategy2: 1.089, benchmark: 1.023 },
    { period: '2023-03', strategy1: 1.123, strategy2: 1.234, benchmark: 1.045 },
    // ... 更多数据
  ]

  const linePlot = new Line('performanceChart', {
    data,
    xField: 'period',
    yField: 'value',
    seriesField: 'category',
    yAxis: {
      label: {
        formatter: (v) => `${(Number(v) * 100 - 100).toFixed(1)}%`
      }
    },
    legend: {
      position: 'top'
    },
    smooth: true,
    animation: {
      appear: {
        animation: 'path-in',
        duration: 1000
      }
    }
  })

  linePlot.render()
}

onMounted(() => {
  loadComparisonData()
  onDomMounted(() => {
    renderChart()
  })
})
</script>

<template>
  <div class="performance-comparison-page">
    <a-card title="策略绩效对比">
      <template #extra>
        <a-space>
          <a-select
            v-model:value="selectedStrategies"
            mode="multiple"
            placeholder="选择对比策略"
            style="width: 300px"
          >
            <a-select-option value="strategy1">双均线策略</a-select-option>
            <a-select-option value="strategy2">动量反转策略</a-select-option>
            <a-select-option value="benchmark">沪深300</a-select-option>
          </a-select>

          <a-range-picker v-model:value="dateRange" />
        </a-space>
      </template>

      <a-tabs>
        <a-tab-pane key="chart" tab="净值曲线">
          <div id="performanceChart" style="height: 400px;"></div>
        </a-tab-pane>

        <a-tab-pane key="metrics" tab="绩效指标">
          <a-table
            :data-source="comparisonData"
            :pagination="false"
            row-key="name"
          >
            <a-table-column title="指标" data-index="name" key="name" />
            <a-table-column title="策略1" data-index="strategy1" key="strategy1">
              <template #default="{ text }">
                <span :class="{ positive: text > 0, negative: text < 0 }">
                  {{ (text * 100).toFixed(2) }}%
                </span>
              </template>
            </a-table-column>
            <a-table-column title="策略2" data-index="strategy2" key="strategy2">
              <template #default="{ text }">
                <span :class="{ positive: text > 0, negative: text < 0 }">
                  {{ (text * 100).toFixed(2) }}%
                </span>
              </template>
            </a-table-column>
            <a-table-column title="基准" data-index="benchmark" key="benchmark">
              <template #default="{ text }">
                <span :class="{ positive: text > 0, negative: text < 0 }">
                  {{ (text * 100).toFixed(2) }}%
                </span>
              </template>
            </a-table-column>
          </a-table>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<style scoped>
.performance-comparison-page {
  padding: 24px;
}

.positive {
  color: #f5222d;
}

.negative {
  color: #52c41a;
}
</style>