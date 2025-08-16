<!--交易驾驶舱网格布局-->
<template>
  <div class="trade-dashboard">
    <div class="dashboard-header">
      <h2>交易驾驶舱</h2>
      <div class="summary">
        <span>总资产: <strong>¥1,234,567.89</strong></span>
        <span>今日盈亏: <strong class="profit">+¥12,345.67</strong></span>
        <span>持仓市值: <strong>¥987,654.32</strong></span>
      </div>
    </div>

    <div class="grid-container">
      <div class="card equity-curve">
        <h3>资金曲线</h3>
        <NetValueChart />
      </div>

      <div class="card risk-matrix">
        <h3>风险矩阵</h3>
        <RiskMatrix />
      </div>

      <div class="card sector-distribution">
        <h3>行业分布</h3>
        <PortfolioPieChart />
      </div>

      <div class="card market-heatmap">
        <h3>行业热度</h3>
        <HeatmapChart />
      </div>

      <div class="card positions">
        <h3>持仓明细</h3>
        <PositionTable />
      </div>

      <div class="card recent-orders">
        <h3>最新成交</h3>
        <OrderTable />
      </div>
    </div>
  </div>
</template>

<script>
import NetValueChart from '../components/charts/NetValueChart.vue'
import RiskMatrix from '../components/trade/RiskMatrix.vue'
import PortfolioPieChart from '../components/charts/PortfolioPieChart.vue'
import HeatmapChart from '../components/charts/HeatmapChart.vue'
import PositionTable from '../components/trade/PositionTable.vue'
import OrderTable from '../components/trade/OrderTable.vue'

export default {
  components: {
    NetValueChart,
    RiskMatrix,
    PortfolioPieChart,
    HeatmapChart,
    PositionTable,
    OrderTable
  }
}
</script>

<style scoped>
.trade-dashboard {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}

.summary {
  display: flex;
  gap: 20px;
}

.summary span {
  font-size: 14px;
}

.profit {
  color: #f56c6c;
}

.grid-container {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: 300px 300px auto;
  gap: 20px;
}

.card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  padding: 15px;
  display: flex;
  flex-direction: column;
}

.card h3 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 16px;
  color: #333;
}

.equity-curve, .risk-matrix {
  grid-row: 1;
}

.sector-distribution, .market-heatmap {
  grid-row: 2;
}

.positions {
  grid-row: 3;
  grid-column: 1;
}

.recent-orders {
  grid-row: 3;
  grid-column: 2;
}
</style>