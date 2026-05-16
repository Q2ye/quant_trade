<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from "vue";
import { useChart } from "@/composables/useChart";
import { useWebSocket } from "@/composables/useWebSocket";

interface DepthData {
  price: number;
  volume: number;
  total: number;
  type: "bid" | "ask";
}

interface Props {
  symbol: string;
  height?: number;
  showVolume?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  height: 300,
  showVolume: true,
});

const { initChart, setChartOption, resizeChart, disposeChart } = useChart();
const { subscribe, unsubscribe, isConnected } = useWebSocket();

const chartEl = ref<HTMLElement>();
const depthData = ref<{ bids: DepthData[]; asks: DepthData[] }>({
  bids: [],
  asks: [],
});
const maxVolume = ref(0);

// 初始化深度图
const initDepthChart = () => {
  if (!chartEl.value) return;

  const chart = initChart(chartEl.value, {
    theme: "dark",
    renderer: "canvas",
  });

  updateChart();
};

// 更新图表
const updateChart = () => {
  const option = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "line",
        lineStyle: {
          color: "rgba(255,255,255,0.2)",
        },
      },
      formatter: (params: any) => {
        const data = params[0].data;
        return `
          <div style="text-align: left;">
            <div>价格: ${data[0]}</div>
            <div>数量: ${data[1]}</div>
            <div>累计: ${data[2]}</div>
          </div>
        `;
      },
    },
    grid: {
      left: "3%",
      right: "3%",
      bottom: "3%",
      top: "3%",
      containLabel: true,
    },
    xAxis: {
      type: "value",
      position: "top",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: "#999",
        formatter: (value: number) => value.toFixed(2),
      },
      splitLine: {
        lineStyle: {
          color: "rgba(255,255,255,0.1)",
        },
      },
    },
    yAxis: {
      type: "value",
      inverse: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
    series: [
      // 买盘深度
      {
        name: "买盘",
        type: "bar",
        data: depthData.value.bids.map((item) => [
          item.price,
          item.volume,
          item.total,
        ]),
        itemStyle: {
          color: "#00b36a",
        },
        emphasis: {
          itemStyle: {
            color: "#00d97e",
          },
        },
        barWidth: "80%",
      },
      // 卖盘深度
      {
        name: "卖盘",
        type: "bar",
        data: depthData.value.asks.map((item) => [
          item.price,
          item.volume,
          item.total,
        ]),
        itemStyle: {
          color: "#ff4d4d",
        },
        emphasis: {
          itemStyle: {
            color: "#ff6666",
          },
        },
        barWidth: "80%",
      },
    ],
  };

  setChartOption(option);
};

// 处理深度数据更新
const handleDepthUpdate = (data: any) => {
  if (data.symbol !== props.symbol) return;

  // 处理买盘数据
  const bids = data.bids.map((bid: [number, number], index: number) => {
    const total = data.bids
      .slice(0, index + 1)
      .reduce((sum: number, b: [number, number]) => sum + b[1], 0);
    return {
      price: bid[0],
      volume: bid[1],
      total,
      type: "bid" as const,
    };
  });

  // 处理卖盘数据
  const asks = data.asks.map((ask: [number, number], index: number) => {
    const total = data.asks
      .slice(0, index + 1)
      .reduce((sum: number, a: [number, number]) => sum + a[1], 0);
    return {
      price: ask[0],
      volume: ask[1],
      total,
      type: "ask" as const,
    };
  });

  depthData.value = { bids, asks };
  maxVolume.value = Math.max(
    ...bids.map((b: any) => b.total),
    ...asks.map((a: any) => a.total),
  );

  updateChart();
};

// 订阅深度数据
watch(
  () => props.symbol,
  (newSymbol, oldSymbol) => {
    if (oldSymbol) {
      unsubscribe([`depth_${oldSymbol}`]);
    }

    if (newSymbol && isConnected.value) {
      subscribe([`depth_${newSymbol}`]);
    }
  },
);

watch(isConnected, (connected) => {
  if (connected && props.symbol) {
    subscribe([`depth_${props.symbol}`]);
  }
});

onMounted(() => {
  initDepthChart();

  if (isConnected.value && props.symbol) {
    subscribe([`depth_${props.symbol}`]);
  }
});

onUnmounted(() => {
  if (props.symbol) {
    unsubscribe([`depth_${props.symbol}`]);
  }
  disposeChart();
});

// 响应式调整
const handleResize = () => {
  resizeChart();
};

defineExpose({
  handleResize,
});
</script>

<template>
  <div class="depth-chart">
    <div class="chart-header">
      <h3>买卖深度图 - {{ symbol }}</h3>
      <div class="legend">
        <span class="bid-legend">
          <span class="color-indicator bid"></span>
          买盘
        </span>
        <span class="ask-legend">
          <span class="color-indicator ask"></span>
          卖盘
        </span>
      </div>
    </div>

    <div class="chart-container">
      <div ref="chartEl" :style="{ height: `${height}px` }"></div>
    </div>

    <div
      class="depth-info"
      v-if="depthData.bids.length > 0 && depthData.asks.length > 0"
    >
      <div class="info-row">
        <span
          >买一: {{ depthData.bids[0]?.price.toFixed(2) }} ({{
            depthData.bids[0]?.volume
          }})</span
        >
        <span
          >卖一: {{ depthData.asks[0]?.price.toFixed(2) }} ({{
            depthData.asks[0]?.volume
          }})</span
        >
      </div>
      <div class="info-row">
        <span
          >价差:
          {{
            (depthData.asks[0]?.price - depthData.bids[0]?.price).toFixed(2)
          }}</span
        >
        <span
          >深度比例:
          {{
            (depthData.bids[0]?.volume / depthData.asks[0]?.volume).toFixed(2)
          }}</span
        >
      </div>
    </div>
  </div>
</template>

<style scoped>
.depth-chart {
  background: var(--bg-color-secondary);
  border-radius: 8px;
  padding: 16px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.chart-header h3 {
  margin: 0;
  font-size: 14px;
  color: var(--text-color-primary);
}

.legend {
  display: flex;
  gap: 16px;
}

.color-indicator {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
  margin-right: 4px;
}

.color-indicator.bid {
  background: #00b36a;
}

.color-indicator.ask {
  background: #ff4d4d;
}

.chart-container {
  position: relative;
}

.depth-info {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-color-secondary);
  margin-bottom: 4px;
}
</style>
