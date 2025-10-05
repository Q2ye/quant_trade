<!--大盘指数看板-->
<script>
export default {
  name: "IndexBoard",
  data() {
    return {
      indices: [
        {
          code: "000001.SH",
          name: "上证指数",
          value: 3254.87,
          change: 0.56,
          changePercent: 0.017,
          high: 3268.45,
          low: 3245.21,
          volume: "3.42亿",
          amount: "4235.68亿"
        },
        {
          code: "399001.SZ",
          name: "深证成指",
          value: 12045.32,
          change: -0.23,
          changePercent: -0.002,
          high: 12120.45,
          low: 12010.78,
          volume: "2.87亿",
          amount: "3876.54亿"
        },
        {
          code: "399006.SZ",
          name: "创业板指",
          value: 2654.21,
          change: 1.24,
          changePercent: 0.047,
          high: 2678.32,
          low: 2645.78,
          volume: "1.23亿",
          amount: "1876.43亿"
        },
        {
          code: "000300.SH",
          name: "沪深300",
          value: 4156.78,
          change: 0.78,
          changePercent: 0.019,
          high: 4178.45,
          low: 4145.32,
          volume: "1.98亿",
          amount: "2876.54亿"
        },
        {
          code: "000688.SH",
          name: "科创50",
          value: 1124.56,
          change: 2.15,
          changePercent: 0.191,
          high: 1135.78,
          low: 1118.45,
          volume: "0.78亿",
          amount: "876.54亿"
        }
      ],
      lastUpdate: new Date(),
      selectedIndex: null,
      isRefreshing: false
    };
  },
  methods: {
    refreshData() {
      this.isRefreshing = true;

      // 模拟数据刷新
      setTimeout(() => {
        this.indices = this.indices.map(index => {
          // 模拟价格波动
          const fluctuation = (Math.random() - 0.5) * 0.5;
          const newValue = index.value * (1 + fluctuation);
          const change = newValue - index.value;
          const changePercent = (change / index.value) * 100;

          return {
            ...index,
            value: parseFloat(newValue.toFixed(2)),
            change: parseFloat(change.toFixed(2)),
            changePercent: parseFloat(changePercent.toFixed(2))
          };
        });

        this.lastUpdate = new Date();
        this.isRefreshing = false;
      }, 1000);
    },
    selectIndex(index) {
      this.selectedIndex = this.selectedIndex?.code === index.code ? null : index;
    },
    formatTime(date) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
  }
};
</script>

<template>
  <div class="index-board">
    <div class="board-header">
      <h3>大盘指数</h3>
      <div class="header-actions">
        <span class="update-time">更新: {{ formatTime(lastUpdate) }}</span>
        <el-button
          size="small"
          :icon="isRefreshing ? 'el-icon-loading' : 'el-icon-refresh'"
          @click="refreshData"
          :disabled="isRefreshing"
        >
          {{ isRefreshing ? '更新中...' : '刷新' }}
        </el-button>
      </div>
    </div>

    <div class="index-list">
      <div
        v-for="(index, idx) in indices"
        :key="idx"
        class="index-item"
        :class="{ 'selected': selectedIndex?.code === index.code }"
        @click="selectIndex(index)"
      >
        <div class="index-name">{{ index.name }}</div>
        <div class="index-value">{{ index.value.toLocaleString() }}</div>
        <div
          class="index-change"
          :class="index.change >= 0 ? 'positive' : 'negative'"
        >
          <span v-if="index.change >= 0">+</span>{{ index.change.toFixed(2) }}
          <span class="change-percent">({{ index.changePercent >= 0 ? '+' : '' }}{{ index.changePercent.toFixed(2) }}%)</span>
        </div>
      </div>
    </div>

    <div v-if="selectedIndex" class="index-detail">
      <div class="detail-header">
        <h4>{{ selectedIndex.name }} ({{ selectedIndex.code }})</h4>
      </div>
      <div class="detail-content">
        <div class="detail-item">
          <span class="label">最高:</span>
          <span class="value">{{ selectedIndex.high.toLocaleString() }}</span>
        </div>
        <div class="detail-item">
          <span class="label">最低:</span>
          <span class="value">{{ selectedIndex.low.toLocaleString() }}</span>
        </div>
        <div class="detail-item">
          <span class="label">成交量:</span>
          <span class="value">{{ selectedIndex.volume }}</span>
        </div>
        <div class="detail-item">
          <span class="label">成交额:</span>
          <span class="value">{{ selectedIndex.amount }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.index-board {
  background: linear-gradient(135deg, #1a2439, #152136);
  border-radius: 12px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
  padding: 20px;
  font-family: 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  border: 1px solid #2a3a5a;
  transition: all 0.3s ease;
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #2a3a5a;
}

.board-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #64b5f6;
  letter-spacing: 1px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 15px;
}

.update-time {
  font-size: 13px;
  color: #9da8b8;
}

.index-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
}

.index-item {
  background: rgba(26, 39, 60, 0.6);
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid #2a3a5a;
  position: relative;
  overflow: hidden;
}

.index-item:hover {
  background: rgba(32, 48, 76, 0.7);
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.index-item.selected {
  background: rgba(25, 55, 100, 0.7);
  border-color: #3a6bc5;
}

.index-item.selected::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  background: #3a6bc5;
}

.index-name {
  font-size: 14px;
  color: #9da8b8;
  margin-bottom: 8px;
  font-weight: 500;
}

.index-value {
  font-size: 22px;
  font-weight: 700;
  color: #e0e0e0;
  margin-bottom: 5px;
  letter-spacing: 1px;
}

.index-change {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.positive {
  color: #f44336;
}

.negative {
  color: #4caf50;
}

.change-percent {
  margin-left: 5px;
  font-size: 12px;
}

.index-detail {
  margin-top: 20px;
  padding-top: 15px;
  border-top: 1px solid #2a3a5a;
  animation: fadeIn 0.3s ease;
}

.detail-header {
  margin-bottom: 15px;
}

.detail-header h4 {
  margin: 0;
  font-size: 16px;
  color: #64b5f6;
}

.detail-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: rgba(26, 39, 60, 0.5);
  border-radius: 6px;
  font-size: 14px;
}

.label {
  color: #9da8b8;
}

.value {
  color: #e0e0e0;
  font-weight: 500;
}

/* 动画效果 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .index-list {
    grid-template-columns: repeat(2, 1fr);
  }

  .detail-content {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 480px) {
  .board-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .header-actions {
    width: 100%;
    justify-content: space-between;
  }

  .index-list {
    grid-template-columns: 1fr;
  }
}
</style>