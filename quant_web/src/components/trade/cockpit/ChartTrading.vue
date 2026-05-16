<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import {
  NCard,
  NRadioGroup,
  NRadioButton,
  NInputNumber,
  NButton,
} from "naive-ui";
import { useChart } from "@/composables/useChart";
import { useMessage } from "naive-ui";
import { useStore } from "vuex";

const message = useMessage();
const store = useStore();

const tradeConfig = reactive({
  symbol: "000001.SZ",
  quantity: 100,
  priceType: "limit",
  limitPrice: 0,
  orderType: "buy",
});

const klineData = ref<any[]>([]);
const currentPrice = ref(0);
const chartRef = ref<HTMLDivElement>();

const initKLineChart = () => {
  if (!chartRef.value) return;

  const data = generateKLineData();
  klineData.value = data;
  currentPrice.value = data[data.length - 1].close;

  const { initChart } = useChart();
const chart = initChart(chartRef.value);
if (!chart) return;
chart.setOption({
    title: { text: `${tradeConfig.symbol} K线图` },
    tooltip: { trigger: "axis" },
    xAxis: { type: "time" },
    yAxis: { type: "value", scale: true },
    dataZoom: [
      { type: "inside", xAxisIndex: 0 },
      { type: "slider", xAxisIndex: 0 },
    ],
    series: [
      {
        type: "candlestick",
        data: data.map((item) => [item.open, item.close, item.low, item.high]),
        itemStyle: {
          color: "#ec0000",
          color0: "#00da3c",
          borderColor: "#ec0000",
          borderColor0: "#00da3c",
        },
      },
    ],
  });

  chart.on("click", (params: any) => {
    if (
      params.componentType === "series" &&
      params.seriesType === "candlestick"
    ) {
      tradeConfig.limitPrice = params.data[3];
    }
  });
};

const generateKLineData = () => {
  const data = [];
  const basePrice = 100;
  const baseTime = new Date("2023-01-01").getTime();

  for (let i = 0; i < 100; i++) {
    const open = basePrice + Math.random() * 10;
    const close = open + (Math.random() - 0.5) * 5;
    const high = Math.max(open, close) + Math.random() * 3;
    const low = Math.min(open, close) - Math.random() * 3;
    const time = baseTime + i * 24 * 60 * 60 * 1000;
    data.push({ time, open, close, high, low });
  }

  return data;
};

const quickOrder = (direction: "buy" | "sell") => {
  tradeConfig.orderType = direction;
  if (tradeConfig.priceType === "market") {
    tradeConfig.limitPrice = currentPrice.value;
  }
  submitOrder();
};

const submitOrder = async () => {
  try {
    const order = {
      symbol: tradeConfig.symbol,
      quantity: tradeConfig.quantity,
      price:
        tradeConfig.priceType === "market" ? undefined : tradeConfig.limitPrice,
      direction: tradeConfig.orderType,
      priceType: tradeConfig.priceType,
    };
    await store.dispatch("market/submitOrder", order);
    message.success("订单提交成功");
  } catch (error) {
    message.error("订单提交失败");
  }
};

const priceChange = computed(() => {
  if (klineData.value.length < 2) return 0;
  const current = klineData.value[klineData.value.length - 1].close;
  const previous = klineData.value[klineData.value.length - 2].close;
  return ((current - previous) / previous) * 100;
});

onMounted(() => {
  initKLineChart();
});
</script>

<template>
  <div class="chart-trading">
    <div class="trading-header">
      <h3>图表联动交易</h3>
      <div class="symbol-info">
        <span class="symbol">{{ tradeConfig.symbol }}</span>
        <span
          class="price"
          :class="{ up: priceChange > 0, down: priceChange < 0 }"
        >
          {{ currentPrice.toFixed(2) }}
          <span class="change">({{ priceChange.toFixed(2) }}%)</span>
        </span>
      </div>
    </div>

    <div class="trading-layout">
      <div class="chart-section">
        <div ref="chartRef" class="kline-chart"></div>
      </div>

      <div class="trade-panel">
        <NCard class="trade-card">
          <template #header>
            <span>快速交易</span>
          </template>

          <div class="trade-direction">
            <NRadioGroup
              :value="tradeConfig.orderType"
              @update:value="(v: string) => (tradeConfig.orderType = v)"
            >
              <NRadioButton value="buy">买入</NRadioButton>
              <NRadioButton value="sell">卖出</NRadioButton>
            </NRadioGroup>
          </div>

          <div class="price-type">
            <NRadioGroup
              :value="tradeConfig.priceType"
              @update:value="(v: string) => (tradeConfig.priceType = v)"
            >
              <NRadioButton value="limit">限价</NRadioButton>
              <NRadioButton value="market">市价</NRadioButton>
            </NRadioGroup>
          </div>

          <div v-if="tradeConfig.priceType === 'limit'" class="price-input">
            <NInputNumber
              v-model:value="tradeConfig.limitPrice"
              :min="0"
              :step="0.01"
              placeholder="委托价格"
            />
          </div>

          <div class="quantity-input">
            <NInputNumber
              v-model:value="tradeConfig.quantity"
              :min="100"
              :step="100"
              placeholder="委托数量"
            />
            <span class="unit">股</span>
          </div>

          <div class="quick-buttons">
            <NButton
              type="success"
              size="large"
              @click="quickOrder('buy')"
              class="buy-button"
            >
              快速买入
            </NButton>
            <NButton
              type="error"
              size="large"
              @click="quickOrder('sell')"
              class="sell-button"
            >
              快速卖出
            </NButton>
          </div>

          <div class="order-info">
            <div class="info-item">
              <span>预估金额:</span>
              <span class="amount">
                {{
                  (
                    tradeConfig.quantity *
                    (tradeConfig.limitPrice || currentPrice)
                  ).toFixed(2)
                }}
                元
              </span>
            </div>
            <div class="info-item">
              <span>手续费:</span>
              <span class="fee">~5.00 元</span>
            </div>
          </div>
        </NCard>
      </div>
    </div>

    <div class="indicators-panel">
      <h4>技术指标</h4>
      <div class="indicators-grid">
        <div class="indicator-item">
          <span class="label">MA5</span>
          <span class="value">12.34</span>
        </div>
        <div class="indicator-item">
          <span class="label">MA10</span>
          <span class="value">12.56</span>
        </div>
        <div class="indicator-item">
          <span class="label">RSI</span>
          <span class="value">45.67</span>
        </div>
        <div class="indicator-item">
          <span class="label">MACD</span>
          <span class="value">0.12</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-trading {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--n-body-color);
}

.trading-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.symbol-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.symbol {
  font-weight: bold;
  font-size: 16px;
}

.price {
  font-size: 18px;
  font-weight: bold;
}

.price.up {
  color: #f56c6c;
}
.price.down {
  color: #67c23a;
}

.change {
  font-size: 14px;
  font-weight: normal;
}

.trading-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
  padding: 16px;
  min-height: 0;
}

.chart-section {
  background: var(--n-color-embedded);
  border-radius: 6px;
  overflow: hidden;
}

.kline-chart {
  height: 100%;
  min-height: 500px;
}

.trade-panel {
  display: flex;
  flex-direction: column;
}

.trade-card {
  height: 100%;
}

.trade-direction,
.price-type {
  margin-bottom: 16px;
  text-align: center;
}

.price-input,
.quantity-input {
  margin-bottom: 16px;
}

.quantity-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit {
  color: var(--n-text-color-3);
}

.quick-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 20px 0;
}

.buy-button,
.sell-button {
  width: 100%;
  height: 40px;
}

.order-info {
  border-top: 1px solid var(--n-border-color);
  padding-top: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.amount,
.fee {
  font-weight: bold;
}

.indicators-panel {
  padding: 16px;
  border-top: 1px solid var(--n-border-color);
}

.indicators-panel h4 {
  margin: 0 0 12px 0;
}

.indicators-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.indicator-item {
  background: var(--n-color-embedded);
  padding: 8px 12px;
  border-radius: 4px;
  text-align: center;
}

.indicator-item .label {
  display: block;
  font-size: 12px;
  color: var(--n-text-color-3);
}

.indicator-item .value {
  display: block;
  font-size: 14px;
  font-weight: bold;
}

@media (max-width: 768px) {
  .trading-layout {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }
  .indicators-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
