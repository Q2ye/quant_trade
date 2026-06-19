<!-- StrategyWorkspace.vue — 策略工作台：编辑器 + 参数 | 回测结果 -->
<template>
  <div class="strategy-workspace bg-gradient-mesh bg-noise">
    <!-- A. 页头 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <n-button text size="small" @click="router.push('/strategies')" style="margin-right:8px">
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
          <n-input
            v-model:value="strategyName"
            class="strategy-name-input"
            placeholder="输入策略名称"
            size="small"
            :style="{ maxWidth: '300px', fontWeight: 600, fontSize: '16px' }"
          />
          <n-tag :type="statusTagType" size="small" style="margin-left:8px">{{ strategyStatus }}</n-tag>
        </div>
        <div class="header-actions">
          <n-button size="small" :loading="saving" @click="saveStrategy">💾 保存</n-button>
          <n-button size="small" type="primary" :loading="isBacktesting" @click="openBacktestModal = true">
            ⚡ {{ isBacktesting ? `回测中 ${backtestProgress}%` : '回测' }}
          </n-button>
          <n-dropdown trigger="click" :options="moreOptions" @select="handleMoreAction">
            <n-button size="small">⋮</n-button>
          </n-dropdown>
        </div>
      </div>
    </div>

    <!-- B. 主内容 — 左右两栏 -->
    <div class="workspace-body">
      <!-- B1. 左栏：代码编辑器 + 策略参数 -->
      <div class="left-col">
        <n-card size="small" title="策略代码" :segmented="true">
          <template #header-extra>
            <n-tag :bordered="false" size="tiny" type="info">Python</n-tag>
          </template>
          <CodeEditorPanel
            :code="strategyCode"
            language="python"
            @update:code="(v: string) => strategyCode = v"
            @save="saveStrategy"
          />
        </n-card>

        <n-card size="small" title="策略参数" style="margin-top:12px">
          <n-empty v-if="Object.keys(strategyParams).length === 0" description="无参数" size="small" style="padding:12px 0" />
          <div v-else class="params-list">
            <div v-for="(val, key) in strategyParams" :key="key" class="param-row">
              <span class="param-label">{{ key }}</span>
              <n-input-number :value="val" size="small" style="width:100%"
                @update:value="(v: number | null) => { if (v !== null) strategyParams[key] = v; }" />
            </div>
          </div>
        </n-card>
      </div>

      <!-- B2. 右栏：回测结果 -->
      <div class="right-col">
        <!-- 回测中 -->
        <template v-if="isBacktesting">
          <n-card size="small" title="回测执行中">
            <n-spin size="medium" />
            <p style="text-align:center;margin:12px 0;color: var(--color-text-secondary)">{{ backtestProgress }}%</p>
            <n-progress type="line" :percentage="Number(backtestProgress)" :height="8" :border-radius="4" />
            <p style="text-align:center;font-size:12px;color:var(--color-text-tertiary);margin-top:8px">{{ backtestStatusText }}</p>
          </n-card>
        </template>

        <!-- 未回测 -->
        <template v-else-if="!currentTaskId">
          <n-card size="small">
            <n-empty description="尚未执行回测" style="padding:40px 0">
              <template #extra>
                <n-button size="small" type="primary" @click="openBacktestModal = true">开始回测</n-button>
              </template>
            </n-empty>
          </n-card>
        </template>

        <!-- 回测结果 -->
        <template v-else>
          <n-spin :show="btResultLoading" size="small">
            <n-card size="small" title="回测结果">
              <template #header-extra>
                <n-select
                  v-if="backtestHistory.length > 0"
                  v-model:value="selectedHistoryTaskId"
                  :options="backtestHistory.map(h => ({ label: h.label, value: h.taskId }))"
                  size="tiny" placeholder="历史回测" style="width:160px"
                  @update:value="(v: string) => loadBacktestResult(v as string)" />
              </template>

              <!-- 指标行 (6列) -->
              <div class="metrics-row">
                <div class="metric-item">
                  <span class="metric-label">年化收益</span>
                  <span class="metric-value" :class="btSummary.annualReturn >= 0 ? 'text-up' : 'text-down'">{{ (btSummary.annualReturn * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">基准收益</span>
                  <span class="metric-value" :class="benchmarkReturn >= 0 ? 'text-up' : 'text-down'">{{ (benchmarkReturn * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">夏普比率</span>
                  <span class="metric-value">{{ btSummary.sharpeRatio.toFixed(2) }}</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">最大回撤</span>
                  <span class="metric-value text-down">{{ (btSummary.maxDrawdown * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">胜率</span>
                  <span class="metric-value">{{ (btSummary.winRate * 100).toFixed(1) }}%</span>
                </div>
                <div class="metric-item">
                  <span class="metric-label">交易笔数</span>
                  <span class="metric-value">{{ btSummary.tradesCount }}</span>
                </div>
              </div>

              <!-- 三子图共享X轴 -->
              <BacktestSubplots
                :equity="btEquityPct"
                :benchmark="btBenchmarkPct"
                :dailyReturns="btDailyReturns"
                :dailyTurnover="btDailyTurnover"
                :drawdown="btDrawdown"
                :height="720"
              />
            </n-card>
          </n-spin>
        </template>
      </div>
    </div>

    <!-- C. 回测配置 Modal -->
    <n-modal v-model:show="openBacktestModal" preset="dialog" title="回测配置" positive-text="开始回测" negative-text="取消"
      @positive-click="handleBacktestSubmit" :loading="isBacktesting">
      <n-form label-width="90px" size="small">
        <n-form-item label="股票池"><n-dynamic-tags v-model:value="btConfig.symbols" /></n-form-item>
        <n-form-item label="开始日期"><n-date-picker v-model:value="btConfig.startDate" type="date" style="width:100%" /></n-form-item>
        <n-form-item label="结束日期"><n-date-picker v-model:value="btConfig.endDate" type="date" style="width:100%" /></n-form-item>
        <n-form-item label="初始资金"><n-input-number v-model:value="btConfig.initialCapital" :min="10000" :step="10000" style="width:100%" /></n-form-item>
        <n-form-item label="基准"><n-select v-model:value="btConfig.benchmark" :options="benchmarkSelectOptions" /></n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import {
  NButton, NTag, NInput, NInputNumber, NSpin, NProgress,
  NEmpty, NSelect, NModal, NForm, NFormItem, NDatePicker, NDynamicTags, NDropdown, NCard,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import CodeEditorPanel from "@/components/editors/CodeEditorPanel.vue";
import BacktestSubplots from "@/components/charts/BacktestSubplots.vue";
import TradeTable from "@/components/data/TradeTable.vue";
import { useStrategyWorkspace } from "@/composables/useStrategyWorkspace";
const router = useRouter();
const msg = useMessage();

const {
  loading, error, saving, strategyName, strategyCode, strategyParams, strategyStatus,
  isBacktesting, backtestProgress, backtestStatus, currentTaskId,
  backtestHistory, selectedHistoryTaskId,
  btSummary, btEquityCurve, btBenchmark, btDrawdown, btMonthlyReturns, btDailyReturns, btDailyTurnover, btTrades, btResultLoading,
  loadStrategy, saveStrategy, submitBacktest, loadBacktestResult, loadBacktestHistory, clearPolling,
} = useStrategyWorkspace();

const btActiveTab = ref("equity");

// 累计收益率百分比（百分比显示）
const btEquityPct = computed(() => {
  if (!btEquityCurve.value.length) return [];
  const base = btEquityCurve.value[0]?.value || 1;
  return btEquityCurve.value.map((p: any) => ({ date: p.date, value: (p.value / base - 1) * 100 }));
});
const btBenchmarkPct = computed(() => {
  if (!btBenchmark.value.length) return [];
  const base = btBenchmark.value[0]?.value || 1;
  return btBenchmark.value.map((p: any) => ({ date: p.date, value: (p.value / base - 1) * 100 }));
});
// 基准累计收益率（供指标行显示）
const benchmarkReturn = computed(() => {
  if (!btBenchmark.value.length) return 0;
  const base = btBenchmark.value[0]?.value || 1;
  const last = btBenchmark.value[btBenchmark.value.length - 1]?.value || base;
  return last / base - 1;
});

// 回测配置 Modal
const openBacktestModal = ref(false);
const btConfig = ref({
  symbols: [] as string[],
  startDate: Date.now() - 365 * 86400000,
  endDate: Date.now(),
  initialCapital: 1000000,
  benchmark: "000300.SH",
});

const benchmarkSelectOptions = [
  { label: "沪深300", value: "000300.SH" },
  { label: "上证指数", value: "000001.SH" },
  { label: "深证成指", value: "399001.SZ" },
  { label: "中证500", value: "000905.SH" },
  { label: "创业板指", value: "399006.SZ" },
];

const statusTagType = computed(() => {
  const map: Record<string, any> = { running: "success", deployed: "info", error: "error", stopped: "warning" };
  return map[strategyStatus.value] || "default";
});

const backtestStatusText = computed(() => {
  const map: Record<string, string> = {
    pending: "排队中...", running: "模拟交易中...",
    data_loading: "加载行情数据...", completed: "已完成",
    failed: "失败", cancelled: "已取消",
  };
  return map[backtestStatus.value] || backtestStatus.value || "等待中...";
});

const moreOptions = [
  { label: "导出策略JSON", key: "export" },
  { label: "查看版本历史", key: "versions" },
  { label: "风控设置", key: "risk" },
];

const handleMoreAction = (key: string) => {
  if (key === "export") {
    const data = JSON.stringify({ name: strategyName.value, code: strategyCode.value, parameters: strategyParams.value }, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${strategyName.value}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  } else if (key === "versions") {
    router.push(`/strategies/versions/${router.currentRoute.value.params.id}`);
  } else if (key === "risk") {
    router.push(`/strategies/risk/${router.currentRoute.value.params.id || ""}`);
  }
};

const handleBacktestSubmit = () => {
  const start = new Date(btConfig.value.startDate).toISOString().slice(0, 10);
  const end = new Date(btConfig.value.endDate).toISOString().slice(0, 10);
  submitBacktest({
    symbols: btConfig.value.symbols,
    startDate: start,
    endDate: end,
    initialCapital: btConfig.value.initialCapital,
    commissionRate: 0.0003,
    slippageRate: 0.001,
    benchmark: btConfig.value.benchmark,
  });
};

onMounted(() => { loadStrategy(); loadBacktestHistory(); });
onBeforeUnmount(() => { clearPolling(); });

</script>

<style lang="scss" scoped>
.strategy-workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

/* ---- 页头 ---- */
.page-header {
  flex-shrink: 0;
  .header-content {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 24px;
  }
  .title-section { display: flex; align-items: center; gap: 4px; }
  .header-actions { display: flex; gap: 6px; }
}

/* ---- 两栏布局 ---- */
.workspace-body {
  flex: 1; overflow: hidden;
  display: grid;
  grid-template-columns: 650px 1fr;
  gap: 12px;
  padding: 0 24px 24px;
  min-height: 0;
}

.left-col {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  :deep(.n-card:first-child) { flex: 1; display: flex; flex-direction: column; min-height: 580px;
    > .n-card__content { flex: 1; display: flex; flex-direction: column; }
  }
}

.right-col {
  overflow-y: auto;
  min-width: 0;
}

/* ---- 参数列表 ---- */
.params-list {
  .param-row { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px;
    .param-label { font-size: 11px; color: var(--color-text-tertiary); font-weight: 500; font-family: monospace; }
  }
}

/* ---- 指标行 ---- */
.metrics-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 12px; }
.metric-item {
  background: var(--color-bg-secondary, rgba(255,255,255,0.06));
  border-radius: 6px; padding: 8px 6px; text-align: center;
  .metric-label { font-size: 10px; color: var(--color-text-tertiary); display: block; margin-bottom: 2px; }
  .metric-value { font-size: 15px; font-weight: 700; color: var(--color-text-primary); }
}

/* ---- 图表工具栏 ---- */
/* ---- 卡片不透底 ---- */
:deep(.n-card) {
  background: var(--color-bg-solid, #0f1724) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
</style>
