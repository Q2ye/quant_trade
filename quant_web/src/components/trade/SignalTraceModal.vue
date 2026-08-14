<!-- SignalTraceModal.vue — 信号链路追溯面板（候选→信号→订单→成交） -->
<template>
  <n-modal
    :show="show"
    preset="card"
    title="信号链路追溯"
    style="width: 640px; max-width: 92vw"
    :mask-closable="true"
    @update:show="$emit('update:show', $event)"
  >
    <!-- Loading -->
    <div v-if="loading" class="trace-loading">
      <n-spin size="large" />
      <span class="trace-loading-text">加载链路中...</span>
    </div>

    <!-- Error -->
    <n-result v-else-if="error" status="500" title="链路加载失败">
      <template #footer>
        <n-button size="small" @click="loadTrace">重试</n-button>
      </template>
    </n-result>

    <!-- Empty -->
    <n-empty v-else-if="!trace?.signal" description="无链路数据" />

    <!-- Data -->
    <template v-else>
      <!-- 链路标题 -->
      <div class="trace-header">
        <n-tag size="small" :bordered="false">{{ trace.signal.ts_code || '—' }}</n-tag>
        <span class="trace-sub">{{ trace.signal.signal_type || '—' }} · {{ (trace.signal.signal_time || '').slice(0, 10) }}</span>
      </div>

      <!-- 链路时间线 -->
      <div class="trace-timeline">
        <!-- 候选 -->
        <TraceNode
          :node="trace.parent"
          :fallback="trace.signal"
          label="候选"
          :active="activeNode === 'candidate'"
          @click="activeNode = 'candidate'"
        />
        <span class="trace-arrow">→</span>

        <!-- 买入信号 -->
        <TraceNode
          :node="trace.signal"
          label="信号"
          :active="activeNode === 'signal'"
          @click="activeNode = 'signal'"
        />
        <span class="trace-arrow">→</span>

        <!-- 订单 -->
        <TraceNode
          :node="trace.order ? { signal_status: trace.order.status, ts_code: trace.order.ts_code, signal_time: trace.order.submitted_at } : null"
          label="订单"
          :active="activeNode === 'order'"
          @click="activeNode = 'order'"
        />
        <span class="trace-arrow">→</span>

        <!-- 成交 -->
        <TraceNode
          :node="trace.trades?.length ? { signal_status: 'filled', ts_code: trace.trades[0].ts_code, signal_time: trace.trades[0].trade_time } : null"
          label="成交"
          :active="activeNode === 'trade'"
          @click="activeNode = 'trade'"
        />
      </div>

      <!-- 节点详情 -->
      <div class="trace-detail">
        <h4 class="detail-title">{{ detailTitle }}</h4>
        <div class="detail-grid">
          <div class="detail-item"><span class="dl">状态</span><span class="dv">{{ detailStatus }}</span></div>
          <div class="detail-item"><span class="dl">价格</span><span class="dv">{{ detailPrice }}</span></div>
          <div class="detail-item"><span class="dl">时间</span><span class="dv">{{ detailTime }}</span></div>
          <div class="detail-item"><span class="dl">数量</span><span class="dv">{{ detailQty }}</span></div>
        </div>
        <div v-if="detailReason" class="detail-reason">{{ detailReason }}</div>
      </div>

      <!-- 操作区 -->
      <div class="trace-actions">
        <n-button size="tiny" quaternary @click="copyId">复制信号ID</n-button>
        <n-button v-if="trace.order" size="tiny" quaternary @click="openOrder">查看订单</n-button>
      </div>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { NModal, NTag, NButton, NSpin, NResult, NEmpty, useMessage } from "naive-ui";
import tradeAPI from "@/api/trade";

const props = defineProps<{ show: boolean; signalId: string }>();
const emit = defineEmits(["update:show"]);
const message = useMessage();

const loading = ref(false);
const error = ref(false);
const trace = ref<any>(null);
const activeNode = ref<"candidate" | "signal" | "order" | "trade">("signal");

const loadTrace = async () => {
  loading.value = true;
  error.value = false;
  trace.value = null;
  // P1 修复：signalId 为空/缺失时清空并直接返回，避免复用上一次的陈旧链路
  if (!props.signalId) {
    loading.value = false;
    return;
  }
  try {
    trace.value = await tradeAPI.getSignalTrace(props.signalId);
    // 默认选中当前信号节点
    activeNode.value = "signal";
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

// 打开弹窗时加载；关闭时清空，防止下次打开显示上一次链路
watch(
  () => [props.show, props.signalId],
  ([show]) => {
    if (show) {
      loadTrace();
    } else {
      trace.value = null;
      error.value = false;
    }
  },
  { immediate: true }
);

// ---- 详情计算 ----
const detailTitle = computed(() => {
  const map: Record<string, string> = { candidate: "候选详情", signal: "信号详情", order: "订单详情", trade: "成交详情" };
  return map[activeNode.value] || "详情";
});

const currentDetail = computed(() => {
  switch (activeNode.value) {
    case "candidate": return trace.value?.parent || trace.value?.signal;
    case "signal": return trace.value?.signal;
    case "order": return trace.value?.order;
    // P2 修复：成交记录无 signal_status 字段，补注入 'filled'，使详情面板状态不再恒为 "—"
    case "trade": {
      const t = trace.value?.trades?.[0];
      return t ? { ...t, signal_status: "filled" } : null;
    }
    default: return trace.value?.signal;
  }
});

const detailStatus = computed(() => currentDetail.value?.signal_status || currentDetail.value?.status || "—");
const detailPrice = computed(() => {
  const p = currentDetail.value?.price;
  return p != null ? `¥${Number(p).toFixed(2)}` : "—";
});
const detailTime = computed(() => {
  const t = currentDetail.value?.signal_time || currentDetail.value?.submitted_at || currentDetail.value?.trade_time;
  return t ? String(t).slice(0, 16).replace("T", " ") : "—";
});
const detailQty = computed(() => {
  const q = currentDetail.value?.quantity || currentDetail.value?.volume;
  return q ? `${q}股` : "—";
});
const detailReason = computed(() => currentDetail.value?.reason || "");

const copyId = async () => {
  try {
    await navigator.clipboard.writeText(props.signalId);
    message.success("已复制信号ID");
  } catch {
    message.info(props.signalId);
  }
};

const openOrder = () => {
  const oid = trace.value?.order?.order_id;
  if (oid) {
    // TODO: 跳转订单详情（若无专门订单页，提示）
    message.info(`订单ID: ${oid}`);
  }
};
</script>

<!-- 链路节点子组件（NTag 由上方 script setup 提供，避免重复 import） -->
<script lang="ts">
import { defineComponent, h } from "vue";

const nodeStatusType = (status?: string) => {
  const s = (status || "").toLowerCase();
  if (["promoted", "confirmed", "filled", "completed", "executed"].includes(s)) return "success";
  if (["pending", "pending_confirm", "pending_manual", "submitted"].includes(s)) return "warning";
  if (["rejected", "cancelled", "expired", "error"].includes(s)) return "error";
  return "info";
};

const TraceNode = defineComponent({
  name: "TraceNode",
  props: {
    node: { type: Object as any, default: null },
    label: { type: String, default: "" },
    active: { type: Boolean, default: false },
  },
  emits: ["click"],
  setup(props, { emit }) {
    return () =>
      h(
        "div",
        {
          class: ["trace-node", props.active ? "trace-node-active" : ""],
          onClick: () => emit("click"),
        },
        [
          h("div", { class: "tn-label" }, props.label),
          props.node
            ? [
                h(NTag, { type: nodeStatusType(props.node.signal_status || props.node.status), size: "tiny", bordered: false }, { default: () => props.node.signal_status || props.node.status || "—" }),
                h("div", { class: "tn-code" }, props.node.ts_code || "—"),
                h("div", { class: "tn-time" }, String(props.node.signal_time || props.node.submitted_at || props.node.trade_time || "").slice(0, 10) || "—"),
              ]
            : h("div", { class: "tn-empty" }, "无"),
        ]
      );
  },
});
</script>

<style scoped>
.trace-loading {
  display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 40px 0;
}
.trace-loading-text { font-size: 12px; color: var(--n-text-color-3); }
.trace-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.trace-sub { font-size: 12px; color: var(--n-text-color-3); }
.trace-timeline { display: flex; align-items: stretch; justify-content: space-between; gap: 4px; margin-bottom: 16px; }
.trace-node {
  flex: 1; text-align: center; padding: 10px 6px; border-radius: 8px;
  background: var(--n-card-color);
  border: 1px solid var(--n-border-color); cursor: pointer; transition: all 0.15s;
  &:hover { border-color: var(--n-color-primary); }
}
.trace-node-active { border-color: var(--n-color-primary) !important; background: color-mix(in srgb, var(--n-color-primary) 10%, transparent); }
.tn-label { font-size: 11px; font-weight: 600; color: var(--n-text-color-1); margin-bottom: 6px; }
.tn-code { font-size: 11px; color: var(--n-text-color-2); margin-top: 4px; }
.tn-time { font-size: 10px; color: var(--n-text-color-3); margin-top: 2px; }
.tn-empty { font-size: 11px; color: var(--n-text-color-3); margin-top: 8px; }
.trace-arrow { align-self: center; color: var(--n-text-color-3); font-size: 14px; padding: 0 2px; }
.trace-detail { padding: 12px; border-radius: 8px; background: var(--n-color, rgba(12,18,32,0.4)); margin-bottom: 12px; }
.detail-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; }
.detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 12px; }
.detail-item { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.dl { color: var(--n-text-color-3); min-width: 32px; }
.dv { color: var(--n-text-color-1); }
.detail-reason { margin-top: 8px; font-size: 11px; color: var(--n-text-color-3); }
.trace-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
