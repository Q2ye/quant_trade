<!--订单表单-->
<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { NInput, NInputNumber, NSelect, NButton } from "naive-ui";
import { Icon } from "@iconify/vue";
import { useMessage } from "naive-ui";

interface Stock {
  symbol: string;
  name: string;
  price: number;
  change: number;
}

const props = defineProps<{
  initialSymbol?: string;
  initialSide?: "buy" | "sell";
}>();

const emit = defineEmits<{
  previewOrder: [order: any];
}>();

const message = useMessage();

const symbol = ref("");
const currentStock = ref<Stock | null>(null);
const direction = ref<"buy" | "sell">("buy");

const orderType = ref<"limit" | "market" | "stop" | "stop_limit">("limit");
const price = ref(0);
const quantity = ref(100);
const triggerPrice = ref(0);

const allStocks: Stock[] = [
  { symbol: "600519.SH", name: "贵州茅台", price: 1685.5, change: 1.25 },
  { symbol: "601318.SH", name: "中国平安", price: 48.25, change: -0.52 },
  { symbol: "600036.SH", name: "招商银行", price: 32.6, change: 0.92 },
  { symbol: "000333.SZ", name: "美的集团", price: 55.8, change: 2.1 },
  { symbol: "601888.SH", name: "中国中免", price: 102.4, change: -1.3 },
];

const orderTypeOptions = [
  { value: "limit", label: "限价单" },
  { value: "market", label: "市价单" },
  { value: "stop", label: "止损单" },
  { value: "stop_limit", label: "止损限价单" },
];

const orderAmount = computed(() => {
  if (!price.value || !quantity.value) return 0;
  return price.value * quantity.value;
});

const getOrderTypeName = (type: string) => {
  const names: Record<string, string> = {
    limit: "限价单",
    market: "市价单",
    stop: "止损单",
    stop_limit: "止损限价单",
  };
  return names[type] || type;
};

const searchStock = () => {
  if (!symbol.value) {
    currentStock.value = null;
    return;
  }
  const stock = allStocks.find(
    (s) => s.symbol.toLowerCase() === symbol.value.toLowerCase(),
  );
  if (stock) {
    currentStock.value = stock;
    if (orderType.value !== "market" && !price.value) {
      price.value = stock.price;
    }
  } else {
    currentStock.value = null;
  }
};

// Auto-fill from parent (cross-page linking: Workspace → Dashboard)
watch(
  () => props.initialSymbol,
  (val) => {
    if (val) {
      symbol.value = val;
      searchStock();
    }
  },
  { immediate: true },
);
watch(
  () => props.initialSide,
  (val) => {
    if (val) direction.value = val;
  },
  { immediate: true },
);

watch(orderType, (newVal) => {
  if (newVal === "market") {
    price.value = 0;
  } else if (!price.value && currentStock.value) {
    price.value = currentStock.value.price;
  }
});

watch(symbol, (newVal) => {
  if (!newVal) currentStock.value = null;
});

const resetForm = () => {
  symbol.value = "";
  currentStock.value = null;
  direction.value = "buy";
  orderType.value = "limit";
  price.value = 0;
  quantity.value = 100;
  triggerPrice.value = 0;
};

const validateForm = (): boolean => {
  if (!symbol.value || !currentStock.value) {
    message.error("请选择有效的股票");
    return false;
  }
  if (orderType.value !== "market" && !price.value) {
    message.error("请输入价格");
    return false;
  }
  if (!quantity.value || quantity.value <= 0) {
    message.error("请输入有效的数量");
    return false;
  }
  if (
    (orderType.value === "stop" || orderType.value === "stop_limit") &&
    !triggerPrice.value
  ) {
    message.error("请输入触发价格");
    return false;
  }
  return true;
};

const previewOrder = () => {
  if (!validateForm()) return;
  const orderDetails: any = {
    symbol: symbol.value,
    name: currentStock.value!.name,
    direction: direction.value === "buy" ? "买入" : "卖出",
    type: getOrderTypeName(orderType.value),
    price: orderType.value === "market" ? "市价" : price.value,
    quantity: quantity.value,
    amount: orderAmount.value,
  };
  if (orderType.value === "stop" || orderType.value === "stop_limit") {
    orderDetails.triggerPrice = triggerPrice.value;
  }
  emit("previewOrder", orderDetails);
};

const submitOrder = () => {
  if (!validateForm()) return;
  message.success("订单提交成功");
  resetForm();
};
</script>

<template>
  <div class="order-form">
    <h2><Icon icon="ant-design:file-text-outlined" /> 交易订单</h2>

    <div class="form-container">
      <div class="form-group">
        <label>证券代码</label>
        <div class="symbol-input">
          <n-input
            v-model:value="symbol"
            placeholder="输入股票代码"
            @input="searchStock"
          />
          <div v-if="currentStock" class="stock-info">
            <span class="name">{{ currentStock.name }}</span>
            <span class="price">{{ currentStock.price }}</span>
            <span
              class="change"
              :class="currentStock.change >= 0 ? 'positive' : 'negative'"
            >
              {{ currentStock.change >= 0 ? "+" : ""
              }}{{ currentStock.change }}%
            </span>
          </div>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>交易方向</label>
          <div class="direction-buttons">
            <n-button
              :type="direction === 'buy' ? 'success' : 'default'"
              @click="direction = 'buy'"
            >
              <template #icon
                ><Icon icon="ant-design:arrow-up-outlined"
              /></template>
              买入
            </n-button>
            <n-button
              :type="direction === 'sell' ? 'error' : 'default'"
              @click="direction = 'sell'"
            >
              <template #icon
                ><Icon icon="ant-design:arrow-down-outlined"
              /></template>
              卖出
            </n-button>
          </div>
        </div>

        <div class="form-group">
          <label>订单类型</label>
          <n-select v-model:value="orderType" :options="orderTypeOptions" />
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label>价格</label>
          <n-input-number
            v-model:value="price"
            :disabled="orderType === 'market'"
            :step="0.01"
            :min="0"
          />
        </div>

        <div class="form-group">
          <label>数量</label>
          <n-input-number v-model:value="quantity" :min="100" :step="100" />
        </div>
      </div>

      <div
        v-if="orderType === 'stop' || orderType === 'stop_limit'"
        class="form-group"
      >
        <label>触发价格</label>
        <n-input-number v-model:value="triggerPrice" :step="0.01" :min="0" />
      </div>

      <div class="form-group">
        <label>交易金额</label>
        <div class="amount-display">¥{{ orderAmount.toLocaleString() }}</div>
      </div>

      <div class="form-actions">
        <n-button type="error" @click="resetForm">
          <template #icon><Icon icon="ant-design:redo-outlined" /></template>
          重置
        </n-button>
        <n-button type="warning" @click="previewOrder">
          <template #icon><Icon icon="ant-design:eye-outlined" /></template>
          预览订单
        </n-button>
        <n-button type="success" @click="submitOrder">
          <template #icon><Icon icon="ant-design:send-outlined" /></template>
          提交订单
        </n-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.order-form {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  height: 100%;
}

h2 {
  font-size: 1.5rem;
  color: #64b5f6;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label {
  color: #a8c7ff;
  font-size: 0.95rem;
}

.symbol-input {
  position: relative;
}

.stock-info {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.9rem;
  pointer-events: none;
}

.stock-info .name {
  color: #a8c7ff;
}

.stock-info .price {
  font-weight: 500;
  color: #e0e7ff;
}

.stock-info .change {
  font-weight: 500;
}

.stock-info .positive {
  color: #5cdd8b;
}

.stock-info .negative {
  color: #ff6b6b;
}

.direction-buttons {
  display: flex;
  gap: 10px;
}

.direction-buttons .n-button {
  flex: 1;
}

.amount-display {
  padding: 10px 12px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  font-size: 1.1rem;
  font-weight: 600;
  color: #64b5f6;
}

.form-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.form-actions .n-button {
  width: 100%;
}
</style>
