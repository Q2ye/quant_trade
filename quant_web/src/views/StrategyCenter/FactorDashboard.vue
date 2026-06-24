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
          <n-button class="action-btn" size="small" @click="loadMetadata" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
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
          multiple
          filterable
          tag
          :max-tag-count="2"
          placeholder="指数或代码（可多选手输）"
          style="min-width:180px;max-width:300px;flex:1"
          size="small"
        />
        <n-select
          v-model:value="researchConfig.basketIds"
          :options="basketOptions"
          multiple
          clearable
          :max-tag-count="2"
          placeholder="选择篮子"
          style="min-width:140px;max-width:220px;flex:0.6"
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
          filterable
          clearable
          placeholder="选择因子（可搜可多选）"
          :options="factorSelectOptions"
          :max-tag-count="3"
          consistent-menu-width
          style="min-width:300px;max-width:520px;flex:1"
          size="small"
        />
        <n-button size="small" quaternary @click="selectAllFactors">
          全选
        </n-button>
        <n-button
          v-if="researchConfig.selectedFactors.length > 0"
          size="small" quaternary @click="researchConfig.selectedFactors = []"
        >
          清空
        </n-button>
        <n-button type="primary" size="small" @click="startResearch" :loading="researchStatus === 'running'">
          {{ researchStatus === 'running' ? '研究中...' : '开始研究' }}
        </n-button>
        <n-button size="small" @click="showFactorDialog = true" quaternary type="primary">
          <template #icon><SmartIcon name="Plus" /></template>
          新建因子
        </n-button>
        <n-button size="small" @click="router.push('/factors/history')" quaternary>
          <template #icon><SmartIcon name="Clock" /></template>
          研究历史
        </n-button>
      </div>
    </div>

    <!-- Progress bar -->
    <div v-if="researchStatus === 'running'" class="progress-bar-row">
      <n-progress
        type="line"
        :percentage="Math.round(researchProgress)"
        :indicator-placement="'inside'"
        :height="24"
        :border-radius="4"
        style="flex:1"
      />
      <span class="progress-hint">已计算 {{ calculatedCount }}/{{ totalStocks }} 只股票</span>
      <n-button size="small" type="warning" quaternary @click="cancelResearch" :loading="cancelling">
        取消
      </n-button>
    </div>

    <!-- Error banner -->
    <n-alert
      v-if="researchStatus === 'failed' && lastError"
      type="error"
      closable
      style="margin-bottom:12px"
      @close="researchStatus = 'idle'; lastError = ''"
    >
      <template #header>研究失败</template>
      {{ lastError }}
    </n-alert>

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
              <div v-if="selectedFactor._icSeries.length > 0" style="height:144px; width:80%; transform:scale(1.25); transform-origin:top left; margin-bottom:40px">
                <v-chart :option="buildICOption(selectedFactor)" autoresize style="height:100%; width:100%" />
              </div>
              <n-empty v-else description="暂无IC序列数据" size="small" />

              <!-- Layer returns -->
              <h5>分层回测收益</h5>
              <div v-if="selectedFactor._layerReturns.length > 0" style="height:160px; width:80%; transform:scale(1.25); transform-origin:top left; margin-bottom:44px">
                <v-chart :option="buildLayerOption(selectedFactor)" autoresize style="height:100%; width:100%" />
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

  <!-- 新建因子弹窗 -->
  <FactorEditDialog v-model="showFactorDialog" @save="onFactorCreated" />
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import VChart from "vue-echarts";
import FactorEditDialog from "@/components/strategy/FactorEditDialog.vue";
import {
  NCard, NDataTable, NTag, NEmpty, NDescriptions, NDescriptionsItem,
  NButton, NResult, NSkeleton, NSelect, NDatePicker, NProgress, NAlert, useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import dataAPI from "@/api/data";
import marketAPI from "@/api/market";
import { getBaskets } from "@/api/basket";

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
type ResearchStatus = "idle" | "running" | "completed" | "failed" | "cancelled";
const researchStatus = ref<ResearchStatus>("idle");
const lastError = ref("");
const researchProgress = ref(0);
const calculatedCount = ref(0);
const totalStocks = ref(0);
const researchId = ref<string | null>(null);
// 多因子提交时，后端为每个因子创建一个独立 research 任务
const allResearchIds = ref<string[]>([]);
const completedResearchIds = ref<Set<string>>(new Set());
const cancelling = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// ---- Research config ----
const researchConfig = reactive({
  universe: ["000300.SH"] as string[],
  selectedFactors: [] as string[],
  dateRange: null as [string, string] | null,
  basketIds: [] as string[],
});
const showFactorDialog = ref(false);
const onFactorCreated = () => { loadMetadata(); };

const universeLoading = ref(false);
const universeOptions = ref<Array<{ label: string; value: string }>>([
  { label: "全部A股", value: "all" },
  { label: "沪深300", value: "000300.SH" },
  { label: "中证500", value: "000905.SH" },
]);

const basketOptions = ref<Array<{ label: string; value: string }>>([]);

async function loadBasketOptions() {
  try {
    const result = await getBaskets().catch(() => ({ baskets: [] as any[] }));
    const list = result?.baskets || [];
    basketOptions.value = list.map((b: any) => ({ label: b.name || b.id, value: b.id }));
  } catch { /* keep empty */ }
}

async function loadUniverseOptions() {
  universeLoading.value = true;
  try {
    const indexes = await marketAPI.getIndexes().catch(() => [] as any[]);
    if (Array.isArray(indexes) && indexes.length > 0) {
      const extra = indexes
        .filter((idx: any) => idx.ts_code && idx.name)
        .map((idx: any) => ({ label: `${idx.name} (${idx.ts_code})`, value: idx.ts_code }));
      universeOptions.value = [
        { label: "全部A股", value: "all" },
        ...extra,
      ];
    }
  } catch { /* keep defaults */ }
  universeLoading.value = false;
}

const factorSelectOptions = computed(() => {
  const grouped: Record<string, any[]> = {};
  for (const f of factorList.value) {
    const cat = f.category || "其他";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push({ label: `${f.desc} (${f.name})`, value: f.name });
  }
  const result: any[] = [];
  for (const [cat, items] of Object.entries(grouped)) {
    result.push({ type: "group", label: cat, key: cat, children: items });
  }
  return result;
});

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
    render: (row: FactorItem) => (row as any)._isEmpty ? "无数据" : (row._hasResult ? `${(row.icMean * 100).toFixed(2)}%` : "--"),
  },
  {
    title: "IC_IR", key: "icIr", width: 70,
    render: (row: FactorItem) => (row as any)._isEmpty ? "无数据" : (row._hasResult ? row.icIr.toFixed(2) : "--"),
  },
  {
    title: "分层收益", key: "layerReturn", width: 90,
    render: (row: FactorItem) => (row as any)._isEmpty ? "无数据" : (row._hasResult ? `${(row.layerReturn * 100).toFixed(1)}%` : "--"),
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
      itemStyle: { color: d.value >= 0 ? "#d03050" : "#18a058", borderRadius: [3, 3, 0, 0] },
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
        color: d.return_ >= 0 ? "#d03050" : "#18a058",
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
        name: m.factor_code,                           // 因子代码（传值/API用，如 VOL_1M）
        category: m.category || "其他",
        desc: m.factor_name,                            // 显示名（展示用，如 1月波动率）
        icMean: 0, icIr: 0, layerReturn: 0,
        _hasResult: false,
        _icSeries: [],
        _layerReturns: [],
      }));
    }

    // 恢复已完成的因子研究结果（页面刷新后数据不丢失）
    const tasksRes = await dataAPI.getRecentResearchTasks().catch(() => null);
    const recentTasks: any[] = tasksRes?.recent_tasks || [];
    console.log(`[FactorDashboard] Recent tasks: ${recentTasks.length} total, statuses:`,
      recentTasks.map(t => `${t.factor_code || t.factor_name}=${t.status}`));
    const completedTasks = recentTasks.filter(
      (t: any) => t.status === "completed" && (t.factor_code || t.factor_name)
    );
    if (completedTasks.length > 0) {
      // 每个因子只取最新的一条已完成研究（按 factor_code 去重）
      const seenFactors = new Set<string>();
      const tasksToLoad: any[] = [];
      for (const t of completedTasks) {
        const code = t.factor_code || t.factor_name;
        if (!seenFactors.has(code)) {
          seenFactors.add(code);
          tasksToLoad.push(t);
        }
      }
      // 并行加载详情并应用到列表
      const details = await Promise.all(
        tasksToLoad.map(t =>
          dataAPI.getResearchTaskDetail(t.research_id).catch(() => null)
        )
      );
      console.log(`[FactorDashboard] Loaded ${details.filter(Boolean).length}/${details.length} details`);
      for (const detail of details) {
        if (detail) {
          console.log(`[FactorDashboard] Detail for ${detail.factor_code || detail.factor_name}: result keys=`,
            detail.result ? Object.keys(detail.result) : 'null');
          applyResearchResults(detail);
        }
      }
    } else {
      console.log('[FactorDashboard] No completed tasks found among recent tasks');
    }
  } catch {
    pageError.value = true;
  } finally {
    pageLoading.value = false;
  }
};

/** 全选：从 factorSelectOptions 中提取所有叶子节点 value（确保与 n-select 选项一致） */
const selectAllFactors = () => {
  const allValues: string[] = [];
  for (const group of factorSelectOptions.value) {
    if ((group as any).children) {
      for (const child of (group as any).children) {
        allValues.push(child.value);
      }
    }
  }
  // 新数组引用确保 Vue reactive 触发 n-select 内部同步
  researchConfig.selectedFactors = [...allValues];
};

const startResearch = async () => {
  if (researchConfig.selectedFactors.length === 0) {
    msg.warning("请至少选择一个因子");
    return;
  }
  researchStatus.value = "running";
  lastError.value = "";
  researchProgress.value = 0;
  calculatedCount.value = 0;
  completedResearchIds.value = new Set();

  try {
    const dr = researchConfig.dateRange;
    const today = new Date();
    const defaultStart = new Date(today.getFullYear() - 1, today.getMonth(), 1).toISOString().slice(0, 10);
    const defaultEnd = today.toISOString().slice(0, 10);
    const params: any = {
      factor_names: researchConfig.selectedFactors,
      universe: researchConfig.universe,
      basket_ids: researchConfig.basketIds.length > 0 ? researchConfig.basketIds : undefined,
      start_date: dr && Array.isArray(dr) && dr.length === 2 ? dr[0] : defaultStart,
      end_date: dr && Array.isArray(dr) && dr.length === 2 ? dr[1] : defaultEnd,
      frequency: "D",
      group_count: 5,
    };

    const res = await dataAPI.submitFactorResearch(params).catch(() => null);
    if (!res?.research_id && !res?.parameters?.research_ids) {
      msg.error("提交研究任务失败");
      researchStatus.value = "failed";
      return;
    }
    // 后端为每个因子创建一个独立 research 任务，全部追踪
    researchId.value = res.research_id;
    allResearchIds.value = res.parameters?.research_ids || [res.research_id];
    startPolling();
  } catch (err) {
    msg.error("提交研究任务失败");
    researchStatus.value = "failed";
  }
};

const cancelResearch = async () => {
  if (allResearchIds.value.length === 0) return;
  if (researchStatus.value !== "running") return;
  cancelling.value = true;
  try {
    // 取消所有运行中的研究任务
    const results = await Promise.all(
      allResearchIds.value.map(id => dataAPI.cancelFactorResearch(id).catch(() => null))
    );
    const allCancelled = results.every(r => r?.success !== false);
    if (allCancelled) {
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      researchStatus.value = "cancelled";
      msg.success("所有研究已取消");
    } else {
      msg.warning("部分研究取消失败");
    }
  } catch {
    msg.error("取消失败");
  } finally {
    cancelling.value = false;
  }
};

const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer);
  const ids = allResearchIds.value;
  pollTimer = setInterval(async () => {
    try {
      // 并行查询所有研究任务状态
      const statuses = await Promise.all(
        ids.map(id => dataAPI.getResearchStatus({ research_id: id }).catch(() => null))
      );
      const validStatuses = statuses.filter(Boolean);

      if (validStatuses.length === 0) return;

      // 汇总进度：取平均值
      const totalProgress = validStatuses.reduce((sum, s) => sum + (s.progress || 0), 0);
      researchProgress.value = totalProgress / validStatuses.length;
      calculatedCount.value = validStatuses.reduce((sum, s) => sum + (s.calculated_count || 0), 0);
      totalStocks.value = validStatuses.reduce((sum, s) => sum + (s.total_stocks || 0), 0);

      // 单独处理每个任务的结果
      for (const status of validStatuses) {
        const rid = status.research_id;
        if (status.status === "completed" && !completedResearchIds.value.has(rid)) {
          completedResearchIds.value.add(rid);
          applyResearchResults(status);
        } else if (status.status === "failed") {
          completedResearchIds.value.add(rid);
          if (!lastError.value) {
            lastError.value = status.error_message || "研究任务执行失败";
          }
        } else if (status.status === "cancelled") {
          completedResearchIds.value.add(rid);
        }
      }

      // 所有任务完成
      if (completedResearchIds.value.size >= ids.length) {
        clearInterval(pollTimer!);
        pollTimer = null;
        const hasCompleted = validStatuses.some(s => s.status === "completed");
        const hasFailed = validStatuses.some(s => s.status === "failed");
        if (hasFailed && !hasCompleted) {
          researchStatus.value = "failed";
        } else if (hasCompleted) {
          researchStatus.value = "completed";
        } else {
          researchStatus.value = "cancelled";
        }
      }
    } catch {
      // polling error, continue
    }
  }, 2000);
};

/** Apply research results to factor list */
const applyResearchResults = (response: any) => {
  if (!response) return;

  const factorCode: string = (response.factor_code || response.factor_name || "").trim();
  const result = response.result || {};
  if (!factorCode || !result || typeof result !== 'object') {
    console.warn('[applyResearchResults] Skipped:', { factorCode, resultType: typeof result });
    return;
  }

  // 无分析数据时仍标记为已研究，但使用占位值（前端显示"无数据"而非"--"）
  if (result._empty) {
    console.warn('[applyResearchResults] Factor "' + factorCode + '" 计算完成但分析无数据', result);
    factorList.value = factorList.value.map(f => {
      if (f.name !== factorCode && f.name.toLowerCase() !== factorCode.toLowerCase()) return f;
      return {
        ...f,
        _hasResult: true,
        _isEmpty: true,
        _icSeries: [],
        _layerReturns: [],
        icMean: 0, icIr: 0, layerReturn: 0,
      };
    });
    return;
  }

  // 兼容旧版未展平的数据结构
  let effectiveResult = result;
  if (!result.ic_analysis && !result.icAnalysis && result.analysis_results && typeof result.analysis_results === 'object') {
    effectiveResult = result.analysis_results;
  }

  const icData: any = effectiveResult.ic_analysis || effectiveResult.icAnalysis || {};
  const quantileData: any = effectiveResult.quantile_analysis || effectiveResult.quantileAnalysis || {};
  const hasData = Object.keys(icData).length > 0 || Object.keys(quantileData).length > 0;
  if (!hasData) {
    console.warn('[applyResearchResults] No IC/quantile data for factor "' + factorCode + '", keys:', Object.keys(effectiveResult));
    return;
  }

  console.log('[applyResearchResults] Found data for "' + factorCode + '": icMean=' + icData.ic_mean + ', icIr=' + icData.ic_ir);

  // Map result to the specific factor in the list (case-insensitive match)
  factorList.value = factorList.value.map(f => {
    if (f.name !== factorCode && f.name.toLowerCase() !== factorCode.toLowerCase()) return f;

    // --- IC data ---
    const icMean: number = icData.ic_mean ?? icData.icMean ?? 0;
    const icIr: number = icData.ic_ir ?? icData.icIr ?? 0;
    const winRate: number = icData.win_rate ?? icData.winRate
      ?? icData.ic_positive_ratio ?? icData.icPositiveRatio;
    const rankIc: number = icData.rank_ic ?? icData.rankIc;

    const icSeriesRaw = icData.ic_series || icData.icSeries || [];
    const icSeries: Array<{ date: string; value: number }> = [];
    if (Array.isArray(icSeriesRaw)) {
      for (let i = 0; i < icSeriesRaw.length; i++) {
        const d = icSeriesRaw[i];
        if (typeof d === 'object' && d !== null) {
          icSeries.push({
            date: d.date || d.period || String(i + 1),
            value: d.value ?? d.ic_value ?? 0,
          });
        } else {
          icSeries.push({ date: String(i + 1), value: typeof d === 'number' ? d : 0 });
        }
      }
    }

    // --- Quantile / layer returns ---
    const layerReturnsRaw = quantileData.quantile_returns || quantileData.quantileReturns || [];
    const layerReturns: Array<{ label: string; return_: number }> = [];
    if (Array.isArray(layerReturnsRaw)) {
      for (let i = 0; i < layerReturnsRaw.length; i++) {
        const l = layerReturnsRaw[i];
        if (typeof l === 'object' && l !== null) {
          layerReturns.push({
            label: l.label || l.group || l.quantile || 'Q' + (i + 1),
            return_: l.return_ ?? l.return ?? l.value ?? 0,
          });
        } else {
          layerReturns.push({
            label: 'Q' + (i + 1),
            return_: typeof l === 'number' ? l : 0,
          });
        }
      }
    }
    const topBottom: number = quantileData.top_minus_bottom ?? quantileData.topMinusBottom ?? 0;

    return {
      ...f,
      icMean,
      icIr,
      layerReturn: topBottom,
      _hasResult: Object.keys(icData).length > 0 || Object.keys(quantileData).length > 0,
      _icSeries: icSeries,
      _layerReturns: layerReturns,
      _rankIc: rankIc,
      _winRate: winRate,
      _topBottom: topBottom,
    };
  });
};


const generateStrategy = () => {
  if (!selectedFactor.value) return;
  const f = selectedFactor.value;
  msg.info(`跳转策略工作台，基于因子 ${f.name} 生成策略`);
  router.push(`/strategies/workspace/new?template=factor&factor=${f.name}&ic=${f.icMean.toFixed(3)}&ic_ir=${f.icIr.toFixed(2)}`);
};

onMounted(() => { loadMetadata(); loadUniverseOptions(); loadBasketOptions(); });

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
