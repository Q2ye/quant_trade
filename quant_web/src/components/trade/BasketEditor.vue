<!--篮子编辑器-->
<script setup lang="ts">
import { ref, computed } from "vue";
import { NInput, NInputNumber, NButton } from "naive-ui";
import { Icon } from "@iconify/vue";
import { useMessage } from "naive-ui";

interface Stock {
  symbol: string;
  name: string;
  price: number;
  change: number;
}

interface BasketStock extends Stock {
  weight: number;
}

const emit = defineEmits<{
  applyBasket: [payload: { name: string; stocks: BasketStock[] }];
}>();

const message = useMessage();

const basketName = ref("优质蓝筹股组合");
const basketDescription = ref("由各行业龙头组成的低波动蓝筹股投资组合");
const searchQuery = ref("");
const searchResults = ref<Stock[]>([]);

const basketStocks = ref<BasketStock[]>([
  {
    symbol: "600519.SH",
    name: "贵州茅台",
    price: 1685.5,
    change: 1.25,
    weight: 20,
  },
  {
    symbol: "601318.SH",
    name: "中国平安",
    price: 48.25,
    change: -0.52,
    weight: 15,
  },
  {
    symbol: "600036.SH",
    name: "招商银行",
    price: 32.6,
    change: 0.92,
    weight: 15,
  },
  {
    symbol: "000333.SZ",
    name: "美的集团",
    price: 55.8,
    change: 2.1,
    weight: 10,
  },
  {
    symbol: "601888.SH",
    name: "中国中免",
    price: 102.4,
    change: -1.3,
    weight: 10,
  },
]);

const allStocks: Stock[] = [
  { symbol: "600519.SH", name: "贵州茅台", price: 1685.5, change: 1.25 },
  { symbol: "601318.SH", name: "中国平安", price: 48.25, change: -0.52 },
  { symbol: "600036.SH", name: "招商银行", price: 32.6, change: 0.92 },
  { symbol: "000333.SZ", name: "美的集团", price: 55.8, change: 2.1 },
  { symbol: "601888.SH", name: "中国中免", price: 102.4, change: -1.3 },
  { symbol: "000858.SZ", name: "五粮液", price: 145.2, change: 0.75 },
  { symbol: "600900.SH", name: "长江电力", price: 23.45, change: 0.43 },
  { symbol: "600276.SH", name: "恒瑞医药", price: 38.7, change: -0.77 },
  { symbol: "601012.SH", name: "隆基绿能", price: 25.6, change: 1.85 },
  { symbol: "000651.SZ", name: "格力电器", price: 36.25, change: 0.83 },
];

const totalWeight = computed(() =>
  basketStocks.value.reduce((sum, s) => sum + (s.weight || 0), 0),
);

const basketValue = computed(() =>
  basketStocks.value.reduce(
    (sum, s) => sum + s.price * 1000 * (s.weight / 100),
    0,
  ),
);

const searchStocks = () => {
  if (!searchQuery.value) {
    searchResults.value = [];
    return;
  }
  const query = searchQuery.value.toLowerCase();
  searchResults.value = allStocks
    .filter(
      (s) =>
        s.symbol.toLowerCase().includes(query) ||
        s.name.toLowerCase().includes(query),
    )
    .slice(0, 5);
};

const addStockToBasket = (stock: Stock) => {
  if (basketStocks.value.some((s) => s.symbol === stock.symbol)) {
    message.warning("该股票已在篮子中");
    return;
  }
  basketStocks.value.push({ ...stock, weight: 0 });
  searchQuery.value = "";
  searchResults.value = [];
};

const removeStock = (index: number) => {
  basketStocks.value.splice(index, 1);
};

const validateWeight = (index: number) => {
  const item = basketStocks.value[index];
  if (item.weight > 100) item.weight = 100;
  else if (item.weight < 0) item.weight = 0;
};

const saveBasket = () => {
  message.success(`篮子 "${basketName.value}" 保存成功`);
};

const applyBasket = () => {
  emit("applyBasket", {
    name: basketName.value,
    stocks: basketStocks.value,
  });
};
</script>

<template>
  <div class="basket-editor">
    <div class="header">
      <h2><Icon icon="ant-design:shopping-outlined" /> 股票篮子编辑器</h2>
      <div class="controls">
        <n-button @click="saveBasket">
          <template #icon><Icon icon="ant-design:save-outlined" /></template>
          保存篮子
        </n-button>
        <n-button type="primary" @click="applyBasket">
          <template #icon
            ><Icon icon="ant-design:play-circle-outlined"
          /></template>
          应用至交易
        </n-button>
      </div>
    </div>

    <div class="editor-container">
      <div class="left-panel">
        <div class="basket-info">
          <div class="input-group">
            <label>篮子名称：</label>
            <n-input v-model:value="basketName" placeholder="输入篮子名称" />
          </div>
          <div class="input-group">
            <label>描述：</label>
            <n-input
              v-model:value="basketDescription"
              type="textarea"
              placeholder="输入篮子描述"
              :autosize="{ minRows: 3, maxRows: 5 }"
            />
          </div>
        </div>

        <div class="stock-search">
          <h3><Icon icon="ant-design:search-outlined" /> 股票搜索</h3>
          <div class="search-bar">
            <n-input
              v-model:value="searchQuery"
              placeholder="输入股票代码或名称"
              @input="searchStocks"
            >
              <template #prefix>
                <Icon icon="ant-design:search-outlined" />
              </template>
            </n-input>
          </div>

          <div class="search-results">
            <div
              v-for="stock in searchResults"
              :key="stock.symbol"
              class="stock-item"
              @click="addStockToBasket(stock)"
            >
              <div class="symbol">{{ stock.symbol }}</div>
              <div class="name">{{ stock.name }}</div>
              <div class="price">{{ stock.price }}</div>
              <div
                class="change"
                :class="stock.change >= 0 ? 'positive' : 'negative'"
              >
                {{ stock.change >= 0 ? "+" : "" }}{{ stock.change }}%
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <h3>
          <Icon icon="ant-design:unordered-list-outlined" /> 篮子成分股 ({{
            basketStocks.length
          }})
        </h3>

        <div class="basket-stocks">
          <div
            v-for="(stock, index) in basketStocks"
            :key="stock.symbol"
            class="basket-item"
          >
            <div class="stock-info">
              <div class="symbol">{{ stock.symbol }}</div>
              <div class="name">{{ stock.name }}</div>
            </div>

            <div class="stock-data">
              <div class="price">{{ stock.price }}</div>
              <div
                class="change"
                :class="stock.change >= 0 ? 'positive' : 'negative'"
              >
                {{ stock.change >= 0 ? "+" : "" }}{{ stock.change }}%
              </div>
            </div>

            <div class="weight-control">
              <label>权重：</label>
              <n-input-number
                v-model:value="stock.weight"
                :min="0"
                :max="100"
                :step="1"
                size="small"
                @update:value="validateWeight(index)"
              />
              <span>%</span>
            </div>

            <n-button
              text
              type="error"
              class="remove-btn"
              @click="removeStock(index)"
            >
              <template #icon
                ><Icon icon="ant-design:close-outlined"
              /></template>
            </n-button>
          </div>
        </div>

        <div class="basket-stats">
          <div class="stat">
            <div class="label">总权重</div>
            <div class="value">{{ totalWeight }}%</div>
          </div>
          <div class="stat">
            <div class="label">股票数量</div>
            <div class="value">{{ basketStocks.length }}</div>
          </div>
          <div class="stat">
            <div class="label">篮子价值</div>
            <div class="value">¥{{ basketValue.toLocaleString() }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.basket-editor {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
}

.header h2 {
  font-size: 1.8rem;
  color: #64b5f6;
  display: flex;
  align-items: center;
  gap: 10px;
}

.controls {
  display: flex;
  gap: 15px;
}

.editor-container {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 20px;
  flex: 1;
  overflow: hidden;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  height: 100%;
}

.basket-info {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.input-group {
  margin-bottom: 15px;
}

.input-group label {
  display: block;
  margin-bottom: 5px;
  color: #a8c7ff;
  font-size: 0.95rem;
}

.stock-search {
  flex: 1;
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stock-search h3 {
  color: #64b5f6;
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-results {
  flex: 1;
  overflow-y: auto;
}

.stock-item {
  padding: 12px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
  cursor: pointer;
  display: grid;
  grid-template-columns: 80px 1fr 80px 70px;
  gap: 10px;
  align-items: center;
  transition: background 0.3s;
}

.stock-item:hover {
  background: rgba(64, 158, 255, 0.1);
}

.stock-item .symbol {
  font-weight: 600;
  color: #64b5f6;
}

.stock-item .name {
  color: #a8c7ff;
  font-size: 0.9rem;
}

.stock-item .price {
  font-weight: 500;
  text-align: right;
}

.stock-item .change {
  text-align: right;
  font-weight: 500;
}

.stock-item .positive {
  color: #5cdd8b;
}
.stock-item .negative {
  color: #ff6b6b;
}

.right-panel {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  display: flex;
  flex-direction: column;
}

.right-panel h3 {
  color: #64b5f6;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.basket-stocks {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 15px;
}

.basket-item {
  padding: 12px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 40px;
  gap: 10px;
  align-items: center;
}

.basket-item .stock-info {
  display: flex;
  flex-direction: column;
}

.basket-item .symbol {
  font-weight: 600;
  color: #64b5f6;
}

.basket-item .name {
  color: #a8c7ff;
  font-size: 0.85rem;
}

.basket-item .stock-data {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.basket-item .price {
  font-weight: 500;
  color: #e0e7ff;
}

.basket-item .change {
  font-weight: 500;
  font-size: 0.9rem;
}

.basket-item .positive {
  color: #5cdd8b;
}
.basket-item .negative {
  color: #ff6b6b;
}

.weight-control {
  display: flex;
  align-items: center;
  gap: 5px;
}

.weight-control label {
  color: #a8c7ff;
  font-size: 0.9rem;
  white-space: nowrap;
}

.weight-control .n-input-number {
  width: 80px;
}

.basket-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  border-top: 1px solid rgba(64, 158, 255, 0.2);
  padding-top: 15px;
}

.stat {
  background: rgba(16, 33, 59, 0.7);
  border-radius: 6px;
  padding: 10px;
  text-align: center;
}

.stat .label {
  color: #a8c7ff;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.stat .value {
  font-weight: 600;
  font-size: 1.1rem;
  color: #64b5f6;
}
</style>
