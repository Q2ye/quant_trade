<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElTable, ElTag, ElDatePicker, ElSelect, ElOption } from 'element-plus'
import type { TradingSignal as Signal } from '@/types/entities/trading'

const signals = ref<Signal[]>([])
const loading = ref(false)
const filterParams = ref({
  startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
  endDate: new Date(),
  strategyId: '',
  signalType: '',
  symbol: ''
})

// 模拟历史信号数据
const mockSignals: Signal[] = [
  {
    id: '1',
    strategy_id: 'ma_cross_001',
    ts_code: '600519.SH',
    symbol: '600519',
    name: '贵州茅台',
    signal_type: 'buy',
    signal_time: '2024-01-15 14:30:00',
    current_price: 1850.50,
    strength: 0.85,
    reason: '双均线金叉买入信号',
    confidence: 0.92,
    status: 'executed'
  },
  {
    id: '2',
    strategy_id: 'rsi_strategy',
    ts_code: '000858.SZ',
    symbol: '000858',
    name: '五粮液',
    signal_type: 'sell',
    signal_time: '2024-01-15 10:15:00',
    current_price: 152.30,
    strength: 0.72,
    reason: 'RSI超卖区域卖出',
    confidence: 0.85,
    status: 'executed'
  }
]

// 获取历史信号
const fetchSignalHistory = async () => {
  loading.value = true
  try {
    // 实际项目中调用API
    // const response = await axios.get('/api/signals/history', { params: filterParams.value })
    // signals.value = response.data

    // 模拟数据
    signals.value = mockSignals.filter(signal => {
      const signalDate = new Date(signal.signal_time)
      return signalDate >= filterParams.value.startDate &&
             signalDate <= filterParams.value.endDate
    })
  } catch (error) {
    ElMessage.error('获取历史信号失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// 导出信号数据
const exportSignals = () => {
  const csvContent = signals.value.map((s: Signal) =>
    `${s.strategy_id},${s.ts_code},${s.signal_type},${s.signal_time},${s.current_price},${s.strength},"${s.reason}"`
  ).join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `signals_${new Date().toISOString().split('T')[0]}.csv`
  a.click()
  window.URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchSignalHistory()
})
</script>

<template>
  <div class="signal-history">
    <div class="history-header">
      <h3>历史信号分析</h3>
      <div class="filter-controls">
        <el-date-picker
          v-model="filterParams.startDate"
          type="date"
          placeholder="开始日期"
          style="width: 150px; margin-right: 10px;"
        />
        <el-date-picker
          v-model="filterParams.endDate"
          type="date"
          placeholder="结束日期"
          style="width: 150px; margin-right: 10px;"
        />
        <el-select v-model="filterParams.signalType" placeholder="信号类型" clearable style="width: 120px; margin-right: 10px;">
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
          <el-option label="持有" value="hold" />
        </el-select>
        <el-button type="primary" @click="fetchSignalHistory">查询</el-button>
        <el-button @click="exportSignals">导出CSV</el-button>
      </div>
    </div>

    <el-table
      :data="signals"
      v-loading="loading"
      style="width: 100%"
    >
      <el-table-column prop="signal_time" label="信号时间" width="180">
        <template #default="{ row }">
          {{ new Date(row.signal_time).toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="strategy_id" label="策略ID" width="150" />

      <el-table-column prop="ts_code" label="股票代码" width="120" />

      <el-table-column prop="signal_type" label="信号类型" width="100">
        <template #default="{ row }">
          <el-tag
            :type="row.signal_type === 'buy' ? 'success' : row.signal_type === 'sell' ? 'danger' : 'info'"
          >
            {{ row.signal_type === 'buy' ? '买入' : row.signal_type === 'sell' ? '卖出' : '持有' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="current_price" label="触发价格" width="120">
        <template #default="{ row }">
          ¥{{ row.current_price?.toFixed(2) }}
        </template>
      </el-table-column>

      <el-table-column prop="strength" label="信号强度" width="120">
        <template #default="{ row }">
          {{ Math.round((row.strength || 0) * 100) }}%
        </template>
      </el-table-column>

      <el-table-column prop="reason" label="信号原因" min-width="200" show-overflow-tooltip />

      <el-table-column label="后续表现" width="120">
        <template #default="{ row }">
          <span :class="getPerformanceClass(row)">+2.5%</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script lang="ts">
function getPerformanceClass(row: any) {
  // 模拟性能计算
  return 'positive'
}
</script>

<style scoped>
.signal-history {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.filter-controls {
  display: flex;
  align-items: center;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>