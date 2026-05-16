<template>
  <div class="trade-execution bg-gradient-mesh bg-noise">
    <h2>交易执行</h2>

    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-card class="execution-card">
          <template #header>
            <div class="card-header">
              <span>交易信号</span>
              <n-button text @click="refreshSignals">刷新</n-button>
            </div>
          </template>
          <SignalTable :signals="signals" @execute="openTradeDialog" />
        </n-card>

        <n-card class="execution-card">
          <template #header><span>篮子交易</span></template>
          <BasketSelector @select="openBasketTrade" />
        </n-card>

        <n-modal
          v-model:show="tradeDialogVisible"
          preset="dialog"
          :title="`执行交易 - ${currentSymbol}`"
          positive-text="确定"
          negative-text="取消"
        >
          <TradeForm
            :symbol="currentSymbol"
            :price="currentPrice"
            :default-quantity="defaultQuantity"
            @submit="executeTrade"
          />
        </n-modal>
      </template>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useStore } from "vuex";
import { useMessage, NSpin, NResult } from "naive-ui";
import SignalTable from "@/components/trade/SignalTable.vue";
import BasketSelector from "@/views/Basket/BasketSelector.vue";
import TradeForm from "@/components/trade/TradeForm.vue";

const store = useStore();
const message = useMessage();
const loading = ref(false);
const error = ref(false);

const signals = ref<any[]>([
  {
    id: 1,
    strategy: "双均线策略",
    symbol: "600519.SH",
    name: "贵州茅台",
    signal: "买入",
    strength: 0.85,
    price: 1850.5,
    timestamp: "2023-08-09 10:05:32",
  },
  {
    id: 2,
    strategy: "动量反转策略",
    symbol: "000001.SH",
    name: "上证指数",
    signal: "卖出",
    strength: 0.72,
    price: 3245.67,
    timestamp: "2023-08-09 09:45:18",
  },
]);

const tradeDialogVisible = ref(false);
const currentSymbol = ref("");
const currentPrice = ref(0);
const defaultQuantity = ref(0);

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshSignals = () =>
  loadData().then(() => message.success("信号已刷新"));

const openTradeDialog = (signal: any) => {
  currentSymbol.value = signal.symbol;
  currentPrice.value = signal.price;
  defaultQuantity.value = signal.signal === "买入" ? 100 : -100;
  tradeDialogVisible.value = true;
};

const openBasketTrade = (basket: any) => {
  currentSymbol.value = basket.id;
  currentPrice.value = basket.currentValue;
  defaultQuantity.value = 0;
  tradeDialogVisible.value = true;
};

const executeTrade = (order: any) => {
  tradeDialogVisible.value = false;
  message.success("交易指令已发送");
  store.commit("trade/ADD_TRADE", {
    ...order,
    id: Date.now(),
    status: "已报",
    timestamp: new Date().toISOString(),
  });
};

onMounted(() => loadData());
</script>

<style scoped>
.trade-execution {
  padding: 20px;
}
.trade-execution h2 {
  margin: 0 0 16px;
  color: var(--n-text-color-1);
}
.execution-card {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
