<!--订单表单-->
<!-- src/components/events/OrderForm.vue -->
<template>
  <div class="order-form">
    <h2><i class="fas fa-file-invoice-dollar"></i> 交易订单</h2>

    <div class="form-container">
      <div class="form-group">
        <label for="symbol">证券代码</label>
        <div class="symbol-input">
          <input
            type="text"
            v-model="symbol"
            placeholder="输入股票代码"
            @input="searchStock"
          >
          <div v-if="currentStock" class="stock-info">
            <span class="name">{{ currentStock.name }}</span>
            <span class="price">{{ currentStock.price }}</span>
            <span class="change" :class="currentStock.change >= 0 ? 'positive' : 'negative'">
              {{ currentStock.change >= 0 ? '+' : '' }}{{ currentStock.change }}%
            </span>
          </div>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="direction-buttons">交易方向</label>
          <div class="direction-buttons">
            <button
              :class="{'active': direction === 'buy'}"
              @click="direction = 'buy'"
            >
              <i class="fas fa-arrow-up"></i> 买入
            </button>
            <button
              :class="{'active': direction === 'sell'}"
              @click="direction = 'sell'"
            >
              <i class="fas fa-arrow-down"></i> 卖出
            </button>
          </div>
        </div>

        <div class="form-group">
          <label for="orderType">订单类型</label>
          <select v-model="orderType">
            <option value="limit">限价单</option>
            <option value="market">市价单</option>
            <option value="stop">止损单</option>
            <option value="stop_limit">止损限价单</option>
          </select>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="price">价格</label>
          <input
            type="number"
            v-model="price"
            :disabled="orderType === 'market'"
            step="0.01"
            min="0"
          >
        </div>

        <div class="form-group">
          <label for="quantity">数量</label>
          <input
            type="number"
            v-model="quantity"
            min="100"
            step="100"
          >
        </div>
      </div>

      <div v-if="orderType === 'stop' || orderType === 'stop_limit'" class="form-group">
        <label for="triggerPrice">触发价格</label>
        <input type="number" v-model="triggerPrice" step="0.01" min="0">
      </div>

      <div class="form-group">
        <label for="amount-display">交易金额</label>
        <div class="amount-display">
          ¥{{ orderAmount.toLocaleString() }}
        </div>
      </div>

      <div class="form-actions">
        <button class="btn reset" @click="resetForm">
          <i class="fas fa-redo"></i> 重置
        </button>
        <button class="btn preview" @click="previewOrder">
          <i class="fas fa-eye"></i> 预览订单
        </button>
        <button class="btn submit" @click="submitOrder">
          <i class="fas fa-paper-plane"></i> 提交订单
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "OrderForm",
  data() {
    return {
      symbol: "",
      currentStock: null,
      direction: "buy",
      orderType: "limit",
      price: 0,
      quantity: 100,
      triggerPrice: 0,
      allStocks: [
        { symbol: "600519.SH", name: "贵州茅台", price: 1685.50, change: 1.25 },
        { symbol: "601318.SH", name: "中国平安", price: 48.25, change: -0.52 },
        { symbol: "600036.SH", name: "招商银行", price: 32.60, change: 0.92 },
        { symbol: "000333.SZ", name: "美的集团", price: 55.80, change: 2.10 },
        { symbol: "601888.SH", name: "中国中免", price: 102.40, change: -1.30 },
      ]
    };
  },
  computed: {
    orderAmount() {
      if (!this.price || !this.quantity) return 0;
      return this.price * this.quantity;
    }
  },
  watch: {
    orderType(newVal) {
      if (newVal === 'market') {
        this.price = 0;
      } else if (!this.price && this.currentStock) {
        this.price = this.currentStock.price;
      }
    },
    symbol(newVal) {
      if (!newVal) {
        this.currentStock = null;
      }
    }
  },
  methods: {
    searchStock() {
      if (!this.symbol) {
        this.currentStock = null;
        return;
      }

      const stock = this.allStocks.find(s =>
        s.symbol.toLowerCase() === this.symbol.toLowerCase()
      );

      if (stock) {
        this.currentStock = stock;
        if (this.orderType !== 'market' && !this.price) {
          this.price = stock.price;
        }
      } else {
        this.currentStock = null;
      }
    },
    resetForm() {
      this.symbol = "";
      this.currentStock = null;
      this.direction = "buy";
      this.orderType = "limit";
      this.price = 0;
      this.quantity = 100;
      this.triggerPrice = 0;
    },
    previewOrder() {
      if (!this.validateForm()) return;

      const orderDetails = {
        symbol: this.symbol,
        name: this.currentStock.name,
        direction: this.direction === "buy" ? "买入" : "卖出",
        type: this.getOrderTypeName(),
        price: this.orderType === "market" ? "市价" : this.price,
        quantity: this.quantity,
        amount: this.orderAmount
      };

      if (this.orderType === "stop" || this.orderType === "stop_limit") {
        orderDetails.triggerPrice = this.triggerPrice;
      }

      this.$emit('preview-order', orderDetails);
    },
    submitOrder() {
      if (!this.validateForm()) return;

      // 模拟订单提交
      this.$message.success('订单提交成功');

      // 重置表单
      this.resetForm();
    },
    validateForm() {
      if (!this.symbol || !this.currentStock) {
        this.$message.error('请选择有效的股票');
        return false;
      }

      if (this.orderType !== "market" && !this.price) {
        this.$message.error('请输入价格');
        return false;
      }

      if (!this.quantity || this.quantity <= 0) {
        this.$message.error('请输入有效的数量');
        return false;
      }

      if ((this.orderType === "stop" || this.orderType === "stop_limit") && !this.triggerPrice) {
        this.$message.error('请输入触发价格');
        return false;
      }

      return true;
    },
    getOrderTypeName() {
      const types = {
        'limit': '限价单',
        'market': '市价单',
        'stop': '止损单',
        'stop_limit': '止损限价单'
      };
      return types[this.orderType];
    }
  }
};
</script>

<style scoped>
.order-form {
  background: rgba(16, 33, 59, 0.8);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(64, 158, 255, 0.2);
  height: 100%;
}

h2 {
  font-size: 1.5rem;
  color: #64b5f6;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.form-container {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label {
  color: #a8c7ff;
  font-size: 0.95rem;
}

input, select {
  padding: 10px 12px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #e0e7ff;
  font-size: 1rem;
  outline: none;
  width: 100%;
}

input:focus, select:focus {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

.symbol-input {
  position: relative;
}

.stock-info {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.9rem;
}

.stock-info .name {
  color: #a8c7ff;
}

.stock-info .price {
  font-weight: 500;
}

.stock-info .change {
  font-weight: 500;
}

.stock-info .positive {
  color: #5cdd8b;
}

.stock-info .negative {
  color: #ff6b6b;
}

.direction-buttons {
  display: flex;
  gap: 10px;
}

.direction-buttons button {
  flex: 1;
  padding: 10px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  color: #a8c7ff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  transition: all 0.3s;
}

.direction-buttons button.active {
  background: rgba(64, 158, 255, 0.2);
  border-color: #409eff;
  color: #e0e7ff;
}

.direction-buttons button:nth-child(1).active {
  background: rgba(92, 221, 139, 0.2);
  border-color: #5cdd8b;
  color: #5cdd8b;
}

.direction-buttons button:nth-child(2).active {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
  color: #ff6b6b;
}

.amount-display {
  padding: 10px 12px;
  background: rgba(16, 33, 59, 0.7);
  border: 1px solid rgba(64, 158, 255, 0.3);
  border-radius: 6px;
  font-size: 1.1rem;
  font-weight: 600;
  color: #64b5f6;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}

.form-actions .btn {
  flex: 1;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 500;
  transition: all 0.3s;
}

.btn.reset {
  background: rgba(255, 107, 107, 0.1);
  border: 1px solid rgba(255, 107, 107, 0.3);
  color: #ff6b6b;
}

.btn.reset:hover {
  background: rgba(255, 107, 107, 0.2);
  border-color: #ff6b6b;
}

.btn.preview {
  background: rgba(255, 184, 108, 0.1);
  border: 1px solid rgba(255, 184, 108, 0.3);
  color: #ffb86c;
}

.btn.preview:hover {
  background: rgba(255, 184, 108, 0.2);
  border-color: #ffb86c;
}

.btn.submit {
  background: rgba(92, 221, 139, 0.1);
  border: 1px solid rgba(92, 221, 139, 0.3);
  color: #5cdd8b;
}

.btn.submit:hover {
  background: rgba(92, 221, 139, 0.2);
  border-color: #5cdd8b;
}
</style>