<!-- FactorDashboard.vue — 因子研究 v2：异步研究任务 + 真实 IC/分层/相关性数据 -->
<template>
  <div class="factor-dashboard bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">因子研究</h1>
          <p class="page-description">{{ statusText }}</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" size="small" @click="router.push('/strategies')" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- Toolbar: research controls -->
    <div class="toolbar-row">
      <div class="toolbar-controls">
        <n-select
          v-model:value="researchConfig.universe"
          :options="universeOptions"
          style="width:130px"
          size="small"
        />
        <n-date-picker
          v-model:formatted-value="researchConfig.dateRange"
          type="daterange"
          style="width:200px"
          size="small"
        />
        <n-select
          v-model:value="researchConfig.selectedFactors"
          multiple
          placeholder="选择因子（可多选）"
          :options="factorSelectOptions"
          style="min-width:280px;max-width:480px;flex:1"
          size="small"
        />
        <n-button type="primary" size="small" @click="startResearch" :loading="researchStatus === 'running'">
          {{ researchStatus === 'running' ? '研究中...' : '开始研究' }}
        </n-button>
      </div>
    </div>

    <!-- Progress bar -->
    <div v-if="researchStatus === 'running'" class="progress-bar-row">
      <n-progress
        type="line"
        :percentage="Math.round(researchProgress * 100)"
        :indicator-placement="'inside'"
        :height="24"
        :border-radius="4"
      />
      <span class="progress-hint">已计算 {{ calculatedCount }}/{{ totalStocks }} 只股票</span>
    </div>

    <div class="main-body">
      <!-- Loading -->
      <template v-if="pageLoading">
        <n-card :class="tokens.surface.card" style="flex:1"><n-skeleton text :repeat="8" /></n-card>
      </template>

      <!-- Error -->
      <n-result v-else-if="pageError" status="500" title="加载失败">
        <template #footer><n-button type="primary" @click="loadMetadata">重试</n-button></template>
      </n-result>

      <!-- Empty factor library -->
      <n-empty
        v-else-if="factorList.length === 0"
        description="暂无因子数据，请先同步因子定义"
        style="padding:60px 0;flex:1"
      >
        <template #extra>
          <n-button type="primary" @click="router.push('/data/sync')">前往数据同步</n-button>
        </template>
      </n-empty>

      <template v-else>
        <!-- Factor table (left) -->
        <div class="factor-table-pane">
          <n-card :class="tokens.surface.card" size="small" content-class="!p-0">
            <n-data-table
              :columns="factorColumns"
              :data="displayFactors"
              size="small"
              :row-key="(row: any) => row.name"
              :row-props="(row: any) => ({ style: 'cursor:pointer', onClick: () => selectedFactor = row })"
              :single-line="false"
              :loading="researchStatus === 'running'"
            />
          </n-card>
        </div>

        <!-- Factor detail (right) -->
        <div class="factor-detail-pane">
          <n-card :class="tokens.surface.card" size="small">
            <!-- No selection -->
            <n-empty v-if="!selectedFactor" description="点击左侧因子查看详情" style="padding:40px 0" />

            <!-- Research not run yet -->
            <n-empty
              v-else-if="!selectedFactor._hasResult"
              description="尚未分析，请选择因子后点击「开始研究」"
              style="padding:40px 0"
            />

            <!-- Detail with real data -->
            <template v-else>
              <h4>{{ selectedFactor.desc }} ({{ selectedFactor.name }})</h4>
              <n-tag
                :type="selectedFactor.icMean > 0 ? 'success' : 'error'"
                size="tiny"
                style="margin-bottom:12px"
              >
                IC 均值: {{ (selectedFactor.icMean * 100).toFixed(1) }}%
              </n-tag>

              <!-- IC series -->
              <h5>IC 序列分析</h5>
              <div v-if="selectedFactor._icSeries.length > 0" style="height:180px">
                <v-chart :option="buildICOption(selectedFactor)" autoresize style="height:100%" />
              </div>
              <n-empty v-else description="暂无IC序列数据" size="small" />

              <!-- Layer returns -->
              <h5>分层回测收益</h5>
              <div v-if="selectedFactor._layerReturns.length > 0" style="height:200px">
                <v-chart :option="buildLayerOption(selectedFactor)" autoresize style="height:100%" />
              </div>
              <n-empty v-else description="暂无分层回测数据" size="small" />

              <!-- Statistics -->
              <n-descriptions size="small" :column="2" style="margin-top:12px">
                <n-descriptions-item label="IC 均值">{{ (selectedFactor.icMean * 100).toFixed(2) }}%</n-descriptions-item>
                <n-descriptions-item label="IC_IR">{{ selectedFactor.icIr.toFixed(2) }}</n-descriptions-item>
                <n-descriptions-item label="Rank IC">{{ selectedFactor._rankIc ? (selectedFactor._rankIc * 100).toFixed(2) + '%' : '--' }}</n-descriptions-item>
                <n-descriptions-item label="胜率">{{ selectedFactor._winRate ? (selectedFactor._winRate * 100).toFixed(0) + '%' : '--' }}</n-descriptions-item>
                <n-descriptions-item label="Top-Bottom">{{ selectedFactor._topBottom ? (selectedFactor._topBottom * 100).toFixed(1) + '%' : '--' }}</n-descriptions-item>
                <n-descriptions-item label="分类">{{ selectedFactor.category }}</n-descriptions-item>
              </n-descriptions>

              <div style="margin-top:16px">
                <n-button size="small" type="primary" @click="generateStrategy">基于此因子生成策略</n-button>
              </div>
            </template>
          </n-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import VChart from "vue-echarts";
import {
  NCard, NDataTable, NTag, NEmpty, NDescriptions, NDescriptionsItem,
  NButton, NResult, NSkeleton, NSelect, NDatePicker, NProgress, useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import dataAPI from "@/api/data";

const router = useRouter();
const msg = useMessage();

// ---- Types ----
interface FactorItem {
  name: string; category: string; desc: string;
  icMean: number; icIr: number; layerReturn: number;
  _hasResult: boolean;
  _icSeries: Array<{ date: string; value: number }>;
  _layerReturns: Array<{ label: string; return_: number }>;
  _rankIc?: number; _winRate?: number; _topBottom?: number;
}

// ---- Page state ----
const pageLoading = ref(true);
const pageError = ref(false);
const factorList = ref<FactorItem[]>([]);
const selectedFactor = ref<FactorItem | null>(null);

// ---- Research state ----
type ResearchStatus = "idle" | "running" | "completed" | "failed";
const researchStatus = ref<ResearchStatus>("idle");
const researchProgress = ref(0);
const calculatedCount = ref(0);
const totalStocks = ref(0);
const researchId = ref<string | null>(null);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// ---- Research config ----
const researchConfig = reactive({
  universe: "000300.SH",
  selectedFactors: [] as string[],
  dateRange: null as [string, string] | null,
});

const universeOptions = [
  { label: "沪深300", value: "000300.SH" },
  { label: "中证500", value: "000905.SH" },
  { label: "全部A股", value: "all" },
];

const factorSelectOptions = computed(() =>
  factorList.value.map(f => ({ label: f.desc || f.name, value: f.name }))
);

// ---- Display factors (enriched with research results) ----
const displayFactors = computed(() => {
  return factorList.value.map(f => {
    // If research result exists for this factor, enrich it
    if (f._hasResult) return f;
    // Show as pending
    return { ...f, icMean: 0, icIr: 0, layerReturn: 0 };
  });
});

const statusText = computed(() => {
  if (pageLoading.value) return "加载中...";
  if (researchStatus.value === "running") return `研究中... ${calculatedCount.value}/${totalStocks.value}`;
  if (researchStatus.value === "completed") return `${factorList.value.length} 个因子可用`;
  return `${factorList.value.length} 个因子，选择因子后开始研究`;
});

// ---- Columns ----
const factorColumns = [
  { title: "因子名", key: "name", width: 120 },
  { title: "描述", key: "desc", width: 120, ellipsis: { tooltip: true } },
  { title: "分类", key: "category", width: 60 },
  {
    title: "IC均值", key: "icMean", width: 80,
    render: (row: FactorItem) => row._hasResult ? `${(row.icMean * 100).toFixed(2)}%` : "--",
  },
  {
    title: "IC_IR", key: "icIr", width: 70,
    render: (row: FactorItem) => row._hasResult ? row.icIr.toFixed(2) : "--",
  },
  {
    title: "分层收益", key: "layerReturn", width: 90,
    render: (row: FactorItem) => row._hasResult ? `${(row.layerReturn * 100).toFixed(1)}%` : "--",
  },
];

// ---- ECharts options ----
const buildICOption = (f: FactorItem) => ({
  backgroundColor: "transparent",
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(20,20,40,0.92)",
    borderColor: "rgba(255,255,255,0.08)",
    textStyle: { color: "#ccc", fontSize: 11 },
    formatter: (p: any) => `${p[0].axisValue}<br/>IC: ${p[0].value.toFixed(3)}`,
  },
  grid: { left: "3%", right: "4%", top: 12, bottom: 12, containLabel: true },
  xAxis: {
    type: "category",
    data: f._icSeries.map(d => d.date),
    axisLabel: { color: "#999", fontSize: 10 },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#999", fontSize: 10 },
    splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
  },
  series: [{
    type: "bar",
    data: f._icSeries.map(d => ({
      value: d.value,
      itemStyle: { color: d.value >= 0 ? "#18a058" : "#d03050", borderRadius: [3, 3, 0, 0] },
    })),
    barWidth: "60%",
    markLine: {
      silent: true,
      data: [{ type: "average" as const, name: "均值", lineStyle: { color: "#f0a020", type: "dashed" } }],
      label: { formatter: "{c}", fontSize: 10 },
    },
  }],
});

const buildLayerOption = (f: FactorItem) => ({
  backgroundColor: "transparent",
  tooltip: {
    trigger: "axis",
    backgroundColor: "rgba(20,20,40,0.92)",
    borderColor: "rgba(255,255,255,0.08)",
    textStyle: { color: "#ccc", fontSize: 11 },
    formatter: (p: any) => `${p[0].name}<br/>收益: ${p[0].value.toFixed(2)}%`,
  },
  grid: { left: "3%", right: "4%", top: 12, bottom: 12, containLabel: true },
  xAxis: {
    type: "category",
    data: f._layerReturns.map(d => d.label),
    axisLabel: { color: "#999", fontSize: 10 },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#999", fontSize: 10, formatter: "{value}%" },
    splitLine: { lineStyle: { color: "rgba(255,255,255,0.06)" } },
  },
  series: [{
    type: "bar",
    data: f._layerReturns.map(d => ({
      value: +(d.return_ * 100).toFixed(2),
      itemStyle: {
        color: d.return_ >= 0 ? "#18a058" : "#d03050",
        borderRadius: [4, 4, 0, 0],
      },
    })),
    barWidth: "50%",
    label: { show: true, position: "top", fontSize: 10, formatter: "{c}%" },
  }],
});

// ---- Actions ----
const loadMetadata = async () => {
  pageLoading.value = true;
  pageError.value = false;
  try {
    const metaRes = await dataAPI.getFactorMetadata({ page_size: 200 }).catch(() => null);
    if (metaRes?.metadata_list && metaRes.metadata_list.length > 0) {
      factorList.value = metaRes.metadata_list.map((m: any) => ({
        name: m.factor_name || m.factor_code,
        category: m.category || "其他",
        desc: m.display_name || m.description || m.factor_name || m.factor_code,
        icMean: 0, icIr: 0, layerReturn: 0,
        _hasResult: false,
        _icSeries: [],
        _layerReturns: [],
      }));
      // Auto-select first few factors
      if (researchConfig.selectedFactors.length === 0) {
        researchConfig.selectedFactors = factorList.value.slice(0, 5).map(f => f.name);
      }
    }
  } catch {
    pageError.value = true;
  } finally {
    pageLoading.value = false;
  }
};

const startResearch = async () => {
  if (researchConfig.selectedFactors.length === 0) {
    msg.warning("请至少选择一个因子");
    return;
  }
  researchStatus.value = "running";
  researchProgress.value = 0;
  calculatedCount.value = 0;

  try {
    const dr = researchConfig.dateRange;
    const today = new Date();
    const defaultStart = new Date(today.getFullYear() - 1, today.getMonth(), 1).toISOString().slice(0, 10);
    const defaultEnd = today.toISOString().slice(0, 10);
    const params: any = {
      factor_names: researchConfig.selectedFactors,
      universe: researchConfig.universe,
      start_date: dr && Array.isArray(dr) && dr.length === 2 ? dr[0] : defaultStart,
      end_date: dr && Array.isArray(dr) && dr.length === 2 ? dr[1] : defaultEnd,
    };

    const res = await dataAPI.submitFactorResearch(params).catch(() => null);
    if (!res?.research_id) {
      msg.error("提交研究任务失败");
      researchStatus.value = "failed";
      return;
    }
    researchId.value = res.research_id;
    startPolling();
  } catch (err) {
    msg.error("提交研究任务失败");
    researchStatus.value = "failed";
  }
};

const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const status = await dataAPI.getResearchStatus({ research_id: researchId.value! });
      if (!status) return;

      researchProgress.value = status.progress || 0;
      calculatedCount.value = status.calculated_count || 0;
      totalStocks.value = status.total_stocks || 0;

      if (status.status === "completed") {
        clearInterval(pollTimer!);
        pollTimer = null;
        researchStatus.value = "completed";
        applyResearchResults(status.result || status);
      } else if (status.status === "failed") {
        clearInterval(pollTimer!);
        pollTimer = null;
        researchStatus.value = "failed";
        msg.error(status.error_message || "研究任务失败");
      }
    } catch {
      // polling error, continue
    }
  }, 2000);
};

/** Apply research results to factor list */
const applyResearchResults = (result: any) => {
  if (!result) return;

  // Try different result structures from backend
  const icData = result.ic_analysis || result.icAnalysis || [];
  const quantileData = result.quantile_analysis || result.quantileAnalysis || [];
  const stabilityData = result.stability_analysis || result.stabilityAnalysis || result.summary || {};

  // Build a lookup: factor_name -> analysis result
  const icByFactor: Record<string, any> = {};
  if (Array.isArray(icData)) {
    icData.forEach((r: any) => {
      const name = r.factor_name || r.factor || "";
      icByFactor[name] = r;
    });
  }

  const quantileByFactor: Record<string, any> = {};
  if (Array.isArray(quantileData)) {
    quantileData.forEach((r: any) => {
      const name = r.factor_name || r.factor || "";
      quantileByFactor[name] = r;
    });
  }

  // Also check summary-level data
  const summaryIcMean: Record<string, number> = result.ic_mean || result.icMean || {};
  const summaryIcIr: Record<string, number> = result.ic_ir || result.icIr || {};
  const summaryTopBottom: Record<string, number> = result.top_minus_bottom || result.topBottom || {};

  // Enrich factor list
  factorList.value = factorList.value.map(f => {
    const ic = icByFactor[f.name] || {};
    const q = quantileByFactor[f.name] || {};

    // Extract IC data
    const icMean = ic.ic_mean ?? ic.icMean ?? summaryIcMean[f.name] ?? 0;
    const icIr = ic.ic_ir ?? ic.icIr ?? summaryIcIr[f.name] ?? 0;
    const icSeriesRaw = ic.ic_series || ic.icSeries || [];
    const icSeries = Array.isArray(icSeriesRaw)
      ? icSeriesRaw.map((d: any) => ({
          date: d.date || d.period || "",
          value: d.value ?? d.ic_value ?? 0,
        }))
      : [];

    // Extract quantile data
    const layerReturnsRaw = q.quantile_returns || q.quantileReturns || q.layers || q.layer_returns || [];
    let layerReturns: Array<{ label: string; return_: number }> = [];
    if (Array.isArray(layerReturnsRaw) && layerReturnsRaw.length > 0) {
      layerReturns = layerReturnsRaw.map((l: any, i: number) => ({
        label: l.label || l.group || l.quantile || `Q${i + 1}`,
        return_: l.return_ ?? l.return ?? l.value ?? 0,
      }));
    }

    const topBottom = q.top_minus_bottom ?? q.topMinusBottom ?? summaryTopBottom[f.name];
    const winRate = ic.win_rate ?? ic.winRate ?? ic.positive_ratio ?? ic.positiveRatio;
    const rankIc = ic.rank_ic ?? ic.rankIc;

    return {
      ...f,
      icMean: icMean || 0,
      icIr: icIr || 0,
      layerReturn: topBottom || 0,
      _hasResult: icMean !== 0 || icSeries.length > 0 || layerReturns.length > 0,
      _icSeries: icSeries,
      _layerReturns: layerReturns,
      _rankIc: rankIc,
      _winRate: winRate,
      _topBottom: topBottom,
    };
  });

  // Auto-select first enriched factor
  const enriched = factorList.value.find(f => f._hasResult);
  if (enriched) selectedFactor.value = enriched;
};

const generateStrategy = () => {
  if (!selectedFactor.value) return;
  const f = selectedFactor.value;
  msg.info(`跳转策略工作台，基于因子 ${f.name} 生成策略`);
  router.push(`/strategies/workspace/new?template=factor&factor=${f.name}&ic=${f.icMean.toFixed(3)}&ic_ir=${f.icIr.toFixed(2)}`);
};

onMounted(() => loadMetadata());

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<style lang="scss" scoped>
.factor-dashboard { height: 100%; overflow-y: hidden; display: flex; flex-direction: column; }
.main-body { display: flex; gap: 12px; padding: 10px 24px 24px; flex: 1; overflow: hidden; }
.factor-table-pane { width: 55%; overflow-y: auto; }
.factor-detail-pane { width: 45%; overflow-y: auto;
  h4 { margin: 0 0 6px; font-size: 15px; color: var(--color-text-primary); }
  h5 { margin: 14px 0 6px; font-size: 13px; color: var(--color-text-secondary); }
}

.toolbar-row {
  padding: 10px 32px 8px;
  .toolbar-controls {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  }
}

.progress-bar-row {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 32px; background: rgba(124,58,237,0.06);
  .progress-hint { font-size: 12px; color: var(--color-text-tertiary); white-space: nowrap; }
}
</style>
