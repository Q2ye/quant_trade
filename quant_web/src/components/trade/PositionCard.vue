<!--持仓卡片-->
<script setup lang="ts">
import { NCard, NButton, NButtonGroup } from "naive-ui";
import { Icon } from "@iconify/vue";

const props = defineProps<{
  position: {
    symbol: string;
    name: string;
    quantity: number;
    available: number;
    costPrice: number;
    currentPrice: number;
    change: number;
    marketValue: number;
    profit: number;
    profitRatio: number;
  };
}>();

const emit = defineEmits<{
  "trade-position": [payload: { symbol: string; direction: string }];
  "close-position": [symbol: string];
}>();

const tradePosition = (direction: string) => {
  emit("trade-position", {
    symbol: props.position.symbol,
    direction,
  });
};

const closePosition = () => {
  emit("close-position", props.position.symbol);
};
</script>

<template>
  <n-card
    :class="{ 'high-value': position.marketValue > 100000 }"
    class="position-card"
  >
    <template #header>
      <div class="symbol">{{ position.symbol }}</div>
      <div class="name">{{ position.name }}</div>
    </template>

    <div class="card-content">
      <div class="position-data">
        <div class="data-item">
          <div class="label">持仓数量</div>
          <div class="value">{{ position.quantity.toLocaleString() }}</div>
        </div>
        <div class="data-item">
          <div class="label">可用数量</div>
          <div class="value">{{ position.available.toLocaleString() }}</div>
        </div>
      </div>

      <div class="position-data">
        <div class="data-item">
          <div class="label">成本价</div>
          <div class="value">¥{{ position.costPrice.toFixed(2) }}</div>
        </div>
        <div class="data-item">
          <div class="label">当前价</div>
          <div class="value">¥{{ position.currentPrice.toFixed(2) }}</div>
        </div>
      </div>

      <div class="position-data">
        <div class="data-item">
          <div class="label">涨跌幅</div>
          <div
            class="value"
            :class="position.change >= 0 ? 'positive' : 'negative'"
          >
            {{ position.change >= 0 ? "+" : ""
            }}{{ position.change.toFixed(2) }}%
          </div>
        </div>
        <div class="data-item">
          <div class="label">持仓价值</div>
          <div class="value">¥{{ position.marketValue.toLocaleString() }}</div>
        </div>
      </div>

      <div class="position-data">
        <div class="data-item">
          <div class="label">浮动盈亏</div>
          <div
            class="value"
            :class="position.profit >= 0 ? 'positive' : 'negative'"
          >
            {{ position.profit >= 0 ? "+" : "" }}¥{{
              position.profit.toLocaleString()
            }}
          </div>
        </div>
        <div class="data-item">
          <div class="label">盈亏比例</div>
          <div
            class="value"
            :class="position.profitRatio >= 0 ? 'positive' : 'negative'"
          >
            {{ position.profitRatio >= 0 ? "+" : ""
            }}{{ position.profitRatio.toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <n-button-group>
        <n-button type="success" size="small" @click="tradePosition('buy')">
          <template #icon><Icon icon="ant-design:plus-outlined" /></template>
          加仓
        </n-button>
        <n-button type="error" size="small" @click="tradePosition('sell')">
          <template #icon><Icon icon="ant-design:minus-outlined" /></template>
          减仓
        </n-button>
        <n-button type="warning" size="small" @click="closePosition">
          <template #icon><Icon icon="ant-design:close-outlined" /></template>
          平仓
        </n-button>
      </n-button-group>
    </template>
  </n-card>
</template>

<style scoped>
.position-card {
  transition: all 0.3s;
  position: relative;
}

.position-card.high-value::before {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  border-width: 0 25px 25px 0;
  border-style: solid;
  border-color: transparent #ffb86c transparent transparent;
}

.position-card.high-value::after {
  content: "VIP";
  position: absolute;
  top: 2px;
  right: 2px;
  font-size: 10px;
  font-weight: bold;
  color: #1a2a4c;
  transform: rotate(45deg);
  width: 25px;
  text-align: center;
}

.position-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.symbol {
  font-size: 1.2rem;
  font-weight: 600;
  color: #64b5f6;
}

.name {
  font-size: 0.9rem;
  color: #a8c7ff;
}

.position-data {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.data-item {
  background: rgba(16, 33, 59, 0.7);
  border-radius: 6px;
  padding: 8px;
}

.label {
  font-size: 0.8rem;
  color: #a8c7ff;
  margin-bottom: 3px;
}

.value {
  font-size: 0.95rem;
  font-weight: 500;
}

.positive {
  color: #5cdd8b;
}
.negative {
  color: #ff6b6b;
}
</style>
