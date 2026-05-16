<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { NButton, NButtonGroup, NInputNumber } from "naive-ui";
import { useTrade } from "@/composables/useTrade";
import { useStore } from "vuex";

interface Props {
  symbol?: string;
  defaultVolume?: number;
  showMarketOrder?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  defaultVolume: 100,
  showMarketOrder: true,
});

const emit = defineEmits<{
  orderPlaced: [orderId: string];
  orderCancelled: [orderId: string];
}>();

const store = useStore();
const { quickOrder, marketOrder, limitOrder, estimateFees, isTrading } =
  useTrade();

const orderType = ref<"market" | "limit">("limit");
const direction = ref<"buy" | "sell">("buy");
const price = ref<number>(0);
const volume = ref<number>(props.defaultVolume);
const isSubmitting = ref(false);

const currentPrice = computed(() => {
  if (props.symbol) {
    return store.getters["market/getCurrentPrice"](props.symbol);
  }
  return 0;
});

const availableCash = computed(() => {
  return store.getters["trade/getAvailableCash"];
});

const availablePosition = computed(() => {
  if (props.symbol && direction.value === "sell") {
    const position = store.getters["trade/getPosition"](props.symbol);
    return position ? position.available_volume : 0;
  }
  return 0;
});

const estimatedFees = computed(() => {
  if (!price.value || !volume.value) return null;
  return estimateFees(
    price.value || currentPrice.value,
    volume.value,
    direction.value,
  );
});

const totalAmount = computed(() => {
  const p = orderType.value === "market" ? currentPrice.value : price.value;
  return p * volume.value;
});

const priceStep = computed(() => {
  const p = currentPrice.value;
  if (p < 2) return 0.01;
  if (p < 5) return 0.02;
  if (p < 10) return 0.05;
  if (p < 20) return 0.1;
  if (p < 50) return 0.2;
  if (p < 100) return 0.5;
  return 1;
});

const volumeStep = computed(() => 100);

const changePrice = (delta: number) => {
  const step = priceStep.value;
  price.value = Math.max(0, price.value + delta * step);
};

const changeVolume = (delta: number) => {
  const step = volumeStep.value;
  volume.value = Math.max(step, volume.value + delta * step);
};

const setVolumePercent = (percent: number) => {
  if (direction.value === "buy") {
    const maxVolume = Math.floor(
      availableCash.value / (price.value || currentPrice.value),
    );
    volume.value = Math.floor((maxVolume * percent) / 100);
  } else {
    volume.value = Math.floor((availablePosition.value * percent) / 100);
  }
  volume.value = Math.max(volumeStep.value, volume.value);
};

const submitOrder = async () => {
  if (!props.symbol) {
    alert("请选择交易标的");
    return;
  }

  if (isSubmitting.value) return;

  isSubmitting.value = true;

  try {
    let orderId: string;

    if (orderType.value === "market") {
      orderId = await marketOrder(props.symbol, direction.value, volume.value);
    } else {
      if (!price.value || price.value <= 0) {
        alert("请输入有效的价格");
        return;
      }
      orderId = await limitOrder(
        props.symbol,
        direction.value,
        price.value,
        volume.value,
      );
    }

    emit("orderPlaced", orderId);

    volume.value = props.defaultVolume;
    if (orderType.value === "limit") {
      price.value = currentPrice.value;
    }

    store.dispatch("ui/showMessage", {
      type: "success",
      message: `订单提交成功 (${orderId})`,
    });
  } catch (error: any) {
    store.dispatch("ui/showMessage", {
      type: "error",
      message: `下单失败: ${error.message}`,
    });
  } finally {
    isSubmitting.value = false;
  }
};

watch(
  () => props.symbol,
  (newSymbol) => {
    if (newSymbol) {
      price.value = currentPrice.value;
    }
  },
  { immediate: true },
);

watch(direction, () => {
  volume.value = props.defaultVolume;
});
</script>

<template>
  <div class="quick-order-panel">
    <div class="panel-header">
      <h3>快速交易</h3>
      <span v-if="symbol" class="symbol">{{ symbol }}</span>
    </div>

    <div class="order-form">
      <div class="form-group">
        <label>订单类型</label>
        <n-button-group>
          <n-button
            :type="orderType === 'limit' ? 'primary' : 'default'"
            @click="orderType = 'limit'"
          >
            限价单
          </n-button>
          <n-button
            v-if="showMarketOrder"
            :type="orderType === 'market' ? 'primary' : 'default'"
            @click="orderType = 'market'"
          >
            市价单
          </n-button>
        </n-button-group>
      </div>

      <div class="form-group">
        <label>方向</label>
        <n-button-group>
          <n-button
            :type="direction === 'buy' ? 'success' : 'default'"
            @click="direction = 'buy'"
          >
            买入
          </n-button>
          <n-button
            :type="direction === 'sell' ? 'error' : 'default'"
            @click="direction = 'sell'"
          >
            卖出
          </n-button>
        </n-button-group>
      </div>

      <div v-if="orderType === 'limit'" class="form-group">
        <label>价格</label>
        <div class="input-with-buttons">
          <n-input-number
            v-model:value="price"
            :step="priceStep"
            :min="0"
          />
          <div class="adjust-buttons">
            <n-button size="tiny" @click="changePrice(1)">+</n-button>
            <n-button size="tiny" @click="changePrice(-1)">-</n-button>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>数量 (股)</label>
        <div class="input-with-buttons">
          <n-input-number
            v-model:value="volume"
            :step="volumeStep"
            :min="0"
          />
          <div class="adjust-buttons">
            <n-button size="tiny" @click="changeVolume(1)">+</n-button>
            <n-button size="tiny" @click="changeVolume(-1)">-</n-button>
          </div>
        </div>
        <div class="quick-percent">
          <n-button size="tiny" @click="setVolumePercent(25)">25%</n-button>
          <n-button size="tiny" @click="setVolumePercent(50)">50%</n-button>
          <n-button size="tiny" @click="setVolumePercent(75)">75%</n-button>
          <n-button size="tiny" @click="setVolumePercent(100)">100%</n-button>
        </div>
      </div>

      <div v-if="estimatedFees" class="fee-estimation">
        <div class="fee-item">
          <span>佣金:</span>
          <span>¥{{ estimatedFees.commission.toFixed(2) }}</span>
        </div>
        <div v-if="direction === 'sell'" class="fee-item">
          <span>印花税:</span>
          <span>¥{{ estimatedFees.tax.toFixed(2) }}</span>
        </div>
        <div class="fee-item">
          <span>总费用:</span>
          <span>¥{{ estimatedFees.total.toFixed(2) }}</span>
        </div>
        <div class="fee-item total">
          <span>净金额:</span>
          <span>¥{{ estimatedFees.netAmount.toFixed(2) }}</span>
        </div>
      </div>

      <n-button
        class="submit-button"
        :type="direction === 'buy' ? 'success' : 'error'"
        block
        :loading="isSubmitting"
        :disabled="isSubmitting || !symbol"
        @click="submitOrder"
      >
        {{ direction === "buy" ? "买入" : "卖出" }} {{ symbol || "" }}
      </n-button>

      <div class="balance-info">
        <div v-if="direction === 'buy'">
          可用资金: ¥{{ availableCash.toFixed(2) }}
        </div>
        <div v-else>可用持仓: {{ availablePosition }} 股</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quick-order-panel {
  background: var(--bg-color-secondary);
  border-radius: 8px;
  padding: 16px;
  min-width: 300px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-color-primary);
}

.symbol {
  font-size: 14px;
  color: var(--text-color-secondary);
  font-weight: bold;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-color-secondary);
}

.input-with-buttons {
  display: flex;
  gap: 8px;
}

.input-with-buttons > :first-child {
  flex: 1;
}

.adjust-buttons {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quick-percent {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}

.quick-percent .n-button {
  flex: 1;
}

.fee-estimation {
  margin: 16px 0;
  padding: 12px;
  background: var(--bg-color);
  border-radius: 4px;
  font-size: 12px;
}

.fee-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.fee-item.total {
  border-top: 1px solid var(--border-color);
  padding-top: 4px;
  font-weight: bold;
  color: var(--text-color-primary);
}

.submit-button {
  width: 100%;
}

.balance-info {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-color-secondary);
  text-align: center;
}
</style>
