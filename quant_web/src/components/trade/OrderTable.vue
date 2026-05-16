<template>
  <div class="order-table">
    <div class="table-header">
      <div class="header-item">代码</div>
      <div class="header-item">名称</div>
      <div class="header-item">方向</div>
      <div class="header-item">价格</div>
      <div class="header-item">数量</div>
      <div class="header-item">金额</div>
      <div class="header-item">时间</div>
      <div class="header-item">状态</div>
    </div>

    <div class="table-body">
      <div
        v-for="(order, index) in orders"
        :key="index"
        class="table-row"
        :class="{
          'buy-row': order.direction === 'B',
          'sell-row': order.direction === 'S',
        }"
      >
        <div class="row-item">{{ order.code }}</div>
        <div class="row-item">{{ order.name }}</div>
        <div class="row-item">
          <span v-if="order.direction === 'B'" class="buy-tag">买</span>
          <span v-else class="sell-tag">卖</span>
        </div>
        <div class="row-item">{{ order.price.toFixed(2) }}</div>
        <div class="row-item">{{ order.volume }}</div>
        <div class="row-item">
          {{ (order.price * order.volume).toFixed(2) }}
        </div>
        <div class="row-item">{{ formatTime(order.time) }}</div>
        <div class="row-item">
          <span
            :class="{
              'status-pending': order.status === 'P',
              'status-filled': order.status === 'F',
              'status-cancelled': order.status === 'C',
            }"
          >
            {{ statusMap[order.status] }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "OrderTable",
  props: {
    orders: {
      type: Array,
      default: () => [
        {
          code: "600519.SH",
          name: "贵州茅台",
          direction: "B",
          price: 1800.5,
          volume: 100,
          time: new Date(),
          status: "F",
        },
        {
          code: "000858.SZ",
          name: "五粮液",
          direction: "S",
          price: 210.25,
          volume: 200,
          time: new Date(),
          status: "P",
        },
      ],
    },
  },
  data() {
    return {
      statusMap: {
        P: "已报",
        F: "成交",
        C: "撤单",
      },
    };
  },
  methods: {
    formatTime(date) {
      return `${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}:${String(date.getSeconds()).padStart(2, "0")}`;
    },
  },
};
</script>

<style scoped>
.order-table {
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-size: 12px;
  color: #333;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 2fr 0.8fr 1fr 1fr 1.2fr 1.5fr 0.8fr;
  padding: 8px 5px;
  border-bottom: 1px solid #eee;
}

.table-header {
  font-weight: bold;
  background-color: #f5f7fa;
}

.table-body {
  max-height: 300px;
  overflow-y: auto;
}

.row-item {
  padding: 4px 2px;
  text-align: center;
}

.buy-tag {
  background-color: #f56c6c;
  color: white;
  padding: 2px 5px;
  border-radius: 3px;
}

.sell-tag {
  background-color: #67c23a;
  color: white;
  padding: 2px 5px;
  border-radius: 3px;
}

.buy-row {
  background-color: rgba(247, 213, 213, 0.1);
}

.sell-row {
  background-color: rgba(213, 234, 213, 0.1);
}

.status-pending {
  color: #e6a23c;
}

.status-filled {
  color: #67c23a;
}

.status-cancelled {
  color: #909399;
}
</style>
