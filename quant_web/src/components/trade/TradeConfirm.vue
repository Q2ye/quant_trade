<!--交易确认弹窗-->
<!-- src/components/events/TradeConfirm.vue -->
<template>
  <div class="trade-confirm" v-if="visible">
    <div class="confirm-overlay" @click="cancel"></div>

    <div class="confirm-dialog">
      <div class="dialog-header">
        <h3><i class="fas fa-check-circle"></i> 交易确认</h3>
        <button class="close-btn" @click="cancel">
          <i class="fas fa-times"></i>
        </button>
      </div>

      <div class="dialog-content">
        <div class="trade-summary">
          <div class="summary-item">
            <div class="label">交易方向:</div>
            <div class="value" :class="order.direction === '买入' ? 'buy' : 'sell'">
              {{ order.direction }}
            </div>
          </div>
          <div class="summary-item">
            <div class="label">证券代码:</div>
            <div class="value">{{ order.symbol }}</div>
          </div>
          <div class="summary-item">
            <div class="label">证券名称:</div>
            <div class="value">{{ order.name }}</div>
          </div>
          <div class="summary-item">
            <div class="label">订单类型:</div>
            <div class="value">{{ order.type }}</div>
          </div>
          <div class="summary-item">
            <div class="label">价格:</div>
            <div class="value">{{ order.price }}</div>
          </div>
          <div class="summary-item">
            <div class="label">数量:</div>
            <div class="value">{{ order.quantity }}</div>
          </div>
          <div v-if="order.triggerPrice" class="summary-item">
            <div class="label">触发价格:</div>
            <div class="value">{{ order.triggerPrice }}</div>
          </div>
          <div class="summary-item highlight">
            <div class="label">交易金额:</div>
            <div class="value">¥{{ order.amount.toLocaleString() }}</div>
          </div>
        </div>

        <div class="account-info">
          <div class="info-item">
            <div class="label">可用资金:</div>
            <div class="value">¥1,250,680.50</div>
          </div>
          <div class="info-item">
            <div class="label">交易后资金:</div>
            <div class="value" :class="order.direction === '买入' ? 'negative' : 'positive'">
              {{ order.direction === '买入' ? '¥' + (1250680.50 - order.amount).toLocaleString() : '¥' + (1250680.50 + order.amount).toLocaleString() }}
            </div>
          </div>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="btn cancel" @click="cancel">
          <i class="fas fa-times"></i> 取消
        </button>
        <button class="btn confirm" @click="confirm">
          <i class="fas fa-check"></i> 确认交易
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "TradeConfirm",
  props: {
    visible: Boolean,
    order: Object
  },
  methods: {
    cancel() {
      this.$emit('cancel');
    },
    confirm() {
      this.$emit('confirm', this.order);
      this.$message.success('交易指令已发送');
    }
  }
};
</script>

<style scoped>
.trade-confirm {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.confirm-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(5px);
}

.confirm-dialog {
  position: relative;
  width: 500px;
  background: linear-gradient(135deg, #1a2a4c 0%, #0c1a2e 100%);
  border-radius: 12px;
  border: 1px solid rgba(64, 158, 255, 0.5);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  overflow: hidden;
  z-index: 1001;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid rgba(64, 158, 255, 0.2);
}

.dialog-header h3 {
  font-size: 1.3rem;
  color: #64b5f6;
  display: flex;
  align-items: center;
  gap: 10px;
}

.close-btn {
  background: none;
  border: none;
  color: #a8c7ff;
  font-size: 1.2rem;
  cursor: pointer;
  transition: color 0.3s;
}

.close-btn:hover {
  color: #ff6b6b;
}

.dialog-content {
  padding: 20px;
  max-height: 70vh;
  overflow-y: auto;
}

.trade-summary {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  margin-bottom: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.summary-item {
  display: flex;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(64, 158, 255, 0.1);
}

.summary-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.summary-item.highlight {
  padding-top: 10px;
  margin-top: 10px;
  border-top: 1px solid rgba(64, 158, 255, 0.3);
}

.label {
  width: 100px;
  color: #a8c7ff;
  font-size: 0.95rem;
}

.value {
  flex: 1;
  font-weight: 500;
  color: #e0e7ff;
}

.value.buy {
  color: #5cdd8b;
}

.value.sell {
  color: #ff6b6b;
}

.highlight .value {
  font-size: 1.2rem;
  font-weight: 700;
  color: #64b5f6;
}

.account-info {
  background: rgba(24, 50, 90, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.info-item {
  display: flex;
  margin-bottom: 10px;
}

.info-item:last-child {
  margin-bottom: 0;
}

.info-item .value.positive {
  color: #5cdd8b;
}

.info-item .value.negative {
  color: #ff6b6b;
}

.dialog-footer {
  display: flex;
  padding: 15px 20px;
  border-top: 1px solid rgba(64, 158, 255, 0.2);
}

.btn {
  flex: 1;
  padding: 12px;
  border-radius: 6px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn.cancel {
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
  margin-right: 10px;
}

.btn.cancel:hover {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
}

.btn.confirm {
  background: rgba(92, 221, 139, 0.1);
  border: 1px solid rgba(92, 221, 139, 0.3);
  color: #5cdd8b;
}

.btn.confirm:hover {
  background: rgba(92, 221, 139, 0.2);
  border-color: #5cdd8b;
}
</style>