<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { NTag, NButton } from "naive-ui";

interface RiskEvent {
  id: number;
  rule_id: number;
  rule_name: string;
  strategy_id?: string;
  event_type: string;
  event_message: string;
  trigger_value: any;
  action_taken: string;
  created_at: string;
}

const events = ref<RiskEvent[]>([]);
const loading = ref(false);

const fetchRiskEvents = async () => {
  loading.value = true;
  try {
    events.value = [
      {
        id: 1,
        rule_id: 1,
        rule_name: "单股仓位限制",
        strategy_id: "ma_cross_001",
        event_type: "position_limit",
        event_message: "贵州茅台持仓超过20%限制",
        trigger_value: { position_ratio: 0.25, symbol: "600519.SH" },
        action_taken: "alert",
        created_at: "2024-01-15 14:30:00",
      },
      {
        id: 2,
        rule_id: 2,
        rule_name: "单日亏损限制",
        event_type: "daily_loss_limit",
        event_message: "单日亏损达到5%限制",
        trigger_value: { daily_loss: -0.06 },
        action_taken: "stop_strategy",
        created_at: "2024-01-15 11:20:00",
      },
    ];
  } finally {
    loading.value = false;
  }
};

const viewEventDetail = (event: RiskEvent) => {
  console.log("事件详情:", event);
};

const columns = [
  { title: "发生时间", key: "created_at", width: 180 },
  { title: "触发规则", key: "rule_name", width: 150 },
  {
    title: "关联策略",
    key: "strategy_id",
    width: 120,
    render: (row: RiskEvent) => row.strategy_id || "系统级",
  },
  {
    title: "事件类型",
    key: "event_type",
    width: 120,
    render: (row: RiskEvent) =>
      h(
        NTag,
        { type: row.action_taken === "stop_strategy" ? "error" : "warning" },
        { default: () => row.event_type },
      ),
  },
  { title: "事件描述", key: "event_message", minWidth: 200 },
  {
    title: "执行动作",
    key: "action_taken",
    width: 120,
    render: (row: RiskEvent) =>
      h(
        NTag,
        { type: row.action_taken === "stop_strategy" ? "error" : "info" },
        { default: () => (row.action_taken === "alert" ? "报警" : "停止策略") },
      ),
  },
  {
    title: "操作",
    key: "op",
    width: 80,
    render: (row: RiskEvent) =>
      h(
        NButton,
        { size: "small", onClick: () => viewEventDetail(row) },
        { default: () => "详情" },
      ),
  },
];

onMounted(() => fetchRiskEvents());
</script>

<template>
  <div class="risk-events bg-gradient-mesh bg-noise">
    <div class="events-header">
      <h3>风险事件记录</h3>
      <div class="stats">
        <span
          >今日事件:
          {{
            events.filter((e) =>
              e.created_at.startsWith(new Date().toISOString().split("T")[0]),
            ).length
          }}</span
        >
        <span>总事件数: {{ events.length }}</span>
      </div>
    </div>

    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="events"
        :bordered="false"
        size="small"
      >
        <template #empty>
          <n-empty description="暂无风险事件" />
        </template>
      </n-data-table>
    </n-spin>
  </div>
</template>

<style scoped>
.risk-events {
  padding: 20px;
}

.events-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}

.events-header h3 {
  margin: 0;
  color: var(--n-text-color-1);
}

.stats {
  display: flex;
  gap: 20px;
  color: var(--n-text-color-2);
  font-size: 14px;
}
</style>
