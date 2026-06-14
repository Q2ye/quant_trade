<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { NTag, NButton, NSpin, NResult, useMessage } from "naive-ui";

const message = useMessage();

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
const error = ref(false);
const searchKeyword = ref("");
const filterEventType = ref("");
const detailEvent = ref<RiskEvent | null>(null);
const showDetail = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);

const eventTypeOptions = [
  { label: "持仓限制", value: "position_limit" },
  { label: "单日亏损", value: "daily_loss_limit" },
  { label: "黑名单", value: "blacklist" },
  { label: "波动率限制", value: "volatility_limit" },
];

const filteredEvents = computed(() => {
  let result = events.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (e) =>
        e.event_message.toLowerCase().includes(kw) ||
        e.rule_name.toLowerCase().includes(kw) ||
        (e.strategy_id || "").toLowerCase().includes(kw),
    );
  }
  if (filterEventType.value) {
    result = result.filter((e) => e.event_type === filterEventType.value);
  }
  return result;
});

const fetchRiskEvents = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
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
      {
        id: 3,
        rule_id: 3,
        rule_name: "黑名单拦截",
        strategy_id: "mean_rev_002",
        event_type: "blacklist",
        event_message: "尝试交易黑名单标的 ST退市",
        trigger_value: { ts_code: "600086.SH" },
        action_taken: "stop_strategy",
        created_at: "2024-01-14 10:15:00",
      },
    ];
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const viewEventDetail = (event: RiskEvent) => {
  detailEvent.value = event;
  showDetail.value = true;
};

const todayCount = computed(
  () =>
    events.value.filter((e) => {
      const today = new Date().toISOString().split("T")[0];
      return e.created_at.startsWith(today);
    }).length,
);

const columns = [
  { title: "发生时间", key: "created_at", width: 160 },
  { title: "触发规则", key: "rule_name", width: 150 },
  {
    title: "关联策略",
    key: "strategy_id",
    width: 130,
    render: (row: RiskEvent) => row.strategy_id || "系统级",
  },
  {
    title: "事件类型",
    key: "event_type",
    width: 120,
    render: (row: RiskEvent) =>
      h(
        NTag,
        {
          type: row.action_taken === "stop_strategy" ? "error" : "warning",
          size: "small",
        },
        {
          default: () => {
            const m: Record<string, string> = {
              position_limit: "持仓限制",
              daily_loss_limit: "单日亏损",
              blacklist: "黑名单",
              volatility_limit: "波动率限制",
            };
            return m[row.event_type] || row.event_type;
          },
        },
      ),
  },
  { title: "事件描述", key: "event_message", minWidth: 220 },
  {
    title: "执行动作",
    key: "action_taken",
    width: 100,
    render: (row: RiskEvent) =>
      h(
        NTag,
        {
          type: row.action_taken === "stop_strategy" ? "error" : "info",
          size: "small",
        },
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
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">风险事件记录</h1>
        </div>
        <div class="header-actions">
          <span class="stat-badge">今日事件: {{ todayCount }}</span>
          <span class="stat-badge">总事件数: {{ events.length }}</span>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="fetchRiskEvents">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-card class="main-card">
          <template #header>
            <div class="card-header">
              <span>风险事件列表</span>
              <div class="header-controls">
                <n-input
                  v-model:value="searchKeyword"
                  placeholder="搜索规则/策略/描述..."
                  size="small"
                  clearable
                  style="width: 200px"
                />
                <n-select
                  v-model:value="filterEventType"
                  placeholder="事件类型"
                  size="small"
                  clearable
                  style="width: 120px"
                  :options="eventTypeOptions"
                />
              </div>
            </div>
          </template>

          <n-spin :show="loading">
            <n-data-table
              :columns="columns"
              :data="filteredEvents"
              :bordered="false"
              size="small"
            >
              <template #empty>
                <n-empty description="暂无风险事件" />
              </template>
            </n-data-table>

            <div class="pagination-container">
              <n-pagination
                v-model:page="currentPage"
                v-model:page-size="pageSize"
                :item-count="filteredEvents.length"
                :page-sizes="[10, 20, 50]"
                show-size-picker
              />
            </div>
          </n-spin>
        </n-card>
      </template>
    </div>

    <n-modal
      v-model:show="showDetail"
      preset="card"
      title="事件详情"
      style="width: 560px"
    >
      <n-descriptions v-if="detailEvent" :column="2" bordered size="small">
        <n-descriptions-item label="发生时间">{{
          detailEvent.created_at
        }}</n-descriptions-item>
        <n-descriptions-item label="触发规则">{{
          detailEvent.rule_name
        }}</n-descriptions-item>
        <n-descriptions-item label="关联策略">{{
          detailEvent.strategy_id || "系统级"
        }}</n-descriptions-item>
        <n-descriptions-item label="事件类型">{{
          detailEvent.event_type
        }}</n-descriptions-item>
        <n-descriptions-item label="执行动作">
          <n-tag
            :type="
              detailEvent.action_taken === 'stop_strategy' ? 'error' : 'info'
            "
            size="small"
          >
            {{ detailEvent.action_taken === "alert" ? "报警" : "停止策略" }}
          </n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="触发值">{{
          JSON.stringify(detailEvent.trigger_value)
        }}</n-descriptions-item>
        <n-descriptions-item label="事件描述" :span="2">{{
          detailEvent.event_message
        }}</n-descriptions-item>
      </n-descriptions>
    </n-modal>
  </div>
</template>

<style scoped>
.risk-events {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.stat-badge {
  color: var(--n-text-color-2, rgba(255, 255, 255, 0.64));
  font-size: 13px;
  padding: 4px 12px;
  background: var(--color-bg-secondary, rgba(255, 255, 255, 0.04));
  border-radius: 4px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
