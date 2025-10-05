<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElTable, ElTag, ElButton } from 'element-plus'

interface RiskEvent {
  id: number
  rule_id: number
  rule_name: string
  strategy_id?: string
  event_type: string
  event_message: string
  trigger_value: any
  action_taken: string
  created_at: string
}

const events = ref<RiskEvent[]>([])
const loading = ref(false)

// 获取风险事件
const fetchRiskEvents = async () => {
  loading.value = true
  try {
    // 模拟数据
    events.value = [
      {
        id: 1,
        rule_id: 1,
        rule_name: '单股仓位限制',
        strategy_id: 'ma_cross_001',
        event_type: 'position_limit',
        event_message: '贵州茅台持仓超过20%限制',
        trigger_value: { position_ratio: 0.25, symbol: '600519.SH' },
        action_taken: 'alert',
        created_at: '2024-01-15 14:30:00'
      },
      {
        id: 2,
        rule_id: 2,
        rule_name: '单日亏损限制',
        event_type: 'daily_loss_limit',
        event_message: '单日亏损达到5%限制',
        trigger_value: { daily_loss: -0.06 },
        action_taken: 'stop_strategy',
        created_at: '2024-01-15 11:20:00'
      }
    ]
  } catch (error) {
    console.error('获取风险事件失败:', error)
  } finally {
    loading.value = false
  }
}

// 查看事件详情
const viewEventDetail = (event: RiskEvent) => {
  console.log('事件详情:', event)
}

onMounted(() => {
  fetchRiskEvents()
})
</script>

<template>
  <div class="risk-events">
    <div class="events-header">
      <h3>风险事件记录</h3>
      <div class="stats">
        <span>今日事件: {{ events.filter(e => e.created_at.startsWith(new Date().toISOString().split('T')[0])).length }}</span>
        <span>总事件数: {{ events.length }}</span>
      </div>
    </div>

    <el-table :data="events" v-loading="loading" style="width: 100%">
      <el-table-column prop="created_at" label="发生时间" width="180" />

      <el-table-column prop="rule_name" label="触发规则" width="150" />

      <el-table-column prop="strategy_id" label="关联策略" width="120">
        <template #default="{ row }">
          {{ row.strategy_id || '系统级' }}
        </template>
      </el-table-column>

      <el-table-column prop="event_type" label="事件类型" width="120">
        <template #default="{ row }">
          <el-tag :type="row.action_taken === 'stop_strategy' ? 'danger' : 'warning'">
            {{ row.event_type }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="event_message" label="事件描述" min-width="200" />

      <el-table-column prop="action_taken" label="执行动作" width="120">
        <template #default="{ row }">
          <el-tag :type="row.action_taken === 'stop_strategy' ? 'danger' : 'info'">
            {{ row.action_taken === 'alert' ? '报警' : '停止策略' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="viewEventDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.risk-events {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
}

.events-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.stats {
  display: flex;
  gap: 20px;
  color: #606266;
  font-size: 14px;
}
</style>