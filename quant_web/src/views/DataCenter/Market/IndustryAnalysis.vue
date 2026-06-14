<!-- IndustryAnalysis.vue — 申万行业分析（矩形树图 + 动量和量能 + 排名迁移） -->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NTabs, NTabPane, NButton, useMessage } from "naive-ui";
import marketAPI from "@/api/market";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";

import IndustryTreemap from "@/components/market/IndustryTreemap.vue";
import IndustryTrendChart from "@/components/market/IndustryTrendChart.vue";
import IndustryMomentumScatter from "@/components/market/IndustryMomentumScatter.vue";
import IndustryRankChart from "@/components/market/IndustryRankChart.vue";
import IndustryDetailPanel from "@/components/market/IndustryDetailPanel.vue";
import type { StageStatItem } from "@/components/market/IndustryDetailPanel.vue";
import type { SwHeatmapItem } from "@/types/entities/market";

const route = useRoute();
const router = useRouter();
const message = useMessage();

const loading = ref(true);
const error = ref(false);
const heatmapData = ref<SwHeatmapItem[]>([]);
const trendData = ref<any>(null);
const trendLoading = ref(false);
const trendDays = ref(60);

// ---- detail state ----
const selectedCode = ref("");
const selectedName = ref("");

// ---- heatmap config (for stage stats) ----
const heatmapKeys: (keyof SwHeatmapItem)[] = [
  "pct_1d",
  "pct_5d",
  "pct_10d",
  "pct_20d",
  "pct_30d",
  "pct_60d",
];
const heatmapLabels: Record<string, string> = {
  pct_1d: "今日",
  pct_5d: "5日",
  pct_10d: "10日",
  pct_20d: "20日",
  pct_30d: "30日",
  pct_60d: "60日",
};

// ---- stage stats (computed from heatmapData + selected industry) ----
const stageStats = computed<StageStatItem[]>(() => {
  if (!selectedCode.value || !heatmapData.value.length) return [];
  const selected = heatmapData.value.find((r) => r.code === selectedCode.value);
  if (!selected) return [];
  return heatmapKeys.map((k) => {
    const pct = (selected[k] as number | null | undefined) ?? null;
    const rank =
      heatmapData.value.filter(
        (r) => ((r[k] as number | null | undefined) ?? -9999) > (pct ?? -9999),
      ).length + 1;
    return {
      label: heatmapLabels[k] || k,
      pct,
      rank,
    };
  });
});

// ---- handlers ----
function onTreemapSelect(code: string, name: string) {
  selectedCode.value = code;
  selectedName.value = name;
}

function onDetailClose() {
  selectedCode.value = "";
  selectedName.value = "";
}

async function fetchTrend(days_val?: number) {
  trendLoading.value = true;
  const d = days_val ?? trendDays.value;
  try {
    trendData.value = await marketAPI.getIndustryTrend(d);
  } catch {
    trendData.value = null;
  }
  trendLoading.value = false;
}

async function load() {
  loading.value = true;
  error.value = false;
  try {
    heatmapData.value = await marketAPI.getIndustryHeatmap({
      windows: "1d,5d,10d,20d,30d,60d",
    });
    // auto-focus from query param
    const focus = route.query.focus as string;
    if (focus && heatmapData.value.length) {
      const item = heatmapData.value.find((r) => r.name === focus);
      if (item) {
        selectedCode.value = item.code;
        selectedName.value = item.name;
      }
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
  fetchTrend();
}

function goBack() {
  if (window.history.length > 1) router.back();
  else router.push("/market/dashboard");
}

onMounted(load);
</script>

<template>
  <div class="industry-page bg-gradient-mesh bg-noise">
    <div class="page-header glass-surface">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">申万行业分析</h1>
          <p class="page-description">28 个申万一级行业 · 多维度轮动分析</p>
        </div>
        <div class="header-actions">
          <n-button
            size="tiny"
            type="primary"
            ghost
            @click="
              router.push(
                '/strategies/create?template=industry_rotation&sector=' +
                  encodeURIComponent(selectedName || ''),
              )
            "
            >创建行业轮动策略</n-button
          >
          <n-button class="action-btn" @click="goBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-tabs type="line" animated default-value="treemap">
        <n-tab-pane name="treemap" tab="矩形树图">
          <IndustryTreemap
            :data="heatmapData"
            :loading="loading"
            :error="error"
            @select="onTreemapSelect"
            @retry="load"
          />
        </n-tab-pane>

        <n-tab-pane name="rank" tab="排名迁移">
          <IndustryRankChart
            :data="heatmapData"
            :loading="loading"
            :error="error"
            :selected-code="selectedCode"
            @select="onTreemapSelect"
            @retry="load"
          />
        </n-tab-pane>

        <n-tab-pane name="trend" tab="趋势对比">
          <IndustryTrendChart
            :data="trendData"
            :loading="trendLoading"
            :selected-code="selectedCode"
            @select="onTreemapSelect"
            @retry="fetchTrend()"
          />
        </n-tab-pane>

        <n-tab-pane name="scatter" tab="动量和量能">
          <IndustryMomentumScatter
            :data="heatmapData"
            :loading="loading"
            :error="error"
            :selected-code="selectedCode"
            @select="onTreemapSelect"
            @retry="load"
          />
        </n-tab-pane>
      </n-tabs>

      <!-- Detail panel (shared across tabs) -->
      <IndustryDetailPanel
        :code="selectedCode"
        :name="selectedName"
        :visible="!!selectedCode"
        :stage-stats="stageStats"
        @close="onDetailClose"
      />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.industry-page {
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}

.main-content {
  padding: 0 16px;
}
</style>
