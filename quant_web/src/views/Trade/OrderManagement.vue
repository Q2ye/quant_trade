<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElTable, ElTag, ElButton, ElSelect, ElOption } from 'element-plus'

interface Order {
  order_id: string
  strategy_id?: string
  ts_code: string
  order_type: string
  direction: string
  price: number
  volume: number
  status: string
  submitted_at: string
  filled_volume?: number
  filled_amount?: number
}

// 订单状态映射
const statusMap: Record<string, { text: string; type: import('element-plus').TagProps['type'] }> = {
  submitted: { text: '已报', type: 'primary' },
  partial_filled: { text: '部成', type: 'warning' },
  filled: { text: '已成', type: 'success' },
  cancelled: { text: '已撤', type: 'info' },
  rejected: { text: '废单', type: 'danger' }
}

const orders = ref<Order[]>([])
const filterStatus = ref('all')
const loading = ref(false)

// 获取订单列表
const fetchOrders = async () => {
  loading.value = true
  try {
    // 模拟数据
    orders.value = [
      {
        order_id: 'O20240115001',
        strategy_id: 'ma_cross_001',
        ts_code: '600519.SH',
        order_type: 'limit',
        direction: 'buy',
        price: 1850.00,
        volume: 100,
        status: 'submitted',
        submitted_at: '2024-01-15 14:30:00'
      },
      {
        order_id: 'O20240115002',
        ts_code: '000858.SZ',
        order_type: 'market',
        direction: 'sell',
        price: 0,
        volume: 200,
        status: 'filled',
        submitted_at: '2024-01-15 10:15:00',
        filled_volume: 200,
        filled_amount: 31000
      }
    ]
  } catch (error) {
    ElMessage.error('获取订单列表失败')
  } finally {
    loading.value = false
  }
}

// 撤单操作
const cancelOrder = async (order: Order) => {
  try {
    order.status = 'cancelled'
    ElMessage.success('撤单请求已发送')
  } catch (error) {
    ElMessage.error('撤单失败')
  }
}

// 批量撤单
const batchCancel = async () => {
  const pendingOrders = orders.value.filter(o => o.status === 'submitted')
  if (pendingOrders.length === 0) {
    ElMessage.warning('没有可撤单的订单')
    return
  }

  try {
    pendingOrders.forEach(order => {
      order.status = 'cancelled'
    })
    ElMessage.success(`已撤销 ${pendingOrders.length} 个订单`)
  } catch (error) {
    ElMessage.error('批量撤单失败')
  }
}

// 过滤订单
const filteredOrders = computed(() => {
  if (filterStatus.value === 'all') {
    return orders.value
  }
  return orders.value.filter(order => order.status === filterStatus.value)
})

onMounted(() => {
  fetchOrders()
})
</script>

<template>
  <div class="order-management">
    <div class="management-header">
      <h3>订单管理</h3>
      <div class="header-actions">
        <el-select v-model="filterStatus" style="width: 120px; margin-right: 10px;">
          <el-option label="全部状态" value="all" />
          <el-option label="已报" value="submitted" />
          <el-option label="部成" value="partial_filled" />
          <el-option label="已成" value="filled" />
          <el-option label="已撤" value="cancelled" />
        </el-select>
        <el-button @click="batchCancel" type="warning">批量撤单</el-button>
        <el-button @click="fetchOrders">刷新</el-button>
      </div>
    </div>

    <el-table :data="filteredOrders" v-loading="loading" style="width: 100%">
      <el-table-column prop="order_id" label="订单ID" width="140" />

      <el-table-column prop="strategy_id" label="策略ID" width="120">
        <template #default="{ row }">
          {{ row.strategy_id || '手动' }}
        </template>
      </el-table-column>

      <el-table-column prop="ts_code" label="标的代码" width="100" />

      <el-table-column prop="direction" label="方向" width="80">
        <template #default="{ row }">
          <el-tag :type="row.direction === 'buy' ? 'success' : 'danger'" size="small">
            {{ row.direction === 'buy' ? '买入' : '卖出' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="order_type" label="类型" width="80">
        <template #default="{ row }">
          {{ row.order_type === 'limit' ? '限价' : '市价' }}
        </template>
      </el-table-column>

      <el-table-column prop="price" label="价格" width="100">
        <template #default="{ row }">
          {{ row.price > 0 ? `¥${row.price.toFixed(2)}` : '市价' }}
        </template>
      </el-table-column>

      <el-table-column prop="volume" label="数量" width="100" />

      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type" effect="dark">
            {{ statusMap[row.status]?.text }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="submitted_at" label="提交时间" width="180" />

      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'submitted' || row.status === 'partial_filled'"
            size="small"
            type="danger"
            @click="cancelOrder(row)"
          >
            撤单
          </el-button>
          <span v-else style="color: #909399;">--</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.order-management {
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

.header-actions {
  display: flex;
  align-items: center;
}
</style>