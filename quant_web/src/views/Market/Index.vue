<!--行情首页-->
<template>
  <div class="market-index">
    <div class="market-header">
      <h2>市场概览</h2>
      <div class="market-filters">
        <el-select v-model="selectedMarket" placeholder="选择市场">
          <el-option label="沪深A股" value="A"></el-option>
          <el-option label="科创板" value="K"></el-option>
          <el-option label="创业板" value="C"></el-option>
          <el-option label="北交所" value="B"></el-option>
        </el-select>
        <el-select v-model="selectedIndustry" placeholder="选择行业">
          <el-option v-for="industry in industries" :key="industry" :label="industry" :value="industry"></el-option>
        </el-select>
        <el-button type="primary" icon="el-icon-refresh" @click="refreshData">刷新</el-button>
      </div>
    </div>

    <div class="market-grid">
      <!-- 大盘指数卡片 -->
      <div class="grid-card index-card">
        <h3>大盘指数</h3>
        <div class="index-list">
          <div v-for="index in marketIndices" :key="index.code" class="index-item">
            <div class="index-name">{{ index.name }}</div>
            <div class="index-value">{{ index.value }}</div>
            <div :class="['index-change', index.change > 0 ? 'positive' : 'negative']">
              {{ index.change > 0 ? '+' : '' }}{{ index.change }}%
            </div>
          </div>
        </div>
      </div>

      <!-- 涨跌分布 -->
      <div class="grid-card distribution-card">
        <h3>涨跌分布</h3>
        <div class="distribution-chart">
          <div class="distribution-item rise">
            <div class="distribution-label">上涨</div>
            <div class="distribution-bar">
              <div class="bar-fill" :style="{ width: risePercentage + '%' }"></div>
            </div>
            <div class="distribution-value">{{ riseCount }}</div>
          </div>
          <div class="distribution-item fall">
            <div class="distribution-label">下跌</div>
            <div class="distribution-bar">
              <div class="bar-fill" :style="{ width: fallPercentage + '%' }"></div>
            </div>
            <div class="distribution-value">{{ fallCount }}</div>
          </div>
          <div class="distribution-item flat">
            <div class="distribution-label">平盘</div>
            <div class="distribution-bar">
              <div class="bar-fill" :style="{ width: flatPercentage + '%' }"></div>
            </div>
            <div class="distribution-value">{{ flatCount }}</div>
          </div>
        </div>
      </div>

      <!-- 热门板块 -->
      <div class="grid-card hot-industry-card">
        <h3>热门板块</h3>
        <div class="industry-list">
          <div v-for="industry in hotIndustries" :key="industry.name" class="industry-item">
            <div class="industry-name">{{ industry.name }}</div>
            <div class="industry-change">{{ industry.change }}%</div>
            <div class="industry-stocks">{{ industry.stockCount }}只股票</div>
          </div>
        </div>
      </div>

      <!-- 股票排行榜 -->
      <div class="grid-card stock-rank-card">
        <h3>股票涨幅榜</h3>
        <el-table :data="topRisingStocks" style="width: 100%">
          <el-table-column prop="code" label="代码" width="80"></el-table-column>
          <el-table-column prop="name" label="名称"></el-table-column>
          <el-table-column prop="price" label="最新价"></el-table-column>
          <el-table-column prop="change" label="涨跌幅">
            <template #default="scope">
              <span :class="scope.row.change > 0 ? 'positive' : 'negative'">
                {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="volume" label="成交量(万)"></el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 自选股列表 -->
    <div class="favorite-stocks">
      <h3>自选股</h3>
      <el-table :data="favoriteStocks" style="width: 100%">
        <el-table-column prop="code" label="代码" width="80"></el-table-column>
        <el-table-column prop="name" label="名称"></el-table-column>
        <el-table-column prop="price" label="最新价"></el-table-column>
        <el-table-column prop="change" label="涨跌幅">
          <template #default="scope">
            <span :class="scope.row.change > 0 ? 'positive' : 'negative'">
              {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作">
          <template #default="scope">
            <el-button size="mini" @click="viewStockDetail(scope.row)">详情</el-button>
            <el-button size="mini" type="danger" @click="removeFavorite(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MarketIndex',
  data() {
    return {
      selectedMarket: 'A',
      selectedIndustry: '',
      industries: [
        '信息技术', '医药生物', '新能源', '消费', '金融',
        '房地产', '工业', '材料', '能源', '公用事业'
      ],
      marketIndices: [
        { name: '上证指数', code: '000001.SH', value: '3254.87', change: 0.56 },
        { name: '深证成指', code: '399001.SZ', value: '12045.32', change: -0.23 },
        { name: '创业板指', code: '399006.SZ', value: '2654.21', change: 1.24 },
        { name: '沪深300', code: '000300.SH', value: '4156.78', change: 0.78 },
        { name: '科创50', code: '000688.SH', value: '1124.56', change: 2.15 }
      ],
      riseCount: 2456,
      fallCount: 1234,
      flatCount: 210,
      hotIndustries: [
        { name: '人工智能', change: 4.56, stockCount: 42 },
        { name: '半导体', change: 3.78, stockCount: 35 },
        { name: '新能源汽车', change: 3.21, stockCount: 28 },
        { name: '光伏', change: 2.89, stockCount: 31 },
        { name: '医疗器械', change: 2.45, stockCount: 27 }
      ],
      topRisingStocks: [
        { code: '603019', name: '中科曙光', price: '45.32', change: 10.01, volume: '125.4' },
        { code: '002230', name: '科大讯飞', price: '67.89', change: 9.98, volume: '98.7' },
        { code: '300750', name: '宁德时代', price: '425.12', change: 8.76, volume: '86.3' },
        { code: '600519', name: '贵州茅台', price: '1785.45', change: 7.89, volume: '45.2' },
        { code: '000858', name: '五粮液', price: '215.67', change: 6.54, volume: '67.8' }
      ],
      favoriteStocks: [
        { code: '600519', name: '贵州茅台', price: '1785.45', change: 7.89 },
        { code: '000858', name: '五粮液', price: '215.67', change: 6.54 },
        { code: '601318', name: '中国平安', price: '48.32', change: -0.56 },
        { code: '600036', name: '招商银行', price: '36.78', change: 1.23 },
        { code: '300059', name: '东方财富', price: '24.56', change: 3.45 }
      ]
    };
  },
  computed: {
    totalStocks() {
      return this.riseCount + this.fallCount + this.flatCount;
    },
    risePercentage() {
      return (this.riseCount / this.totalStocks * 100).toFixed(1);
    },
    fallPercentage() {
      return (this.fallCount / this.totalStocks * 100).toFixed(1);
    },
    flatPercentage() {
      return (this.flatCount / this.totalStocks * 100).toFixed(1);
    }
  },
  methods: {
    refreshData() {
      console.log('刷新市场数据...');
      // 模拟数据刷新
      this.topRisingStocks = [...this.topRisingStocks];
      this.favoriteStocks = [...this.favoriteStocks];
    },
    viewStockDetail(stock) {
      this.$router.push({ name: 'StockDetail', params: { code: stock.code } });
    },
    removeFavorite(stock) {
      this.favoriteStocks = this.favoriteStocks.filter(s => s.code !== stock.code);
    }
  }
};
</script>

<style scoped>
.market-index {
  padding: 20px;
  background-color: #121a29;
  color: #e0e0e0;
  height: 100%;
  overflow-y: auto;
}

.market-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #2a3a5a;
}

.market-filters {
  display: flex;
  gap: 15px;
}

.market-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.grid-card {
  background: #1a2439;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.grid-card h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #64b5f6;
  border-bottom: 1px solid #2a3a5a;
  padding-bottom: 10px;
}

.index-card {
  grid-column: 1;
}

.distribution-card {
  grid-column: 2;
}

.hot-industry-card {
  grid-column: 1;
}

.stock-rank-card {
  grid-column: 2;
}

.index-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.index-item {
  display: flex;
  justify-content: space-between;
  padding: 10px;
  background: #152136;
  border-radius: 6px;
}

.index-name {
  font-weight: bold;
}

.index-value {
  color: #f5f5f5;
}

.index-change {
  font-weight: bold;
}

.positive {
  color: #f44336;
}

.negative {
  color: #4caf50;
}

.distribution-chart {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.distribution-item {
  display: flex;
  align-items: center;
  gap: 15px;
}

.distribution-label {
  width: 60px;
}

.distribution-bar {
  flex: 1;
  height: 20px;
  background: #2a3a5a;
  border-radius: 10px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
}

.rise .bar-fill {
  background: linear-gradient(90deg, #f44336, #e53935);
}

.fall .bar-fill {
  background: linear-gradient(90deg, #4caf50, #43a047);
}

.flat .bar-fill {
  background: linear-gradient(90deg, #9e9e9e, #757575);
}

.distribution-value {
  width: 50px;
  text-align: right;
}

.industry-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.industry-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #152136;
  border-radius: 6px;
  transition: background 0.3s;
}

.industry-item:hover {
  background: #1d2c46;
}

.industry-name {
  flex: 1;
}

.industry-change {
  width: 60px;
  text-align: right;
  font-weight: bold;
  color: #f44336;
}

.industry-stocks {
  width: 100px;
  text-align: right;
  color: #9e9e9e;
}

.favorite-stocks {
  background: #1a2439;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.favorite-stocks h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #64b5f6;
  border-bottom: 1px solid #2a3a5a;
  padding-bottom: 10px;
}

@media (max-width: 1200px) {
  .market-grid {
    grid-template-columns: 1fr;
  }

  .index-card,
  .distribution-card,
  .hot-industry-card,
  .stock-rank-card {
    grid-column: auto;
  }
}
</style>