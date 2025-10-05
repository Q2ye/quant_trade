<template>
  <div class="position-list">
    <div v-if="positions.length === 0" class="empty-state">
      <i class="fas fa-chart-line"></i>
      <p>暂无持仓</p>
    </div>

    <div v-else class="positions-container">
      <div
        class="position-item"
        v-for="position in positions"
        :key="position.symbol"
        @click="$emit('select-symbol', position.symbol)"
      >
        <div class="position-header">
          <span class="symbol">{{ position.symbol }}</span>
          <span class="name">{{ position.name }}</span>
        </div>

        <div class="position-details">
          <div class="detail-row">
            <span>持仓:</span>
            <span>{{ position.volume }} 股</span>
          </div>
          <div class="detail-row">
            <span>成本:</span>
            <span>¥{{ position.costPrice }}</span>
          </div>
          <div class="detail-row">
            <span>现价:</span>
            <span>¥{{ position.currentPrice }}</span>
          </div>
          <div class="detail-row">
            <span>盈亏:</span>
            <span :class="getProfitClass(position)">
              {{ calculateProfit(position) }}%
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "PositionList",
  props: {
    positions: {
      type: Array,
      default: () => []
    }
  },
  methods: {
    calculateProfit(position) {
      const profit = ((position.currentPrice - position.costPrice) / position.costPrice * 100);
      return profit.toFixed(2);
    },

    getProfitClass(position) {
      const profit = this.calculateProfit(position);
      return parseFloat(profit) >= 0 ? 'profit-positive' : 'profit-negative';
    }
  }
};
</script>

<style scoped>
.position-list {
  height: 100%;
  overflow-y: auto;
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

.positions-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.position-item {
  background: rgba(16, 33, 59, 0.6);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.3s;
}

.position-item:hover {
  border-color: rgba(64, 158, 255, 0.4);
  background: rgba(16, 33, 59, 0.8);
}

.position-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.symbol {
  font-weight: 600;
  color: #e0e7ff;
}

.name {
  color: #a8c7ff;
  font-size: 0.9rem;
}

.position-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  font-size: 0.85rem;
}

.detail-row {
  display: flex;
  justify-content: space-between;
}

.detail-row span:first-child {
  color: #a8c7ff;
}

.detail-row span:last-child {
  color: #e0e7ff;
  font-weight: 500;
}

.profit-positive {
  color: #5cdd8b;
}

.profit-negative {
  color: #ff6b6b;
}
</style>