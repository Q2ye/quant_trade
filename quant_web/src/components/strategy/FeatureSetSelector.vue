<!-- FeatureSetSelector.vue — 特征集选择器 v3.4 -->
<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { NSelect, NTag, NText } from "naive-ui";
import strategyAPI from "@/api/strategy";

const props = defineProps<{
  modelValue?: string[];
  category?: string;
}>();

const emit = defineEmits<{ "update:modelValue": [value: string[]] }>();

const featureSets = ref<any[]>([]);
const loading = ref(false);

const options = computed(() => {
  const grouped: Record<string, any[]> = {};
  for (const fs of featureSets.value) {
    const cat = fs.category || "custom";
    if (props.category && cat !== props.category) continue;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push({
      label: fs.name,
      value: fs.id,
      description: fs.description || "",
      count: Array.isArray(fs.feature_columns) ? fs.feature_columns.length : 0,
    });
  }
  const result: any[] = [];
  for (const [cat, items] of Object.entries(grouped)) {
    result.push({
      type: "group",
      label: categoryLabel(cat),
      key: cat,
      children: items,
    });
  }
  return result;
});

function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    etf_bottom: "ETF 抄底",
    momentum: "动量",
    value: "价值",
    volatility: "波动",
    quality: "质量",
    volume: "量价",
    custom: "自定义",
  };
  return map[cat] || cat;
}

const selectedIds = ref<string[]>(props.modelValue || []);
const activeSet = computed(() => {
  if (selectedIds.value.length === 0) return null;
  return featureSets.value.find((f: any) => f.id === selectedIds.value[0]) || null;
});

async function loadFeatureSets() {
  loading.value = true;
  try {
    const data = await strategyAPI.getFeatureSets();
    if (data && data.length > 0) {
      featureSets.value = data;
      return;
    }
  } catch { /* API 不可用，使用内置预设 */ }
  // 内置预设（与 DB 中 feature_sets 表同步）
  featureSets.value = [
    { id: "etf_bottom_oversold", name: "etf_bottom_oversold", description: "ETF抄底-超跌与价格偏离", category: "etf_bottom", feature_columns: ["drawdown_20d","drawdown_60d","drawdown_120d","rsi_6","rsi_14","rsi_28","rsi_low_days","boll_pct_b","boll_width","ma_disparity_20","ma_disparity_60","ma_disparity_120","close_to_low_20d","std_20d","atr_14","atr_ratio_20","amplitude_5d","max_dd_duration","price_position_250d","momentum_3d","momentum_5d","consecutive_down_days"] },
    { id: "etf_bottom_volume_flow", name: "etf_bottom_volume_flow", description: "ETF抄底-量价与资金流向", category: "etf_bottom", feature_columns: ["volume_shrink_5d","volume_shrink_20d","volume_ratio_5d","vol_decline_corr","vol_spike_count","volume_dry_up","turnover_rate","turnover_change_5d","amount_change_5d","obv_divergence","share_change_5d","share_change_20d","north_flow_5d","north_flow_20d","vwap_distance","pct_chg_abs_mean_5d","fund_flow_score","high_vol_days_5d"] },
    { id: "etf_bottom_valuation", name: "etf_bottom_valuation", description: "ETF抄底-估值与安全边际", category: "etf_bottom", feature_columns: ["pe_ttm","pb","pe_percentile_5y","pb_percentile_5y","pe_percentile_1y","pb_percentile_1y","pe_zscore","pb_zscore","erp","erp_percentile_5y","dyr","total_mv_log","turnover_rate_idx","fund_size_change_20d","m_fee","fund_age_days"] },
    { id: "etf_bottom_market_regime", name: "etf_bottom_market_regime", description: "ETF抄底-市场状态与情绪", category: "etf_bottom", feature_columns: ["market_regime","breadth_ratio","breadth_ma5","breadth_ma20","breadth_extreme","ma_regime_index","index_ma_disparity","index_drawdown_60d","index_volatility","index_momentum_20d","sector_rank","sector_flow_5d","trend_strength","momentum_score","volatility_pct","hma"] },
  ];
  loading.value = false;
}

function handleChange(values: string[]) {
  selectedIds.value = values;
  emit("update:modelValue", values);
}

onMounted(loadFeatureSets);
</script>

<template>
  <div class="feature-set-selector">
    <n-select
      v-model:value="selectedIds"
      :options="options"
      :loading="loading"
      placeholder="选择特征集（可选）"
      style="min-width: 240px"
      size="small"
      multiple
      :max-tag-count="2"
      @update:value="handleChange"
    />

    <div v-if="activeSet" class="feature-preview">
      <n-text depth="3" style="font-size: 12px">
        {{ activeSet.description || activeSet.name }}
        <n-tag size="tiny" :bordered="false">
          {{ activeSet.feature_columns?.length || 0 }} 个因子
        </n-tag>
      </n-text>
    </div>
  </div>
</template>

<style scoped>
.feature-set-selector {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.feature-preview {
  padding-left: 4px;
}
</style>
