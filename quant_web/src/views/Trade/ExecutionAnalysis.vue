<!-- views/Trade/ExecutionAnalysis.vue -->
<template>
  <div class="execution-analysis">
    <div class="page-header">
      <h1>交易执行分析</h1>
      <p>分析订单执行质量和交易成本</p>
    </div>

    <el-row :gutter="16" class="stats-row">
      <el-col :span="4" v-for="stat in executionStats" :key="stat.name">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-value" :class="stat.trend">
              {{ stat.value }}
            </div>
            <div class="stat-label">{{ stat.name }}</div>
            <div class="stat-trend">
              <Icon :icon="stat.trend === 'up' ? 'mdi:trending-up' : 'mdi:trending-down'" />
              {{ stat.change }}
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="charts-row">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>执行价格分析</span>
          </template>
          <div ref="priceChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>执行时间分布</span>
          </template>
          <div ref="timeChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>交易执行记录</span>
          <div>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
            <el-button type="primary" class="ml-2" @click="exportData">
              导出数据
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="executionRecords" stripe>
        <el-table-column prop="orderId" label="订单ID" width="120" />
        <el-table-column prop="symbol" label="标的" width="100" />
        <el-table-column prop="direction" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.direction === 'BUY' ? 'success' : 'danger'" size="small">
              {{ row.direction === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="targetPrice" label="目标价" width="100" />
        <el-table-column prop="executedPrice" label="执行价" width="100" />
        <el-table-column prop="slippage" label="滑点" width="100">
          <template #default="{ row }">
            <span :class="row.slippage >= 0 ? 'positive' : 'negative'">
              {{ row.slippage >= 0 ? '+' : '' }}{{ row.slippage.toFixed(4) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="executionTime" label="执行时间" width="180" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          :page-sizes="[10, 20, 50, 100]"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const dateRange = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(150)
const priceChart = ref<HTMLElement>()
const timeChart = ref<HTMLElement>()

const executionStats = ref([
  { name: '平均滑点', value: '-0.0023', change: '0.0012', trend: 'down' },
  { name: '执行成功率', value: '99.8%', change: '0.3%', trend: 'up' },
  { name: '平均执行时间', value: '1.2s', change: '-0.3s', trend: 'down' },
  { name: 'VWAP偏差', value: '-0.0015', change: '0.0008', trend: 'down' },
  { name: '交易成本', value: '0.12%', change: '-0.02%', trend: 'down' },
  { name: '大单执行率', value: '95.6%', change: '1.2%', trend: 'up' }
])

const executionRecords = ref([
  {
    orderId: 'ORD001234',
    symbol: '000001.SZ',
    direction: 'BUY',
    quantity: 1000,
    targetPrice: 15.20,
    executedPrice: 15.198,
    slippage: -0.002,
    executionTime: '2024-01-15 09:30:15',
    status: '已完成'
  },
  // 更多记录...
])

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    '已完成': 'success',
    '部分成交': 'warning',
    '已取消': 'info',
    '失败': 'danger'
  }
  return map[status] || 'info'
}

const exportData = () => {
  ElMessage.success('数据导出成功')
}

onMounted(() => {
  // 初始化价格分析图表
  if (priceChart.value) {
    const chart = echarts.init(priceChart.value)
    chart.setOption({
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: ['09:30', '10:00', '10:30', '11:00', '13:00', '14:00', '14:30']
      },
      yAxis: {
        type: 'value',
        name: '价格(元)'
      },
      series: [{
        name: '执行价格',
        type: 'line',
        data: [15.20, 15.18, 15.22, 15.25, 15.23, 15.28, 15.26],
        smooth: true
      }]
    })
  }

  // 初始化时间分布图表
  if (timeChart.value) {
    const chart = echarts.init(timeChart.value)
    chart.setOption({
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: ['<1s', '1-2s', '2-3s', '3-5s', '5-10s', '>10s']
      },
      yAxis: {
        type: 'value',
        name: '订单数量'
      },
      series: [{
        name: '执行时间分布',
        type: 'bar',
        data: [120, 85, 45, 30, 15, 5]
      }]
    })
  }
})
</script>

<style scoped>
.execution-analysis {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.stats-row {
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 8px;
}

.stat-content {
  text-align: center;
  padding: 16px 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}

.stat-value.up {
  color: #f56c6c;
}

.stat-value.down {
  color: #67c23a;
}

.stat-label {
  color: #909399;
  font-size: 14px;
  margin-bottom: 4px;
}

.stat-trend {
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.charts-row {
  margin-bottom: 24px;
}

.main-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.positive {
  color: #f56c6c;
}

.negative {
  color: #67c23a;
}

.ml-2 {
  margin-left: 8px;
}
</style>