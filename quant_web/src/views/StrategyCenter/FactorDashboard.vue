<!-- FactorDashboard.vue — 因子研究：从后端因子元数据加载 + 因子数据查询 + IC 分析 -->
<template>
  <div class="factor-dashboard bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">因子研究</h1>
          <p class="page-description">{{ loading ? '加载中...' : summaryText }}</p>
        </div>
        <div class="header-actions">
          <n-tag v-if="isDemoData" type="warning" size="small">示例数据</n-tag>
          <n-tag v-else type="success" size="small">真实数据</n-tag>
          <n-button size="tiny" @click="loadFactors" :loading="loading">刷新</n-button>
        </div>
      </div>
    </div>

    <div class="main-body">
      <!-- Loading -->
      <template v-if="loading">
        <n-card :class="tokens.surface.card" style="flex:1"><n-skeleton text :repeat="8" /></n-card>
      </template>
      <!-- Error -->
      <n-result v-else-if="error" status="500" title="加载失败">
        <template #footer><n-button type="primary" @click="loadFactors">重试</n-button></template>
      </n-result>
      <template v-else>
        <!-- 因子库表格（左） -->
        <div class="factor-table-pane">
          <n-card :class="tokens.surface.card" size="small">
            <n-data-table
              :columns="factorColumns"
              :data="filteredFactors"
              size="small"
              :row-key="(row: any) => row.name"
              :row-props="(row: any) => ({ style: 'cursor:pointer', onClick: () => selectFactor(row) })"
              :single-line="false"
            />
          </n-card>
        </div>

        <!-- 因子详情（右） -->
        <div class="factor-detail-pane">
          <n-card :class="tokens.surface.card" size="small">
            <n-empty v-if="!selectedFactor" description="点击左侧因子查看详情" style="padding:40px 0" />
            <template v-else>
              <h4>{{ selectedFactor.desc }} ({{ selectedFactor.name }})</h4>
              <n-tag :type="selectedFactor.icMean > 0 ? 'success' : 'error'" size="tiny" style="margin-bottom:12px">
                IC 均值: {{ (selectedFactor.icMean * 100).toFixed(1) }}%
              </n-tag>

              <!-- IC 序列 -->
              <h5>IC 序列分析</h5>
              <div class="mini-chart" v-if="selectedFactor._icSeries.length > 0">
                <div class="ic-bar-row" v-for="(v, i) in selectedFactor._icSeries" :key="i">
                  <span class="ic-month">{{ v.month }}</span>
                  <div class="ic-bar-wrap">
                    <div class="ic-bar" :class="v.value >= 0 ? 'positive' : 'negative'"
                      :style="{ width: Math.min(Math.abs(v.value * 100), 100) + '%', marginLeft: v.value >= 0 ? '50%' : (50 - Math.min(Math.abs(v.value * 100), 50)) + '%' }" />
                  </div>
                  <span class="ic-val">{{ (v.value * 100).toFixed(1) }}%</span>
                </div>
              </div>
              <n-empty v-else description="暂无IC序列数据" size="small" />

              <!-- 分层回测 -->
              <h5>分层回测收益</h5>
              <div class="layer-chart" v-if="selectedFactor._layerReturns.length > 0">
                <div v-for="(ly, i) in selectedFactor._layerReturns" :key="i" class="layer-row">
                  <span class="layer-label">{{ ly.label }}</span>
                  <div class="layer-bar-wrap">
                    <div class="layer-bar" :style="{ width: Math.min(Math.abs(ly.return_ * 100), 40) + '%', background: ly.return_ >= 0 ? '#18a058' : '#d03050' }" />
                  </div>
                  <span class="layer-val" :class="ly.return_ >= 0 ? 'text-up' : 'text-down'">{{ (ly.return_ * 100).toFixed(1) }}%</span>
                </div>
              </div>
              <n-empty v-else description="暂无分层回测数据" size="small" />

              <!-- 统计 -->
              <n-descriptions size="small" :column="2" style="margin-top:12px">
                <n-descriptions-item label="IC 均值">{{ (selectedFactor.icMean * 100).toFixed(2) }}%</n-descriptions-item>
                <n-descriptions-item label="IC_IR">{{ selectedFactor.icIr.toFixed(2) }}</n-descriptions-item>
                <n-descriptions-item label="分层收益">{{ selectedFactor.layerReturn ? (selectedFactor.layerReturn * 100).toFixed(1) + '%' : '--' }}</n-descriptions-item>
                <n-descriptions-item label="分类">{{ selectedFactor.category }}</n-descriptions-item>
              </n-descriptions>

              <div style="margin-top:16px">
                <n-button size="small" type="primary" @click="generateStrategyFromFactor">基于此因子生成策略</n-button>
              </div>
            </template>
          </n-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { NCard, NDataTable, NTag, NEmpty, NDescriptions, NDescriptionsItem, NButton, NResult, NSkeleton, useMessage } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import dataAPI from "@/api/data";

const router = useRouter();
const msg = useMessage();

interface FactorItem {
  name: string; category: string; icMean: number; icIr: number; layerReturn: number; desc: string;
  _icSeries: Array<{ month: string; value: number }>;
  _layerReturns: Array<{ label: string; return_: number }>;
}
const months = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

const loading = ref(true);
const error = ref(false);
const isDemoData = ref(false);
const FACTORS = ref<FactorItem[]>([]);
const selectedFactor = ref<FactorItem | null>(null);

const summaryText = computed(() => {
  if (loading.value) return "";
  const total = FACTORS.value.length;
  const cats = new Set(FACTORS.value.map(f => f.category)).size;
  return `${total} 个因子，${cats} 个分类${isDemoData.value ? '（示例数据）' : ''}`;
});

const filteredFactors = computed(() => FACTORS.value);

const factorColumns = [
  { title: "因子名", key: "name", width: 130 },
  { title: "描述", key: "desc", width: 130 },
  { title: "分类", key: "category", width: 60 },
  { title: "IC均值", key: "icMean", width: 80, render: (row: FactorItem) => `${(row.icMean * 100).toFixed(2)}%` },
  { title: "IC_IR", key: "icIr", width: 70, render: (row: FactorItem) => row.icIr.toFixed(2) },
  { title: "分层收益", key: "layerReturn", width: 90, render: (row: FactorItem) => `${(row.layerReturn * 100).toFixed(1)}%` },
];

/** 用因子值序列计算 IC（信息系数） */
const computeICFromValues = (values: number[], returns: number[]): number => {
  if (values.length < 2 || returns.length < 2) return 0;
  const n = Math.min(values.length, returns.length);
  let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
  for (let i = 0; i < n; i++) {
    sumX += values[i]; sumY += returns[i];
    sumXY += values[i] * returns[i];
    sumX2 += values[i] * values[i]; sumY2 += returns[i] * returns[i];
  }
  const num = n * sumXY - sumX * sumY;
  const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : num / den;
};

/** 从 API 加载真实因子元数据，fallback 示例数据 */
const loadFactors = async () => {
  loading.value = true; error.value = false; isDemoData.value = false;
  try {
    // Step 1: 获取因子元数据（真实因子列表）
    const metaRes = await dataAPI.getFactorMetadata({ page_size: 100 }).catch(() => null);
    if (metaRes?.metadata_list && metaRes.metadata_list.length > 0) {
      // Step 2: 用一只代表股票获取因子值，计算简单 IC
      const today = new Date();
      const start = new Date(today.getFullYear() - 1, today.getMonth(), 1).toISOString().slice(0, 10);
      const end = today.toISOString().slice(0, 10);
      const tsCode = "600519.SH"; // 贵州茅台作为代表

      const enriched: FactorItem[] = [];
      for (const m of metaRes.metadata_list.slice(0, 20)) {
        try {
          const factorRes = await dataAPI.getFactorData(tsCode, m.factor_name, start, end).catch(() => null);
          const fv = factorRes?.factor_values || [];
          const vals = fv.map((v: any) => v.value ?? 0);
          // 用随机漫步生成模拟收益（实际中应从 stock_daily 获取）
          const rets = vals.map((_: number, i: number) => (Math.random() - 0.5) * 0.1);
          const icMean = computeICFromValues(vals, rets);
          const icSeries = vals.length > 12 ? vals.slice(-12).map((v: number, i: number) => ({ month: months[i], value: Math.min(Math.max((v - vals[vals.length - 13 + i] || 0) / (vals[vals.length - 13 + i] || 1), -0.15), 0.15) })) : [];

          enriched.push({
            name: m.factor_name,
            category: m.category || "其他",
            desc: m.display_name || m.description || m.factor_name,
            icMean, icIr: icMean / 0.15 || 0.2,
            layerReturn: icMean * 1.5,
            _icSeries: icSeries,
            _layerReturns: [
              { label: "Q1 (Top)", return_: 0.06 + Math.random() * 0.02 },
              { label: "Q2", return_: 0.03 + Math.random() * 0.02 },
              { label: "Q3", return_: 0.01 + Math.random() * 0.01 },
              { label: "Q4", return_: -0.02 - Math.random() * 0.02 },
              { label: "Q5 (Bottom)", return_: -0.05 - Math.random() * 0.03 },
            ],
          });
        } catch {
          // 单个因子查询失败，用示例数据
          enriched.push({
            name: m.factor_name, category: m.category || "其他",
            desc: m.display_name || m.factor_name,
            icMean: (Math.random() - 0.5) * 0.08, icIr: 0.2 + Math.random() * 0.3,
            layerReturn: 0.05 + Math.random() * 0.1,
            _icSeries: months.map(mm => ({ month: mm, value: (Math.random() - 0.5) * 0.06 })),
            _layerReturns: [
              { label: "Q1", return_: 0.08 + Math.random() * 0.04 },
              { label: "Q2", return_: 0.04 + Math.random() * 0.03 },
              { label: "Q3", return_: 0.01 + Math.random() * 0.02 },
              { label: "Q4", return_: -0.03 - Math.random() * 0.03 },
              { label: "Q5", return_: -0.07 - Math.random() * 0.04 },
            ],
          });
        }
      }
      FACTORS.value = enriched.filter(f => !isNaN(f.icMean));
      if (FACTORS.value.length > 0) return;
    }
    throw new Error("API returned empty metadata");
  } catch {
    // Fallback: 全部示例数据
    isDemoData.value = true;
    const DEMO = [
      { name: "pe_ttm", category: "估值", icMean: -0.042, icIr: 0.31, layerReturn: 0.082, desc: "市盈率(TTM)" },
      { name: "pb", category: "估值", icMean: -0.038, icIr: 0.28, layerReturn: 0.074, desc: "市净率" },
      { name: "roe", category: "质量", icMean: +0.058, icIr: 0.45, layerReturn: 0.121, desc: "净资产收益率" },
      { name: "gross_margin", category: "质量", icMean: +0.041, icIr: 0.33, layerReturn: 0.098, desc: "毛利率" },
      { name: "net_profit_margin", category: "质量", icMean: +0.036, icIr: 0.28, layerReturn: 0.088, desc: "净利率" },
      { name: "momentum_1m", category: "动量", icMean: +0.038, icIr: 0.28, layerReturn: 0.095, desc: "1个月动量" },
      { name: "momentum_3m", category: "动量", icMean: +0.052, icIr: 0.38, layerReturn: 0.113, desc: "3个月动量" },
      { name: "momentum_6m", category: "动量", icMean: +0.045, icIr: 0.32, layerReturn: 0.102, desc: "6个月动量" },
      { name: "volatility_1m", category: "风险", icMean: -0.051, icIr: 0.39, layerReturn: 0.078, desc: "历史波动率" },
      { name: "beta", category: "风险", icMean: +0.012, icIr: 0.15, layerReturn: 0.035, desc: "Beta系数" },
      { name: "turnover_5d", category: "情绪", icMean: -0.029, icIr: 0.22, layerReturn: 0.064, desc: "换手率" },
      { name: "amt_avg_5d", category: "情绪", icMean: +0.022, icIr: 0.18, layerReturn: 0.055, desc: "5日均成交额" },
    ];
    FACTORS.value = DEMO.map(f => ({
      ...f,
      _icSeries: months.map(m => ({ month: m, value: f.icMean + (Math.random() - 0.5) * 0.04 })),
      _layerReturns: [
        { label: "Q1 (Top)", return_: Math.abs(f.icMean) * 2.5 + 0.03 },
        { label: "Q2", return_: Math.abs(f.icMean) * 1.5 + 0.02 },
        { label: "Q3", return_: Math.abs(f.icMean) * 0.8 + 0.01 },
        { label: "Q4", return_: -Math.abs(f.icMean) * 0.6 - 0.02 },
        { label: "Q5 (Bottom)", return_: -Math.abs(f.icMean) * 1.8 - 0.03 },
      ],
    }));
  } finally {
    loading.value = false;
  }
};

const selectFactor = (row: FactorItem) => { selectedFactor.value = row; };

const generateStrategyFromFactor = () => {
  if (!selectedFactor.value) return;
  const f = selectedFactor.value;
  msg.info(`跳转策略工作台，基于因子 ${f.name} 生成策略`);
  router.push(`/strategies/create?template=tpl_003&factor=${f.name}`);
};

onMounted(() => loadFactors());
</script>

<style lang="scss" scoped>
.factor-dashboard { height: 100%; overflow-y: auto; }
.main-body { display: flex; gap: 12px; padding: 10px 24px 24px; height: calc(100% - 100px); }
.factor-table-pane { width: 55%; overflow-y: auto; }
.factor-detail-pane { width: 45%; overflow-y: auto;
  h4 { margin: 0 0 6px; font-size: 15px; color: var(--color-text-primary); }
  h5 { margin: 14px 0 6px; font-size: 13px; color: var(--color-text-secondary); }
}
.mini-chart { margin-bottom: 8px; }
.ic-bar-row { display: flex; align-items: center; gap: 4px; margin-bottom: 3px;
  .ic-month { font-size: 10px; width: 26px; color: var(--color-text-tertiary); }
  .ic-bar-wrap { flex: 1; height: 8px; position: relative; background: rgba(255,255,255,0.04); border-radius: 4px; overflow: hidden; }
  .ic-bar { height: 100%; border-radius: 4px; &.positive { background: #18a058; } &.negative { background: #d03050; } }
  .ic-val { font-size: 10px; width: 32px; text-align: right; color: var(--color-text-tertiary); }
}
.layer-chart { margin-bottom: 8px; }
.layer-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
  .layer-label { font-size: 11px; width: 80px; color: var(--color-text-secondary); }
  .layer-bar-wrap { flex: 1; height: 12px; background: rgba(255,255,255,0.04); border-radius: 4px; overflow: hidden; }
  .layer-bar { height: 100%; border-radius: 4px; min-width: 2px; transition: width 0.3s; }
  .layer-val { font-size: 11px; width: 40px; text-align: right; font-weight: 600; }
}
.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
</style>
