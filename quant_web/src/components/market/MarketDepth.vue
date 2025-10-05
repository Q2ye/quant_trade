<!-- src/components/market/MarketDepth.vue -->
<template>
  <div class="market-depth">
    <div class="depth-header">
      <h3>{{ symbol || '选择标的' }}</h3>
      <div class="price-info" v-if="currentPrice">
        <span class="price">{{ currentPrice.toFixed(2) }}</span>
        <span class="change" :class="changeClass">
          {{ change >= 0 ? '+' : '' }}{{ change.toFixed(2) }} ({{ changePercent >= 0 ? '+' : '' }}{{ changePercent.toFixed(2) }}%)
        </span>
      </div>
    </div>

    <div class="depth-container" v-if="depthData.bids.length > 0 || depthData.asks.length > 0">
      <!-- 卖盘 (Ask) -->
      <div class="depth-side ask-side">
        <div class="depth-header-row">
          <span>卖盘</span>
          <span>价格(元)</span>
          <span>数量(手)</span>
        </div>
        <div
          class="depth-row ask-row"
          v-for="(ask, index) in depthData.asks.slice().reverse()"
          :key="'ask-' + index"
          :style="getAskRowStyle(ask)"
        >
          <span class="depth-index">{{ 5 - index }}</span>
          <span class="price">{{ ask.price.toFixed(2) }}</span>
          <span class="volume">{{ ask.volume }}</span>
        </div>
      </div>

      <!-- 当前价格 -->
      <div class="current-price" v-if="currentPrice">
        <div class="price-display">
          {{ currentPrice.toFixed(2) }}
        </div>
        <div class="price-label">最新价</div>
      </div>

      <!-- 买盘 (Bid) -->
      <div class="depth-side bid-side">
        <div class="depth-header-row">
          <span>买盘</span>
          <span>价格(元)</span>
          <span>数量(手)</span>
        </div>
        <div
          class="depth-row bid-row"
          v-for="(bid, index) in depthData.bids"
          :key="'bid-' + index"
          :style="getBidRowStyle(bid)"
        >
          <span class="depth-index">{{ index + 1 }}</span>
          <span class="price">{{ bid.price.toFixed(2) }}</span>
          <span class="volume">{{ bid.volume }}</span>
        </div>
      </div>
    </div>

    <div class="empty-state" v-else>
      <i class="fas fa-chart-bar"></i>
      <p>暂无深度数据</p>
      <p class="hint">请选择交易标的查看深度行情</p>
    </div>

    <!-- 统计信息 -->
    <div class="depth-stats" v-if="depthData.bids.length > 0 && depthData.asks.length > 0">
      <div class="stat-item">
        <span class="label">买卖价差:</span>
        <span class="value">{{ spread.toFixed(2) }}</span>
      </div>
      <div class="stat-item">
        <span class="label">买卖总量比:</span>
        <span class="value">{{ bidAskRatio.toFixed(2) }}</span>
      </div>
      <div class="stat-item">
        <span class="label">深度强度:</span>
        <span class="value" :class="depthStrengthClass">
          {{ depthStrength.toFixed(1) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "MarketDepth",
  props: {
    symbol: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      currentPrice: 0,
      change: 0,
      changePercent: 0,
      depthData: {
        bids: [],
        asks: []
      },
      updateInterval: null
    };
  },
  computed: {
    changeClass() {
      return this.change >= 0 ? 'positive' : 'negative';
    },
    spread() {
      if (this.depthData.asks.length === 0 || this.depthData.bids.length === 0) {
        return 0;
      }
      const bestAsk = this.depthData.asks[this.depthData.asks.length - 1].price;
      const bestBid = this.depthData.bids[0].price;
      return bestAsk - bestBid;
    },
    bidAskRatio() {
      const totalBidVolume = this.depthData.bids.reduce((sum, bid) => sum + bid.volume, 0);
      const totalAskVolume = this.depthData.asks.reduce((sum, ask) => sum + ask.volume, 0);
      return totalBidVolume / (totalAskVolume || 1);
    },
    depthStrength() {
      const totalVolume = this.depthData.bids.reduce((sum, bid) => sum + bid.volume, 0) +
                         this.depthData.asks.reduce((sum, ask) => sum + ask.volume, 0);
      const maxPossible = 50000; // 假设最大深度为50000手
      return Math.min((totalVolume / maxPossible) * 100, 100);
    },
    depthStrengthClass() {
      if (this.depthStrength > 70) return 'strength-high';
      if (this.depthStrength > 30) return 'strength-medium';
      return 'strength-low';
    }
  },
  watch: {
    symbol(newSymbol) {
      if (newSymbol) {
        this.loadDepthData();
        this.startRealTimeUpdates();
      } else {
        this.stopRealTimeUpdates();
        this.resetData();
      }
    }
  },
  mounted() {
    if (this.symbol) {
      this.loadDepthData();
      this.startRealTimeUpdates();
    }
  },
  beforeDestroy() {
    this.stopRealTimeUpdates();
  },
  methods: {
    loadDepthData() {
      // 模拟深度数据 - 在实际应用中这里应该调用API获取实时深度数据
      const basePrice = this.getMockPrice(this.symbol);
      this.currentPrice = basePrice;
      this.change = (Math.random() - 0.5) * 2;
      this.changePercent = (this.change / basePrice) * 100;

      // 生成买卖五档数据
      this.depthData = {
        bids: this.generateBids(basePrice),
        asks: this.generateAsks(basePrice)
      };
    },

    getMockPrice(symbol) {
      // 根据股票代码返回模拟基准价格
      const priceMap = {
        '600519.SH': 1685.50,
        '601318.SH': 48.25,
        '600036.SH': 32.60,
        '000333.SZ': 55.80,
        '601888.SH': 102.40
      };
      return priceMap[symbol] || 10 + Math.random() * 100;
    },

    generateBids(basePrice) {
      const bids = [];
      let price = basePrice - 0.01;
      for (let i = 0; i < 5; i++) {
        bids.push({
          price: price - i * 0.01,
          volume: Math.floor(Math.random() * 500) + 100
        });
      }
      return bids.sort((a, b) => b.price - a.price); // 价格从高到低排序
    },

    generateAsks(basePrice) {
      const asks = [];
      let price = basePrice + 0.01;
      for (let i = 0; i < 5; i++) {
        asks.push({
          price: price + i * 0.01,
          volume: Math.floor(Math.random() * 500) + 100
        });
      }
      return asks.sort((a, b) => a.price - b.price); // 价格从低到高排序
    },

    updateDepthData() {
      // 模拟实时深度数据更新
      if (this.depthData.bids.length > 0 && this.depthData.asks.length > 0) {
        // 随机更新一些档位的数量
        const bidIndex = Math.floor(Math.random() * this.depthData.bids.length);
        const askIndex = Math.floor(Math.random() * this.depthData.asks.length);

        this.depthData.bids[bidIndex].volume = Math.max(10,
          this.depthData.bids[bidIndex].volume + Math.floor(Math.random() * 100 - 50)
        );
        this.depthData.asks[askIndex].volume = Math.max(10,
          this.depthData.asks[askIndex].volume + Math.floor(Math.random() * 100 - 50)
        );

        // 小幅更新当前价格
        const priceChange = (Math.random() - 0.5) * 0.1;
        this.currentPrice += priceChange;
        this.change += priceChange;
        this.changePercent = (this.change / (this.currentPrice - this.change)) * 100;

        // 触发响应式更新
        this.depthData = { ...this.depthData };
      }
    },

    getAskRowStyle(ask) {
      const maxVolume = Math.max(...this.depthData.asks.map(a => a.volume));
      const widthPercent = (ask.volume / maxVolume) * 80;
      return {
        '--volume-width': `${widthPercent}%`
      };
    },

    getBidRowStyle(bid) {
      const maxVolume = Math.max(...this.depthData.bids.map(b => b.volume));
      const widthPercent = (bid.volume / maxVolume) * 80;
      return {
        '--volume-width': `${widthPercent}%`
      };
    },

    startRealTimeUpdates() {
      this.stopRealTimeUpdates();
      this.updateInterval = setInterval(() => {
        this.updateDepthData();
      }, 2000); // 每2秒更新一次
    },

    stopRealTimeUpdates() {
      if (this.updateInterval) {
        clearInterval(this.updateInterval);
        this.updateInterval = null;
      }
    },

    resetData() {
      this.currentPrice = 0;
      this.change = 0;
      this.changePercent = 0;
      this.depthData = {
        bids: [],
        asks: []
      };
    }
  }
};
</script>

<style scoped>
.market-depth {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: rgba(16, 33, 59, 0.8);
  border-radius: 8px;
  padding: 12px;
}

.depth-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
}

.depth-header h3 {
  margin: 0;
  color: #64b5f6;
  font-size: 1.1rem;
}

.price-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.price {
  font-size: 1.3rem;
  font-weight: 600;
  color: #e0e7ff;
}

.change {
  font-size: 0.85rem;
  font-weight: 500;
}

.change.positive {
  color: #5cdd8b;
}

.change.negative {
  color: #ff6b6b;
}

.depth-container {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: 1;
}

.depth-side {
  display: flex;
  flex-direction: column;
}

.depth-header-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr;
  gap: 8px;
  padding: 5px 8px;
  font-size: 0.8rem;
  color: #a8c7ff;
  border-bottom: 1px solid rgba(64, 158, 255, 0.1);
}

.depth-row {
  display: grid;
  grid-template-columns: 40px 1fr 1fr;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 0.9rem;
  position: relative;
  overflow: hidden;
  transition: all 0.2s;
}

.depth-row:hover {
  background: rgba(64, 158, 255, 0.1);
}

.ask-row {
  color: #ff6b6b;
}

.ask-row::before {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: var(--volume-width);
  background: linear-gradient(90deg, rgba(255, 107, 107, 0.1) 0%, rgba(255, 107, 107, 0.3) 100%);
  border-radius: 0 4px 4px 0;
}

.bid-row {
  color: #5cdd8b;
}

.bid-row::before {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: var(--volume-width);
  background: linear-gradient(90deg, rgba(92, 221, 139, 0.1) 0%, rgba(92, 221, 139, 0.3) 100%);
  border-radius: 0 4px 4px 0;
}

.depth-index {
  text-align: center;
  font-weight: 500;
  color: #a8c7ff;
}

.price {
  font-weight: 600;
  text-align: right;
}

.volume {
  text-align: right;
  font-weight: 500;
}

.current-price {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10px 0;
  margin: 5px 0;
  border-top: 1px solid rgba(64, 158, 255, 0.2);
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
}

.price-display {
  font-size: 1.4rem;
  font-weight: 700;
  color: #64b5f6;
  margin-bottom: 4px;
}

.price-label {
  font-size: 0.8rem;
  color: #a8c7ff;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #a8c7ff;
  opacity: 0.7;
}

.empty-state i {
  font-size: 3rem;
  margin-bottom: 10px;
}

.hint {
  font-size: 0.85rem;
  margin-top: 5px;
  opacity: 0.6;
}

.depth-stats {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  margin-top: 15px;
  padding-top: 10px;
  border-top: 1px solid rgba(64, 158, 255, 0.2);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  background: rgba(16, 33, 59, 0.6);
  border-radius: 4px;
}

.stat-item .label {
  font-size: 0.75rem;
  color: #a8c7ff;
  margin-bottom: 4px;
}

.stat-item .value {
  font-size: 0.9rem;
  font-weight: 600;
  color: #e0e7ff;
}

.strength-high {
  color: #5cdd8b !important;
}

.strength-medium {
  color: #ffb86c !important;
}

.strength-low {
  color: #ff6b6b !important;
}

/* 响应式设计 */
@media (max-height: 700px) {
  .depth-header {
    margin-bottom: 10px;
  }

  .depth-row {
    padding: 4px 8px;
    font-size: 0.85rem;
  }

  .current-price {
    padding: 5px 0;
    margin: 3px 0;
  }

  .price-display {
    font-size: 1.2rem;
  }
}
</style>