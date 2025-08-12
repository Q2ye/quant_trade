<!--篮子编辑器-->
<template>
  <div class="basket-editor">
    <div class="header">
      <h2><i class="fas fa-shopping-basket"></i> 股票篮子编辑器</h2>
      <div class="controls">
        <button class="btn" @click="saveBasket">
          <i class="fas fa-save"></i> 保存篮子
        </button>
        <button class="btn" @click="applyBasket">
          <i class="fas fa-play"></i> 应用至交易
        </button>
      </div>
    </div>

    <div class="editor-container">
      <div class="left-panel">
        <div class="basket-info">
          <div class="input-group">
            <label for="basketName">篮子名称：</label>
            <input type="text" v-model="basketName" placeholder="输入篮子名称">
          </div>
          <div class="input-group">
            <label for="basketDescription">描述：</label>
            <textarea v-model="basketDescription" placeholder="输入篮子描述"></textarea>
          </div>
        </div>

        <div class="stock-search">
          <h3><i class="fas fa-search"></i> 股票搜索</h3>
          <div class="search-bar">
            <input
              type="text"
              v-model="searchQuery"
              placeholder="输入股票代码或名称"
              @input="searchStocks"
            >
            <i class="fas fa-search"></i>
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
              <div class="change" :class="stock.change >= 0 ? 'positive' : 'negative'">
                {{ stock.change >= 0 ? '+' : '' }}{{ stock.change }}%
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="right-panel">
        <h3><i class="fas fa-list"></i> 篮子成分股 ({{ basketStocks.length }})</h3>

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
              <div class="change" :class="stock.change >= 0 ? 'positive' : 'negative'">
                {{ stock.change >= 0 ? '+' : '' }}{{ stock.change }}%
              </div>
            </div>

            <div class="weight-control">
              <label for="stock.weight">权重：</label>
              <input
                type="number"
                v-model="stock.weight"
                min="0"
                max="100"
                step="1"
                @input="validateWeight(index)"
              > %
            </div>

            <button class="remove-btn" @click="removeStock(index)">
              <i class="fas fa-times"></i>
            </button>
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

<script>
export default {
  name: "BasketEditor",
  data() {
    return {
      basketName: "优质蓝筹股组合",
      basketDescription: "由各行业龙头组成的低波动蓝筹股投资组合",
      searchQuery: "",
      searchResults: [],
      basketStocks: [
        { symbol: "600519.SH", name: "贵州茅台", price: 1685.50, change: 1.25, weight: 20 },
        { symbol: "601318.SH", name: "中国平安", price: 48.25, change: -0.52, weight: 15 },
        { symbol: "600036.SH", name: "招商银行", price: 32.60, change: 0.92, weight: 15 },
        { symbol: "000333.SZ", name: "美的集团", price: 55.80, change: 2.10, weight: 10 },
        { symbol: "601888.SH", name: "中国中免", price: 102.40, change: -1.30, weight: 10 },
      ],
      allStocks: [
        { symbol: "600519.SH", name: "贵州茅台", price: 1685.50, change: 1.25 },
        { symbol: "601318.SH", name: "中国平安", price: 48.25, change: -0.52 },
        { symbol: "600036.SH", name: "招商银行", price: 32.60, change: 0.92 },
        { symbol: "000333.SZ", name: "美的集团", price: 55.80, change: 2.10 },
        { symbol: "601888.SH", name: "中国中免", price: 102.40, change: -1.30 },
        { symbol: "000858.SZ", name: "五粮液", price: 145.20, change: 0.75 },
        { symbol: "600900.SH", name: "长江电力", price: 23.45, change: 0.43 },
        { symbol: "600276.SH", name: "恒瑞医药", price: 38.70, change: -0.77 },
        { symbol: "601012.SH", name: "隆基绿能", price: 25.60, change: 1.85 },
        { symbol: "000651.SZ", name: "格力电器", price: 36.25, change: 0.83 },
      ]
    };
  },
  computed: {
    totalWeight() {
      return this.basketStocks.reduce((sum, stock) => sum + parseFloat(stock.weight || 0), 0);
    },
    basketValue() {
      // 模拟篮子价值计算
      return this.basketStocks.reduce((sum, stock) => {
        return sum + (stock.price * 1000 * (stock.weight / 100));
      }, 0);
    }
  },
  methods: {
    searchStocks() {
      if (!this.searchQuery) {
        this.searchResults = [];
        return;
      }

      const query = this.searchQuery.toLowerCase();
      this.searchResults = this.allStocks.filter(stock => {
        return stock.symbol.toLowerCase().includes(query) ||
               stock.name.toLowerCase().includes(query);
      }).slice(0, 5);
    },
    addStockToBasket(stock) {
      // 检查是否已在篮子中
      if (this.basketStocks.some(s => s.symbol === stock.symbol)) {
        this.$message.warning('该股票已在篮子中');
        return;
      }

      // 添加到篮子
      this.basketStocks.push({
        ...stock,
        weight: 0
      });

      this.searchQuery = "";
      this.searchResults = [];
    },
    removeStock(index) {
      this.basketStocks.splice(index, 1);
    },
    validateWeight(index) {
      if (this.basketStocks[index].weight > 100) {
        this.basketStocks[index].weight = 100;
      } else if (this.basketStocks[index].weight < 0) {
        this.basketStocks[index].weight = 0;
      }
    },
    saveBasket() {
      this.$message.success(`篮子 "${this.basketName}" 保存成功`);
      // 实际应用中这里会调用API保存篮子
    },
    applyBasket() {
      this.$emit('apply-basket', {
        name: this.basketName,
        stocks: this.basketStocks
      });
    }
  }
};
</script>

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

.header h2 i {
  font-size: 1.5rem;
  color: #409eff;
}

.controls {
  display: flex;
  gap: 15px;
}

.btn {
  padding: 10px 20px;
  background: rgba(24, 50, 90, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #a8c7ff;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn:hover {
  background: rgba(64, 158, 255, 0.2);
  border-color: #409eff;
  color: #e0e7ff;
}

.editor-container {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 20px;
  flex: 1;
  overflow: hidden;
}

.left-panel, .right-panel {
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

.input-group input, .input-group textarea {
  width: 100%;
  padding: 10px 12px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #e0e7ff;
  font-size: 1rem;
  outline: none;
}

.input-group textarea {
  height: 80px;
  resize: none;
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

.search-bar {
  position: relative;
}

.search-bar input {
  width: 100%;
  padding: 10px 15px 10px 40px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #e0e7ff;
  font-size: 1rem;
  outline: none;
}

.search-bar i {
  position: absolute;
  left: 15px;
  top: 50%;
  transform: translateY(-50%);
  color: #a8c7ff;
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
}

.weight-control input {
  width: 60px;
  padding: 5px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 4px;
  color: #e0e7ff;
  text-align: center;
}

.remove-btn {
  background: none;
  border: none;
  color: #ff6b6b;
  cursor: pointer;
  font-size: 1.1rem;
  transition: color 0.3s;
}

.remove-btn:hover {
  color: #ff3b3b;
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