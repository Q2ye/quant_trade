<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { NCard, NTag, NButton, NSkeleton, NEmpty } from "naive-ui";
import * as echarts from "echarts";
import SmartIcon from "@/components/common/SmartIcon.vue";
import type { Position, Order, Basket } from "@/types";

const props = defineProps<{
  tsCode: string | null;
  stockName: string;
  currentPrice: number | null;
  changePercent: number | null;
  position: Position | null;
  relatedOrders: Order[];
  relatedBaskets: Basket[];
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: "trade", direction: "buy" | "sell"): void;
  (e: "add-to-basket"): void;
  (e: "navigate-detail"): void;
}>();

const chartRef = ref<HTMLDivElement>();
let chart: echarts.ECharts | null = null;
const chartPeriod = ref<"1D" | "1W" | "1M">("1D");

const pnlColor = computed(() =>
  (props.position?.profit_loss ?? 0) >= 0
    ? "var(--color-stock-up)"
    : "var(--color-stock-down)",
);

const changeColor = computed(() =>
  (props.changePercent ?? 0) >= 0
    ? "var(--color-stock-up)"
    : "var(--color-stock-down)",
);

const initChart = () => {
  if (!chartRef.value || !props.tsCode) return;
  chart?.dispose();

  chart = echarts.init(chartRef.value, "dark");
  chart.setOption({
    grid: { top: 10, right: 8, bottom: 20, left: 42 },
    xAxis: {
      type: "category",
      data: [
        "09:30",
        "10:00",
        "10:30",
        "11:00",
        "11:30",
        "13:30",
        "14:00",
        "14:30",
        "15:00",
      ],
      axisLabel: { fontSize: 10, color: "#666" },
      axisLine: { lineStyle: { color: "#333" } },
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, color: "#666" },
      splitLine: { lineStyle: { color: "rgba(255,255,255,0.04)" } },
    },
    series: [
      {
        type: "line",
        data: [1840, 1845, 1842, 1855, 1852, 1858, 1850, 1848, 1850.5],
        smooth: true,
        showSymbol: false,
        lineStyle: { color: "#448AFF", width: 1.5 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(68,138,255,0.12)" },
            { offset: 1, color: "rgba(68,138,255,0.02)" },
          ]),
        },
      },
    ],
  });
};

watch(
  () => props.tsCode,
  (val) => {
    if (val) setTimeout(initChart, 100);
  },
);

onMounted(() => {
  if (props.tsCode) setTimeout(initChart, 100);
  window.addEventListener("resize", () => chart?.resize());
});

onUnmounted(() => {
  chart?.dispose();
  window.removeEventListener("resize", () => chart?.resize());
});
</script>

<template>
  <div class="stock-context-panel">
    <!-- Empty state -->
    <div v-if="!tsCode" class="panel-empty">
      <n-empty description="点击左侧持仓/订单中的股票查看详情" />
    </div>

    <!-- Loading -->
    <n-skeleton v-else-if="loading" :text="true" :repeat="6" />

    <!-- Data -->
    <template v-else>
      <!-- Header -->
      <div class="panel-header">
        <div class="panel-stock-info">
          <span class="panel-stock-name">{{ stockName || tsCode }}</span>
          <span class="panel-stock-code">{{ tsCode }}</span>
        </div>
        <div
          v-if="currentPrice != null"
          class="panel-price"
          :style="{ color: changeColor }"
        >
          ¥{{ currentPrice.toFixed(2) }}
          <span class="panel-change" :style="{ color: changeColor }">
            {{ (changePercent ?? 0) >= 0 ? "+" : ""
            }}{{ (changePercent ?? 0).toFixed(2) }}%
          </span>
        </div>
      </div>

      <!-- Mini K-line -->
      <div class="mini-chart-section">
        <div class="mini-chart-header">
          <n-tag
            v-for="p in ['1D', '1W', '1M'] as const"
            :key="p"
            size="tiny"
            :type="chartPeriod === p ? 'primary' : 'default'"
            :bordered="false"
            style="cursor: pointer"
            @click="chartPeriod = p"
          >
            {{ p }}
          </n-tag>
        </div>
        <div ref="chartRef" class="mini-chart"></div>
      </div>

      <!-- Position status -->
      <n-card v-if="position" size="small" class="info-card">
        <div class="info-card-title">当前持仓</div>
        <div class="position-stats">
          <div class="ps-item">
            <span class="ps-label">持有</span>
            <span class="ps-value">{{ position.volume }} 股</span>
          </div>
          <div class="ps-item">
            <span class="ps-label">成本</span>
            <span class="ps-value">¥{{ position.cost_price?.toFixed(2) }}</span>
          </div>
          <div class="ps-item">
            <span class="ps-label">浮盈</span>
            <span class="ps-value" :style="{ color: pnlColor }">
              ¥{{ (position.profit_loss ?? 0).toLocaleString() }}
            </span>
          </div>
        </div>
      </n-card>
      <div v-else class="no-position-hint">暂未持有该股票</div>

      <!-- Related orders -->
      <n-card v-if="relatedOrders.length > 0" size="small" class="info-card">
        <div class="info-card-title">关联订单</div>
        <div class="order-list">
          <div
            v-for="o in relatedOrders.slice(0, 5)"
            :key="o.order_id"
            class="order-row"
          >
            <n-tag
              size="tiny"
              :type="o.direction === 'buy' ? 'success' : 'error'"
              :bordered="false"
            >
              {{ o.direction === "buy" ? "买" : "卖" }}
            </n-tag>
            <span class="order-qty">{{ o.volume }}股</span>
            <span class="order-time">{{ o.submitted_at?.slice(11, 16) }}</span>
          </div>
        </div>
      </n-card>

      <!-- Related baskets -->
      <n-card v-if="relatedBaskets.length > 0" size="small" class="info-card">
        <div class="info-card-title">所属篮子</div>
        <div class="basket-tags">
          <n-tag
            v-for="b in relatedBaskets"
            :key="b.id"
            size="small"
            :bordered="false"
          >
            {{ b.name }}
          </n-tag>
        </div>
      </n-card>

      <!-- Quick actions -->
      <div class="quick-actions">
        <n-button type="primary" @click="emit('trade', 'buy')" size="small">
          <template #icon><SmartIcon name="TrendingUp" /></template>
          买入
        </n-button>
        <n-button
          type="error"
          @click="emit('trade', 'sell')"
          size="small"
          :disabled="!position"
        >
          <template #icon><SmartIcon name="TrendingDown" /></template>
          卖出
        </n-button>
        <n-button @click="emit('add-to-basket')" size="small">
          <template #icon><SmartIcon name="Basket" /></template>
          加入篮子
        </n-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stock-context-panel {
  height: 100%;
  overflow-y: auto;
  padding: 4px 0;
}

.panel-empty {
  display: flex;
  justify-content: center;
  padding-top: 80px;
}

.panel-header {
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 12px;
}

.panel-stock-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-stock-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.panel-stock-code {
  font-size: 12px;
  color: var(--n-text-color-3);
  font-family: monospace;
}

.panel-price {
  font-size: 22px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 4px;
}

.panel-change {
  font-size: 13px;
  font-weight: 500;
  margin-left: 6px;
}

.mini-chart-section {
  margin-bottom: 12px;
}

.mini-chart-header {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.mini-chart {
  height: 200px;
  width: 100%;
}

.info-card {
  margin-bottom: 10px;
}

.info-card-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--n-text-color-2);
  margin-bottom: 8px;
}

.position-stats {
  display: flex;
  gap: 0;
}

.ps-item {
  flex: 1;
  text-align: center;
}

.ps-label {
  display: block;
  font-size: 11px;
  color: var(--n-text-color-3);
  margin-bottom: 2px;
}

.ps-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--n-text-color-1);
}

.no-position-hint {
  text-align: center;
  font-size: 12px;
  color: var(--n-text-color-3);
  padding: 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  margin-bottom: 10px;
}

.order-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.order-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.order-qty {
  color: var(--n-text-color-1);
}

.order-time {
  margin-left: auto;
  color: var(--n-text-color-3);
  font-family: monospace;
}

.basket-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
</style>
