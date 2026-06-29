<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import { NTag, NButton, NModal, NForm, NFormItem, NInput, NInputNumber, NSpace, NDataTable, NCard, NEmpty, useMessage } from "naive-ui";
import strategyAPI from "@/api/strategy";

const router = useRouter();
const message = useMessage();
const loading = ref(false);
const signals = ref<any[]>([]);
const showConfirm = ref(false);
const showCancel = ref(false);
const currentSignal = ref<any>(null);
const confirmForm = ref({ fill_price: 0, fill_quantity: 0, fill_time: "" });
const cancelReason = ref("");
const submitting = ref(false);

const signalStatusMap: Record<string, { type: string; label: string }> = {
  pending_manual: { type: "warning", label: "待确认" },
  confirmed: { type: "success", label: "已成交" },
  partial: { type: "info", label: "部分成交" },
  cancelled: { type: "default", label: "已取消" },
  rejected: { type: "error", label: "已拒绝" },
  expired: { type: "default", label: "已过期" },
};

const directionMap: Record<string, string> = {
  buy: "买入", long: "买入", sell: "卖出", short: "卖出",
};

const columns = [
  { title: "时间", key: "created_at", width: 150,
    render: (row: any) => (row.signal_time || row.created_at || "").toString().slice(0, 16).replace("T", " ") },
  { title: "股票", key: "ts_code", width: 110 },
  { title: "方向", key: "direction", width: 70,
    render: (row: any) => h(NTag, {
      type: (row.direction === "buy" || row.direction === "long") ? "error" : "info", size: "small",
    }, { default: () => directionMap[row.direction || row.signal_type] || row.direction || "—" }) },
  { title: "类型", key: "signal_type", width: 70,
    render: (row: any) => {
      const m: Record<string, string> = { entry: "入场", exit: "出场", stop_loss: "止损", take_profit: "止盈" };
      return m[row.signal_type] || row.signal_type || "—";
    }},
  { title: "参考价", key: "price", width: 85,
    render: (row: any) => row.price ? `¥${parseFloat(row.price).toFixed(2)}` : "—" },
  { title: "价格区间", key: "price_range", width: 140,
    render: (row: any) => {
      const lo = parseFloat(row.price_limit_low), hi = parseFloat(row.price_limit_high);
      return lo && hi ? `${lo} ~ ${hi}` : (row.price ? `${row.price} ±2%` : "—");
    }},
  { title: "数量", key: "quantity", width: 80 },
  { title: "置信度", key: "confidence", width: 70,
    render: (row: any) => {
      const c = parseFloat(row.confidence || row.strength);
      return !isNaN(c) ? `${(c * 100).toFixed(0)}%` : "—";
    }},
  { title: "原因", key: "reason", minWidth: 160, ellipsis: { tooltip: true } },
  { title: "状态", key: "signal_status", width: 80,
    render: (row: any) => {
      const s = signalStatusMap[row.signal_status] || { type: "default", label: row.signal_status || "—" };
      return h(NTag, { type: s.type, size: "small" }, { default: () => s.label });
    }},
  { title: "操作", key: "op", width: 190,
    render: (row: any) => {
      if (row.signal_status === "pending_manual") {
        return h(NSpace, { size: 4 }, { default: () => [
          h(NButton, { size: "tiny", type: "primary", onClick: () => openConfirm(row) }, { default: () => "确认成交" }),
          h(NButton, { size: "tiny", quaternary: true, onClick: () => openCancel(row) }, { default: () => "放弃" }),
        ]});
      }
      if (row.signal_status === "confirmed") {
        return h(NButton, { size: "tiny", type: "info", onClick: () => {
          router.push(`/trade/workspace?tab=orders&ts_code=${row.ts_code || ""}&direction=${row.direction || ""}&price=${row.price || row.fill_price || ""}&quantity=${row.quantity || row.fill_quantity || ""}`);
        }}, { default: () => "录入成交" });
      }
      return null;
    }},
  },
];

const fetchSignals = async () => {
  loading.value = true;
  try { signals.value = await strategyAPI.getPendingSignals(); }
  catch { message.error("加载失败"); }
  finally { loading.value = false; }
};

const openConfirm = (row: any) => {
  currentSignal.value = row;
  confirmForm.value = {
    fill_price: row.price || 0,
    fill_quantity: row.quantity || 0,
    fill_time: new Date().toISOString().slice(0, 16),
  };
  showConfirm.value = true;
};

const openCancel = (row: any) => {
  currentSignal.value = row;
  cancelReason.value = "";
  showCancel.value = true;
};

const handleConfirm = async () => {
  submitting.value = true;
  try {
    await strategyAPI.confirmSignal(currentSignal.value.id, confirmForm.value);
    message.success("已确认成交");
    showConfirm.value = false;
    await fetchSignals();
  } catch { message.error("确认失败"); }
  finally { submitting.value = false; }
};

const handleCancel = async () => {
  submitting.value = true;
  try {
    await strategyAPI.cancelSignal(currentSignal.value.id, cancelReason.value);
    message.success("已取消");
    showCancel.value = false;
    await fetchSignals();
  } catch { message.error("操作失败"); }
  finally { submitting.value = false; }
};

onMounted(() => fetchSignals());
</script>

<template>
  <div class="signal-confirm bg-gradient-mesh bg-noise">
    <div class="page-header" style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <h1 class="page-title">信号确认</h1>
        <p class="page-subtitle">待确认的交易信号列表，请在交易完成后标记结果</p>
      </div>
      <n-button size="small" @click="fetchSignals" :loading="loading" quaternary>刷新</n-button>
    </div>

    <n-card>
      <n-data-table :columns="columns" :data="signals" :loading="loading" size="small" :bordered="false">
        <template #empty><n-empty description="暂无待确认信号" /></template>
      </n-data-table>
    </n-card>

    <n-modal v-model:show="showConfirm" preset="card" title="确认成交" style="width: 380px" :mask-closable="false">
      <n-form :model="confirmForm" label-width="80px" size="small">
        <n-form-item label="成交价" required>
          <n-input-number v-model:value="confirmForm.fill_price" :min="0" style="width: 100%" />
        </n-form-item>
        <n-form-item label="成交数量" required>
          <n-input-number v-model:value="confirmForm.fill_quantity" :min="1" style="width: 100%" />
        </n-form-item>
        <n-form-item label="成交时间">
          <n-input v-model:value="confirmForm.fill_time" placeholder="2025-06-27 10:30" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showConfirm = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="handleConfirm">确认成交</n-button>
        </n-space>
      </template>
    </n-modal>

    <n-modal v-model:show="showCancel" preset="card" title="放弃信号" style="width: 380px">
      <n-form label-width="60px" size="small">
        <n-form-item label="原因">
          <n-input v-model:value="cancelReason" placeholder="如：高开超限价、资金不足等" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showCancel = false">返回</n-button>
          <n-button type="warning" :loading="submitting" @click="handleCancel">确认放弃</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.signal-confirm { padding: 0; min-height: 100%; }
.page-subtitle { margin: 4px 0 0; font-size: 13px; color: var(--n-text-color-3, rgba(255,255,255,0.48)); }
</style>
