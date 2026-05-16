<template>
  <div class="basket-selector bg-gradient-mesh bg-noise">
    <div class="selector-header">
      <n-select
        v-model:value="selectedBasket"
        placeholder="选择股票篮子"
        @update:value="handleBasketChange"
        size="small"
        :options="basketOptions"
        style="width: 300px"
      />
      <n-button
        type="primary"
        size="small"
        style="margin-left: 10px"
        @click="createNewBasket"
      >
        新建篮子
      </n-button>
    </div>

    <div class="basket-body">
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
          <div class="basket-content" v-if="currentBasket">
            <div class="basket-info">
              <h3>{{ currentBasket.name }}</h3>
              <p class="description">
                {{ currentBasket.description || "暂无描述" }}
              </p>
              <p class="stats">
                创建于: {{ currentBasket.createdAt }} | 股票数:
                {{ currentBasket.stocks.length }} | 最后更新:
                {{ currentBasket.updatedAt }}
              </p>
            </div>

            <div class="basket-stocks">
              <n-data-table
                :data="currentBasket.stocks"
                :columns="stockColumns"
                :max-height="300"
                :row-key="(row: any) => row.symbol"
                striped
                :bordered="false"
                @update:checked-row-keys="handleStockClick"
              />
            </div>

            <div class="basket-actions">
              <n-space :size="8">
                <n-button
                  type="primary"
                  @click="applyToTrade"
                  :disabled="!currentBasket.stocks.length"
                >
                  应用至交易
                </n-button>
                <n-button @click="exportBasket"> 导出篮子 </n-button>
                <n-button
                  type="error"
                  style="margin-left: auto"
                  @click="deleteBasket"
                >
                  删除篮子
                </n-button>
              </n-space>
            </div>
          </div>

          <div class="empty-basket" v-else>
            <n-empty description="请选择或创建股票篮子" />
          </div>
        </template>
      </n-spin>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted } from "vue";
import { NButton, NInputNumber, NTag, NSpin, NResult } from "naive-ui";

const emit = defineEmits<{
  (e: "basket-change", basket: any): void;
  (e: "basket-created", basket: any): void;
  (
    e: "weight-updated",
    payload: { basketId: string; symbol: string; weight: number },
  ): void;
  (e: "stock-removed", payload: { basketId: string; symbol: string }): void;
  (e: "apply-basket", basket: any): void;
  (e: "export-basket", basket: any): void;
  (e: "basket-deleted", id: string): void;
  (e: "stock-click", stock: any): void;
}>();

const loading = ref(false);
const error = ref(false);

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

const baskets = ref([
  {
    id: "1",
    name: "核心资产组合",
    description: "长期持有的核心资产",
    count: 5,
    createdAt: "2023-07-15",
    updatedAt: "2023-08-10",
    stocks: [
      {
        symbol: "600519.SH",
        name: "贵州茅台",
        weight: 25,
        lastPrice: 1850.5,
        change: 1.25,
      },
      {
        symbol: "600036.SH",
        name: "招商银行",
        weight: 20,
        lastPrice: 32.6,
        change: -0.35,
      },
      {
        symbol: "601318.SH",
        name: "中国平安",
        weight: 18,
        lastPrice: 48.25,
        change: 0.82,
      },
      {
        symbol: "000858.SZ",
        name: "五粮液",
        weight: 17,
        lastPrice: 172.8,
        change: 2.15,
      },
      {
        symbol: "600900.SH",
        name: "长江电力",
        weight: 20,
        lastPrice: 22.45,
        change: 0.45,
      },
    ],
  },
  {
    id: "2",
    name: "科技成长组合",
    description: "高成长科技企业",
    count: 8,
    createdAt: "2023-08-01",
    updatedAt: "2023-08-11",
    stocks: [
      {
        symbol: "300750.SZ",
        name: "宁德时代",
        weight: 30,
        lastPrice: 232.8,
        change: 3.25,
      },
      {
        symbol: "002475.SZ",
        name: "立讯精密",
        weight: 15,
        lastPrice: 32.15,
        change: -1.2,
      },
      {
        symbol: "603986.SH",
        name: "兆易创新",
        weight: 12.5,
        lastPrice: 105.6,
        change: 0.75,
      },
    ],
  },
]);

const selectedBasket = ref("");
const currentBasket = ref<any>(null);

const basketOptions = computed(() =>
  baskets.value.map((b) => ({
    label: b.name,
    value: b.id,
  })),
);

const stockColumns = computed(() => [
  { title: "代码", key: "symbol", width: 90 },
  { title: "名称", key: "name", width: 120 },
  {
    title: "权重",
    key: "weight",
    width: 140,
    render(row: any) {
      return h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "4px" } },
        [
          h(NInputNumber, {
            value: row.weight,
            min: 0,
            max: 100,
            step: 1,
            size: "tiny",
            style: { width: "80px" },
            onUpdateValue: (v: number | null) => {
              row.weight = v ?? 0;
              updateWeight(row);
            },
          }),
          h("span", "%"),
        ],
      );
    },
  },
  {
    title: "当前价",
    key: "lastPrice",
    width: 100,
    render(row: any) {
      return row.lastPrice ? row.lastPrice.toFixed(2) : "--";
    },
  },
  {
    title: "涨跌幅",
    key: "change",
    width: 100,
    render(row: any) {
      const cls = row.change >= 0 ? "up" : "down";
      const prefix = row.change >= 0 ? "+" : "";
      return h(
        "span",
        { class: cls },
        `${prefix}${row.change ? row.change.toFixed(2) : "0.00"}%`,
      );
    },
  },
  {
    title: "操作",
    key: "actions",
    width: 80,
    render(row: any) {
      return h(
        NButton,
        {
          type: "error",
          size: "tiny",
          circle: true,
          onClick: (e: Event) => {
            e.stopPropagation();
            removeStock(row);
          },
        },
        { default: () => "✕" },
      );
    },
  },
]);

const handleBasketChange = (basketId: string) => {
  currentBasket.value = baskets.value.find((b) => b.id === basketId);
  emit("basket-change", currentBasket.value);
};

const createNewBasket = () => {
  const newId = `basket-${Date.now()}`;
  const newBasket = {
    id: newId,
    name: `新篮子 ${baskets.value.length + 1}`,
    description: "",
    count: 0,
    createdAt: new Date().toISOString().split("T")[0],
    updatedAt: new Date().toISOString().split("T")[0],
    stocks: [],
  };
  baskets.value.push(newBasket);
  selectedBasket.value = newId;
  currentBasket.value = newBasket;
  emit("basket-created", newBasket);
};

const updateWeight = (stock: any) => {
  emit("weight-updated", {
    basketId: currentBasket.value.id,
    symbol: stock.symbol,
    weight: stock.weight,
  });
};

const removeStock = (stock: any) => {
  const index = currentBasket.value.stocks.findIndex(
    (s: any) => s.symbol === stock.symbol,
  );
  if (index !== -1) {
    currentBasket.value.stocks.splice(index, 1);
    currentBasket.value.count = currentBasket.value.stocks.length;
    emit("stock-removed", {
      basketId: currentBasket.value.id,
      symbol: stock.symbol,
    });
  }
};

const applyToTrade = () => emit("apply-basket", currentBasket.value);
const exportBasket = () => emit("export-basket", currentBasket.value);
const deleteBasket = () => {
  emit("basket-deleted", currentBasket.value.id);
  baskets.value = baskets.value.filter((b) => b.id !== currentBasket.value.id);
  selectedBasket.value = "";
  currentBasket.value = null;
};
const handleStockClick = (stock: any) => emit("stock-click", stock);

onMounted(() => loadData());
</script>

<style scoped>
.basket-selector {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.selector-header {
  margin-bottom: 20px;
  display: flex;
}
.basket-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.basket-info {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}
.basket-info h3 {
  margin: 0 0 10px;
  font-size: 18px;
}
.description {
  color: var(--n-text-color-3);
  font-size: 14px;
  margin: 5px 0;
}
.stats {
  color: var(--n-text-color-3);
  font-size: 12px;
  margin: 5px 0;
}
.basket-stocks {
  flex: 1;
  margin-bottom: 15px;
}
.basket-actions {
  text-align: left;
}
.empty-basket {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.up {
  color: #f56c6c;
}
.down {
  color: #5cb87a;
}
</style>
