<!--行情报价面板-->
<script>
export default {
  name: "QuotePanel",
  props: {
    symbol: {
      type: String,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
    realTimeData: {
      type: Object,
      default: () => ({
        price: 0,
        open: 0,
        high: 0,
        low: 0,
        prevClose: 0,
        change: 0,
        changePercent: 0,
        volume: 0,
        amount: 0,
        time: "",
      }),
    },
    depthData: {
      type: Array,
      default: () => [
        { price: 10.25, volume: 1500 },
        { price: 10.24, volume: 3200 },
        { price: 10.23, volume: 4800 },
        { price: 10.22, volume: 2100 },
        { price: 10.21, volume: 1500 },
      ],
    },
  },
  computed: {
    priceColor() {
      if (this.realTimeData.change > 0) return "color-up";
      if (this.realTimeData.change < 0) return "color-down";
      return "";
    },

    formattedVolume() {
      return this.formatNumber(this.realTimeData.volume);
    },

    formattedAmount() {
      return this.formatNumber(this.realTimeData.amount);
    },
  },
  methods: {
    formatNumber(num) {
      if (num >= 100000000) {
        return (num / 100000000).toFixed(2) + "亿";
      } else if (num >= 10000) {
        return (num / 10000).toFixed(2) + "万";
      }
      return num.toString();
    },

    formatPrice(price) {
      return price.toFixed(2);
    },
  },
};
</script>

<template>
  <div class="quote-panel">
    <div class="stock-header">
      <div class="stock-name">{{ name }}</div>
      <div class="stock-symbol">{{ symbol }}</div>
    </div>

    <div class="price-section">
      <div class="current-price" :class="priceColor">
        {{ formatPrice(realTimeData.price) }}
      </div>
      <div class="price-change" :class="priceColor">
        <span
          >{{ realTimeData.change > 0 ? "+" : ""
          }}{{ formatPrice(realTimeData.change) }}</span
        >
        <span
          >({{ realTimeData.change > 0 ? "+" : ""
          }}{{ realTimeData.changePercent.toFixed(2) }}%)</span
        >
      </div>
    </div>

    <div class="detail-grid">
      <div class="detail-item">
        <div class="detail-label">今开</div>
        <div class="detail-value">{{ formatPrice(realTimeData.open) }}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">最高</div>
        <div class="detail-value">{{ formatPrice(realTimeData.high) }}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">昨收</div>
        <div class="detail-value">
          {{ formatPrice(realTimeData.prevClose) }}
        </div>
      </div>
      <div class="detail-item">
        <div class="detail-label">最低</div>
        <div class="detail-value">{{ formatPrice(realTimeData.low) }}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">成交量</div>
        <div class="detail-value">{{ formattedVolume }}</div>
      </div>
      <div class="detail-item">
        <div class="detail-label">成交额</div>
        <div class="detail-value">{{ formattedAmount }}元</div>
      </div>
    </div>

    <div class="depth-section">
      <h3 class="section-title">五档行情</h3>
      <div class="depth-container">
        <div class="depth-column">
          <div class="depth-header">
            <span>买价</span>
            <span>数量(手)</span>
          </div>
          <div
            v-for="(item, index) in depthData.slice(0, 5)"
            :key="'bid' + index"
            class="depth-row bid-row"
          >
            <span>{{ index + 1 }}</span>
            <span class="bid-price">{{ formatPrice(item.price) }}</span>
            <span>{{ formatNumber(item.volume) }}</span>
          </div>
        </div>

        <div class="depth-column">
          <div class="depth-header">
            <span>卖价</span>
            <span>数量(手)</span>
          </div>
          <div
            v-for="(item, index) in depthData.slice(0, 5)"
            :key="'ask' + index"
            class="depth-row ask-row"
          >
            <span>{{ index + 1 }}</span>
            <span class="ask-price">{{ formatPrice(item.price) }}</span>
            <span>{{ formatNumber(item.volume) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div class="time-section">
      <span>更新时间: {{ realTimeData.time }}</span>
    </div>
  </div>
</template>

<style scoped>
.quote-panel {
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 15px;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
}

.stock-header {
  display: flex;
  align-items: baseline;
  margin-bottom: 10px;
}

.stock-name {
  font-size: 18px;
  font-weight: bold;
  margin-right: 10px;
}

.stock-symbol {
  font-size: 14px;
  color: #606266;
}

.price-section {
  margin-bottom: 15px;
}

.current-price {
  font-size: 28px;
  font-weight: bold;
  line-height: 1.2;
}

.price-change {
  font-size: 16px;
}

.color-up {
  color: #f56c6c;
}

.color-down {
  color: #67c23a;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 20px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
}

.detail-label {
  color: #909399;
}

.detail-value {
  font-weight: 500;
}

.section-title {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
  padding-bottom: 5px;
  border-bottom: 1px solid #ebeef5;
}

.depth-container {
  display: flex;
  gap: 20px;
}

.depth-column {
  flex: 1;
}

.depth-header {
  display: flex;
  justify-content: space-between;
  padding: 5px 10px;
  background-color: #f5f7fa;
  font-size: 12px;
  color: #909399;
  border-radius: 4px;
}

.depth-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 10px;
  font-size: 13px;
}

.depth-row span:first-child {
  width: 20px;
  text-align: center;
}

.bid-price {
  color: #67c23a;
  font-weight: bold;
}

.ask-price {
  color: #f56c6c;
  font-weight: bold;
}

.time-section {
  margin-top: 15px;
  text-align: right;
  font-size: 12px;
  color: #909399;
  padding-top: 10px;
  border-top: 1px dashed #ebeef5;
}
</style>
