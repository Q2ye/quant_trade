<!-- src/components/trade/OrderList.vue -->
<template>
  <div class="order-list">
    <div v-if="orders.length === 0" class="empty-state">
      <i class="fas fa-clipboard-list"></i>
      <p>暂无委托订单</p>
    </div>

    <div v-else class="orders-container">
      <div class="order-item" v-for="order in orders" :key="order.id">
        <div class="order-header">
          <span class="symbol">{{ order.symbol }}</span>
          <span class="direction" :class="order.direction">
            {{ order.direction === 'buy' ? '买入' : '卖出' }}
          </span>
          <el-tag
            size="mini"
            :type="getStatusType(order.status)"
            class="status-tag"
          >
            {{ getStatusText(order.status) }}
          </el-tag>
        </div>

        <div class="order-details">
          <div class="detail-row">
            <span class="label">类型:</span>
            <span class="value">{{ getOrderTypeText(order.type) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">价格:</span>
            <span class="value">
              {{ order.type === 'market' ? '市价' : `¥${order.price}` }}
            </span>
          </div>
          <div class="detail-row">
            <span class="label">数量:</span>
            <span class="value">{{ order.volume }} 股</span>
          </div>
          <div class="detail-row">
            <span class="label">金额:</span>
            <span class="value amount">
              ¥{{ calculateAmount(order).toLocaleString() }}
            </span>
          </div>
        </div>

        <div class="order-actions">
          <el-button
            v-if="order.status === 'submitted' || order.status === 'partial_filled'"
            size="mini"
            type="danger"
            plain
            @click="handleCancel(order.id)"
          >
            <i class="fas fa-times"></i>
            撤单
          </el-button>
          <span v-else class="action-text">{{ getActionText(order.status) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "OrderList",
  props: {
    orders: {
      type: Array,
      default: () => []
    }
  },
  methods: {
    getStatusType(status) {
      const typeMap = {
        'submitted': 'primary',
        'partial_filled': 'warning',
        'filled': 'success',
        'cancelled': 'info',
        'rejected': 'danger'
      };
      return typeMap[status] || 'info';
    },

    getStatusText(status) {
      const textMap = {
        'submitted': '已报',
        'partial_filled': '部成',
        'filled': '已成',
        'cancelled': '已撤',
        'rejected': '废单'
      };
      return textMap[status] || status;
    },

    getOrderTypeText(type) {
      const typeMap = {
        'limit': '限价',
        'market': '市价',
        'stop': '止损',
        'stop_limit': '止损限价'
      };
      return typeMap[type] || type;
    },

    getActionText(status) {
      const textMap = {
        'filled': '已完成',
        'cancelled': '已取消',
        'rejected': '订单被拒'
      };
      return textMap[status] || '';
    },

    calculateAmount(order) {
      if (order.type === 'market' || !order.price) return 0;
      return order.price * order.volume;
    },

    handleCancel(orderId) {
      this.$confirm('确定要撤销此订单吗?', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        this.$emit('cancel-order', orderId);
        this.$message.success('撤单指令已发送');
      }).catch(() => {
        // 用户取消操作
      });
    }
  }
};
</script>

<style scoped>
.order-list {
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

.empty-state i {
  font-size: 3rem;
  margin-bottom: 10px;
}

.orders-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.order-item {
  background: rgba(16, 33, 59, 0.6);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 8px;
  padding: 12px;
  transition: all 0.3s;
}

.order-item:hover {
  border-color: rgba(64, 158, 255, 0.4);
  background: rgba(16, 33, 59, 0.8);
}

.order-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.symbol {
  font-weight: 600;
  color: #e0e7ff;
  font-size: 1rem;
}

.direction {
  font-size: 0.85rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.direction.buy {
  background: rgba(92, 221, 139, 0.2);
  color: #5cdd8b;
  border: 1px solid rgba(92, 221, 139, 0.3);
}

.direction.sell {
  background: rgba(255, 107, 107, 0.2);
  color: #ff6b6b;
  border: 1px solid rgba(255, 107, 107, 0.3);
}

.status-tag {
  margin-left: auto;
}

.order-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 10px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.label {
  color: #a8c7ff;
  font-size: 0.85rem;
}

.value {
  color: #e0e7ff;
  font-size: 0.85rem;
  font-weight: 500;
}

.amount {
  color: #64b5f6;
  font-weight: 600;
}

.order-actions {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid rgba(64, 158, 255, 0.1);
  padding-top: 8px;
}

.action-text {
  color: #a8c7ff;
  font-size: 0.8rem;
  font-style: italic;
}

/* 滚动条样式 */
.order-list::-webkit-scrollbar {
  width: 6px;
}

.order-list::-webkit-scrollbar-track {
  background: rgba(16, 33, 59, 0.3);
  border-radius: 3px;
}

.order-list::-webkit-scrollbar-thumb {
  background: rgba(64, 158, 255, 0.3);
  border-radius: 3px;
}

.order-list::-webkit-scrollbar-thumb:hover {
  background: rgba(64, 158, 255, 0.5);
}
</style>