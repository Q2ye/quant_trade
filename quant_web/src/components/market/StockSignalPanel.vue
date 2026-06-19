<!-- StockSignalPanel.vue — 个股右侧信号面板（因子得分 + 风险 + 策略信号） -->
<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { NCard, NProgress, NTag, NSpace, NSkeleton, NDivider } from "naive-ui";
import VChart from "vue-echarts";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { RadarChart, BarChart } from "echarts/charts";
import {
  RadarComponent,
  TooltipComponent,
  GridComponent,
} from "echarts/components";
use([
  CanvasRenderer,
  RadarChart,
  BarChart,
  RadarComponent,
  TooltipComponent,
  GridComponent,
]);

const props = defineProps<{
  basicInfo: Record<string, any> | null;
  factorData: Record<string, any>[];
  riskData: Record<string, any>;
  loading?: boolean;
}>();

const router = useRouter();

// ---- extract latest factor values ----
const latestFactors = computed(() => {
  const rows = props.factorData;
  if (!rows?.length) return [];
  const latest = rows[rows.length - 1] || {};
  // filter to numeric columns, exclude meta keys
  const metaKeys = ["ts_code", "trade_date", "id", "created_at", "updated_at"];
  return Object.entries(latest)
    .filter(
      ([k, v]) =>
        !metaKeys.includes(k) && typeof v === "number" && !isNaN(v as number),
    )
    .map(([k, v]) => ({ key: k, value: v as number }))
    .slice(0, 12);
});

// ---- computed score from factor data ----
const compositeScore = computed(() => {
  if (!latestFactors.value.length) return null;
  // simple normalized average; higher absolute value → higher signal
  const vals = latestFactors.value.map((f) => Math.abs(f.value));
  const max = Math.max(...vals, 1);
  const normSum = vals.reduce((s, v) => s + (v / max) * 100, 0);
  return Math.round(normSum / vals.length);
});

const scoreGrade = computed(() => {
  const s = compositeScore.value;
  if (s == null) return { text: "无数据", color: "default" };
  if (s >= 80) return { text: "A", color: "#26a69a" };
  if (s >= 60) return { text: "B", color: "#448AFF" };
  if (s >= 40) return { text: "C", color: "#ff9800" };
  return { text: "D", color: "#ef5350" };
});

// ---- radar chart (top 6 factors) ----
const factorBarOption = computed(() => {
  const items = latestFactors.value.slice(0, 8).reverse();
  if (!items.length) return null;
  const maxVal = Math.max(...items.map((f) => Math.abs(f.value)), 0.01);
  return {
    grid: { top: 5, right: 30, bottom: 10, left: 60 },
    xAxis: { type: "value", max: maxVal * 1.2, axisLabel: { fontSize: 9 } },
    yAxis: {
      type: "category",
      data: items.map((f) => f.key),
      axisLabel: { fontSize: 10 },
      inverse: true,
    },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "bar",
        data: items.map((f) => ({
          value: Math.abs(f.value),
          itemStyle: {
            color: f.value >= 0 ? "#ef5350" : "#26a69a",
            borderRadius: [0, 3, 3, 0],
          },
          name: f.key,
        })),
        barMaxWidth: 14,
      },
    ],
  };
});

// ---- risk flags ----
const riskFlags = computed(() => {
  const flags: { label: string; type: "error" | "warning" | "success" }[] = [];
  const b = props.basicInfo;
  const r = props.riskData || {};
  if (b?.is_st) flags.push({ label: "ST", type: "error" });
  else flags.push({ label: "正常上市", type: "success" });
  if (b?.list_status === "P") flags.push({ label: "暂停上市", type: "error" });
  if (b?.list_status === "D") flags.push({ label: "已退市", type: "error" });
  if (
    r?.pledge_stat?.pledge_ratio != null &&
    r.pledge_stat.pledge_ratio > 0.3
  ) {
    flags.push({
      label: `质押 ${(r.pledge_stat.pledge_ratio * 100).toFixed(0)}%`,
      type: "warning",
    });
  }
  if (r?.st_risk?.risk_level) {
    flags.push({ label: r.st_risk.risk_level, type: "warning" });
  }
  return flags;
});
</script>

<template>
  <div class="signal-panel">
    <!-- Score Card -->
    <n-card size="small" :bordered="false" class="score-card">
      <template v-if="loading">
        <n-skeleton :text="true" :repeat="4" />
      </template>
      <template v-else>
        <div class="score-main">
          <span class="score-num">{{ compositeScore ?? "--" }}</span>
          <span class="score-total">/100</span>
        </div>
        <n-tag
          :color="{ color: scoreGrade.color, textColor: '#fff' }"
          size="medium"
          round
        >
          {{ scoreGrade.text }}级
        </n-tag>
        <div class="score-note">综合信号评分（基于最近因子数据）</div>
      </template>
    </n-card>

    <n-divider style="margin: 8px 0" />

    <!-- Industry + Risk -->
    <div class="meta-row" v-if="basicInfo">
      <n-space size="small" wrap>
        <n-tag size="tiny" v-if="basicInfo.industry">{{
          basicInfo.industry
        }}</n-tag>
        <n-tag size="tiny" v-if="basicInfo.area">{{ basicInfo.area }}</n-tag>
        <n-tag
          v-for="f in riskFlags"
          :key="f.label"
          size="tiny"
          :type="f.type"
          >{{ f.label }}</n-tag
        >
      </n-space>
    </div>

    <n-divider style="margin: 8px 0" />

    <!-- Factor bar chart -->
    <template v-if="factorBarOption">
      <div class="section-title">因子强度</div>
      <VChart :option="factorBarOption" autoresize style="height: 200px" />
    </template>
    <n-empty
      v-else
      description="暂无因子数据"
      size="small"
      style="padding: 16px"
    />

    <n-divider style="margin: 8px 0" />

    <!-- Quick links -->
    <div class="section-title">快捷操作</div>
    <n-space vertical size="small" style="margin-top: 4px">
      <n-tag
        size="small"
        :bordered="true"
        style="cursor: pointer"
        @click="
          router.push(
            '/market/screener?industry=' +
              encodeURIComponent(basicInfo?.industry || ''),
          )
        "
      >
        同行业股票 →
      </n-tag>
      <n-tag
        size="small"
        :bordered="true"
        style="cursor: pointer"
        @click="
          router.push('/backtest/config?stock=' + (basicInfo?.ts_code || ''))
        "
      >
        快速回测此股 →
      </n-tag>
    </n-space>
  </div>
</template>

<style lang="scss" scoped>
.signal-panel {
  width: 100%;
}

.score-card {
  text-align: center;
}

.score-main {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
}

.score-num {
  font-size: 42px;
  font-weight: 700;
  font-family: monospace;
}

.score-total {
  font-size: 16px;
  color: var(--n-text-color-3);
}

.score-note {
  font-size: 11px;
  color: var(--n-text-color-3);
  margin-top: 4px;
}

.meta-row {
  padding: 0 4px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color-2);
  margin-bottom: 2px;
}
</style>
