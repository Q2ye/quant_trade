<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElTable, ElTag, ElButton } from 'element-plus'

interface Position {
  id: number
  ts_code: string
  name: string
  volume: number
  available_volume: number
  cost_price: number
  current_price: number
  market_value: number
  profit_loss: number
  profit_loss_ratio: number
  last_update: string
}

const positions = ref<Position[]>([])
const loading = ref(false)

// 计算总盈亏
const totalStats = computed(() => {
  const totalMarketValue = positions.value.reduce((sum, pos) => sum + pos.market_value, 0)
  const totalProfitLoss = positions.value.reduce((sum, pos) => sum + pos.profit_loss, 0)
  const totalCost = positions.value.reduce((sum, pos) => sum + (pos.cost_price * pos.volume), 0)

  return {
    totalMarketValue,
    totalProfitLoss,
    totalProfitLossRatio: totalCost > 0 ? (totalProfitLoss / totalCost) * 100 : 0
  }
})

// 获取持仓列表
const fetchPositions = async () => {
  loading.value = true
  try {
    // 模拟数据
    positions.value = [
      {
        id: 1,
        ts_code: '600519.SH',
        name: '贵州茅台',
        volume: 100,
        available_volume: 100,
        cost_price: 1750.00,
        current_price: 1850.50,
        market_value: 185050,
        profit_loss: 10050,
        profit_loss_ratio: 5.74,
        last_update: '2024-01-15 15:00:00'
      },
      {
        id: 2,
        ts_code: '000858.SZ',
        name: '五粮液',
        volume: 500,
        available_volume: 500,
        cost_price: 148.00,
        current_price: 152.30,
        market_value: 76150,
        profit_loss: 2150,
        profit_loss_ratio: 2.91,
        last_update: '2024-01-15 15:00:00'
      }
    ]
  } catch (error) {
    ElMessage.error('获取持仓列表失败')
  } finally {
    loading.value = false
  }
}

// 平仓操作
const closePosition = async (position: Position) => {
  try {
    ElMessage.info(`平仓操作: ${position.name} ${position.volume}股`)
    // 实际调用交易API
  } catch (error) {
    ElMessage.error('平仓操作失败')
  }
}

// 批量刷新持仓
const refreshPositions = async () => {
  await fetchPositions()
  ElMessage.success('持仓信息已刷新')
}

onMounted(() => {
  fetchPositions()
})
</script>

<template>
  <div class="position-management">
    <div class="management-header">
      <h3>持仓管理</h3>
      <div class="header-stats">
        <span>持仓市值: ¥{{ totalStats.totalMarketValue.toLocaleString() }}</span>
        <span :class="totalStats.totalProfitLoss >= 0 ? 'positive' : 'negative'">
          总盈亏: ¥{{ totalStats.totalProfitLoss.toLocaleString() }} ({{ totalStats.totalProfitLossRatio.toFixed(2) }}%)
        </span>
        <el-button @click="refreshPositions">刷新</el-button>
      </div>
    </div>

    <el-table :data="positions" v-loading="loading" style="width: 100%">
      <el-table-column prop="ts_code" label="股票代码" width="100" />

      <el-table-column prop="name" label="股票名称" width="120" />

      <el-table-column prop="volume" label="持仓数量" width="100">
        <template #default="{ row }">
          {{ row.volume.toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="available_volume" label="可用数量" width="100">
        <template #default="{ row }">
          {{ row.available_volume.toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="cost_price" label="成本价" width="100">
        <template #default="{ row }">
          ¥{{ row.cost_price.toFixed(2) }}
        </template>
      </el-table-column>

      <el-table-column prop="current_price" label="当前价" width="100">
        <template #default="{ row }">
          ¥{{ row.current_price.toFixed(2) }}
        </template>
      </el-table-column>

      <el-table-column prop="market_value" label="市值" width="120">
        <template #default="{ row }">
          ¥{{ row.market_value.toLocaleString() }}
        </template>
      </el-table-column>

      <el-table-column prop="profit_loss" label="浮动盈亏" width="120">
        <template #default="{ row }">
          <span :class="row.profit_loss >= 0 ? 'positive' : 'negative'">
            ¥{{ row.profit_loss.toLocaleString() }}
          </span>
        </template>
      </el-table-column>

      <el-table-column prop="profit_loss_ratio" label="盈亏比例" width="100">
        <template #default="{ row }">
          <span :class="row.profit_loss_ratio >= 0 ? 'positive' : 'negative'">
            {{ row.profit_loss_ratio.toFixed(2) }}%
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" @click="closePosition(row)">
            平仓
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.position-management {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.management-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.header-stats {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 14px;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>