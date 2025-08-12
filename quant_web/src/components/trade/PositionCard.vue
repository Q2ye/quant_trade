<!--持仓卡片-->
<!-- src/components/trade/PositionCard.vue -->
<template>
  <div class="position-card" :class="{'high-value': position.marketValue > 100000}">
    <div class="card-header">
      <div class="symbol">{{ position.symbol }}</div>
      <div class="name">{{ position.name }}</div>
    </div>

    <div class="card-content">
      <div class="position-data">
        <div class="data-item">
          <div class="label">持仓数量</div>
          <div class="value">{{ position.quantity.toLocaleString() }}</div>
        </div>
        <div class="data-item">
          <div class="label">可用数量</div>
          <div class="value">{{ position.available.toLocaleString() }}</div>
        </div>
      </div>

      <div class="position-data">
        <div class="data-item">
          <div class="label">成本价</div>
          <div class="value">¥{{ position.costPrice.toFixed(2) }}</div>
        </div>
        <div class="data-item">
          <div class="label">当前价</div>
          <div class="value">¥{{ position.currentPrice.toFixed(2) }}</div>
        </div>
      </div>

      <div class="position-data">
        <div class="data-item">
          <div class="label">涨跌幅</div>
          <div class="value" :class="position.change >= 0 ? 'positive' : 'negative'">
            {{ position.change >= 0 ? '+' : '' }}{{ position.change.toFixed(2) }}%
          </div>
        </div>
        <div class="data-item">
          <div class="label">持仓价值</div>
          <div class="value">¥{{ position.marketValue.toLocaleString() }}</div>
        </div>
      </div>

      <div class="position-data">
        <div class="data-item">
          <div class="label">浮动盈亏</div>
          <div class="value" :class="position.profit >= 0 ? 'positive' : 'negative'">
            {{ position.profit >= 0 ? '+' : '' }}¥{{ position.profit.toLocaleString() }}
          </div>
        </div>
        <div class="data-item">
          <div class="label">盈亏比例</div>
          <div class="value" :class="position.profitRatio >= 0 ? 'positive' : 'negative'">
            {{ position.profitRatio >= 0 ? '+' : '' }}{{ position.profitRatio.toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>

    <div class="card-actions">
      <button class="btn buy" @click="tradePosition('buy')">
        <i class="fas fa-plus"></i> 加仓
      </button>
      <button class="btn sell" @click="tradePosition('sell')">
        <i class="fas fa-minus"></i> 减仓
      </button>
      <button class="btn close" @click="closePosition">
        <i class="fas fa-times"></i> 平仓
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: "PositionCard",
  props: {
    position: {
      type: Object,
      required: true
    }
  },
  methods: {
    tradePosition(direction) {
      this.$emit('trade-position', {
        symbol: this.position.symbol,
        direction: direction
      });
    },
    closePosition() {
      this.$emit('close-position', this.position.symbol);
    }
  }
};
</script>

<style scoped>
.position-card {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 10px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  padding: 15px;
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.position-card.high-value::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  border-width: 0 25px 25px 0;
  border-style: solid;
  border-color: transparent #ffb86c transparent transparent;
}

.position-card.high-value::after {
  content: 'VIP';
  position: absolute;
  top: 2px;
  right: 2px;
  font-size: 10px;
  font-weight: bold;
  color: #1a2a4c;
  transform: rotate(45deg);
  width: 25px;
  text-align: center;
}

.position-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
  border-color: rgba(64, 158, 255, 0.5);
}

.card-header {
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
  padding-bottom: 10px;
  margin-bottom: 10px;
}

.symbol {
  font-size: 1.2rem;
  font-weight: 600;
  color: #64b5f6;
}

.name {
  font-size: 0.9rem;
  color: #a8c7ff;
}

.position-data {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.data-item {
  background: rgba(16, 33, 59, 0.7);
  border-radius: 6px;
  padding: 8px;
}

.label {
  font-size: 0.8rem;
  color: #a8c7ff;
  margin-bottom: 3px;
}

.value {
  font-size: 0.95rem;
  font-weight: 500;
}

.positive {
  color: #5cdd8b;
}

.negative {
  color: #ff6b6b;
}

.card-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 10px;
}

.btn {
  padding: 6px;
  border-radius: 4px;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn.buy {
  background: rgba(92, 221, 139, 0.1);
  border: 1px solid rgba(92, 221, 139, 0.3);
  color: #5cdd8b;
}

.btn.buy:hover {
  background: rgba(92, 221, 139, 0.2);
  border-color: #5cdd8b;
}

.btn.sell {
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.btn.sell:hover {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
}

.btn.close {
  background: rgba(255, 184, 108, 0.1);
  border: 1px solid rgba(255, 184, 108, 0.3);
  color: #ffb86c;
}

.btn.close:hover {
  background: rgba(255, 184, 108, 0.2);
  border-color: #ffb86c;
}
</style>