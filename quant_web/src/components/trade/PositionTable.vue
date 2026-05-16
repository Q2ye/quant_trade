<template>
  <div class="position-table">
    <div class="table-header">
      <div class="header-item">代码</div>
      <div class="header-item">名称</div>
      <div class="header-item">持仓</div>
      <div class="header-item">成本</div>
      <div class="header-item">现价</div>
      <div class="header-item">盈亏</div>
      <div class="header-item">盈亏率</div>
      <div class="header-item">市值</div>
    </div>

    <div class="table-body">
      <div
        v-for="(position, index) in positions"
        :key="index"
        class="table-row"
        :class="{
          'profit-row': position.profit > 0,
          'loss-row': position.profit < 0,
        }"
      >
        <div class="row-item">{{ position.code }}</div>
        <div class="row-item">{{ position.name }}</div>
        <div class="row-item">{{ position.volume }}</div>
        <div class="row-item">{{ position.cost.toFixed(2) }}</div>
        <div class="row-item">{{ position.price.toFixed(2) }}</div>
        <div
          class="row-item"
          :class="{ profit: position.profit > 0, loss: position.profit < 0 }"
        >
          {{ position.profit > 0 ? "+" : "" }}{{ position.profit.toFixed(2) }}
        </div>
        <div
          class="row-item"
          :class="{
            profit: position.profitRate > 0,
            loss: position.profitRate < 0,
          }"
        >
          {{ position.profitRate > 0 ? "+" : ""
          }}{{ position.profitRate.toFixed(2) }}%
        </div>
        <div class="row-item">{{ position.value.toFixed(2) }}</div>
      </div>
    </div>

    <div class="table-footer">
      <div>总市值: {{ totalValue.toFixed(2) }}</div>
      <div>
        总盈亏:
        <span :class="{ profit: totalProfit > 0, loss: totalProfit < 0 }">
          {{ totalProfit > 0 ? "+" : "" }}{{ totalProfit.toFixed(2) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "PositionTable",
  props: {
    positions: {
      type: Array,
      default: () => [
        {
          code: "600519.SH",
          name: "贵州茅台",
          volume: 100,
          cost: 1700.25,
          price: 1800.5,
          value: 180050,
          profit: 10025,
          profitRate: 5.89,
        },
        {
          code: "000001.SZ",
          name: "平安银行",
          volume: 500,
          cost: 15.3,
          price: 14.8,
          value: 7400,
          profit: -250,
          profitRate: -3.27,
        },
      ],
    },
  },
  computed: {
    totalValue() {
      return this.positions.reduce((sum, pos) => sum + pos.value, 0);
    },
    totalProfit() {
      return this.positions.reduce((sum, pos) => sum + pos.profit, 0);
    },
  },
};
</script>

<style scoped>
.position-table {
  font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
  font-size: 12px;
  color: #333;
}

.table-header,
.table-row {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr 1fr 1fr 1fr 1fr 1.2fr;
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

.profit {
  color: #f56c6c;
  font-weight: bold;
}

.loss {
  color: #67c23a;
  font-weight: bold;
}

.profit-row {
  background-color: rgba(247, 213, 213, 0.1);
}

.loss-row {
  background-color: rgba(213, 234, 213, 0.1);
}

.table-footer {
  display: flex;
  justify-content: space-between;
  padding: 10px 15px;
  background-color: #f5f7fa;
  font-weight: bold;
  border-top: 1px solid #ddd;
}
</style>
