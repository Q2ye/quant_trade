<!--信号监控组件-->
<script>
import DataTable from "../data/DataTable.vue";

export default {
  name: "SignalMonitor",
  components: { DataTable },
  props: {
    signals: {
      type: Array,
      default: () => [],
    },
  },
  data() {
    return {
      columns: [
        { prop: "symbol", label: "代码", width: "100px" },
        { prop: "name", label: "名称", width: "150px" },
        {
          prop: "signal",
          label: "信号",
          width: "100px",
          color: (row) => (row.signal === "BUY" ? "#f56c6c" : "#67c23a"),
        },
        {
          prop: "price",
          label: "当前价",
          width: "120px",
          formatter: (row, column, value) => value.toFixed(2),
        },
        {
          prop: "change_percent",
          label: "涨跌幅",
          width: "120px",
          color: (row) => {
            const colorMap = {
              up: "#f56c6c",
              down: "#67c23a",
              flat: "",
            };
            const { change_percent } = row;
            if (change_percent > 0) return colorMap.up;
            if (change_percent < 0) return colorMap.down;
            return colorMap.flat;
          },
          formatter: (row, column, value) =>
            (value > 0 ? "+" : "") + value.toFixed(2) + "%",
        },
        { prop: "reason", label: "信号原因", minWidth: "200px" },
        {
          prop: "timestamp",
          label: "时间",
          width: "180px",
          formatter: (row, column, value) => new Date(value).toLocaleString(),
        },
      ],
    };
  },
};
</script>

<template>
  <div class="signal-monitor">
    <div class="header">
      <h3>实时交易信号</h3>
      <div class="stats">
        <span class="buy-signal">买入: {{ buyCount }}</span>
        <span class="sell-signal">卖出: {{ sellCount }}</span>
      </div>
    </div>

    <data-table
      :columns="columns"
      :data="signals"
      :row-height="40"
      min-height="400px"
      max-height="500px"
    />
  </div>
</template>

<style scoped>
.signal-monitor {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: #fff;
  border-radius: 4px;
  padding: 15px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.header h3 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.stats {
  font-size: 14px;
}

.buy-signal {
  color: #f56c6c;
  margin-right: 15px;
}

.sell-signal {
  color: #67c23a;
}
</style>
