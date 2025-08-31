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
        <div class="chart-placeholder">净值走势图表 (vs 沪深300)</div>
      </div>

      <div class="card risk-matrix">
        <h3>风险矩阵</h3>
        <div class="chart-placeholder">回撤/仓位/当日盈亏监控</div>
      </div>

      <div class="card sector-distribution">
        <h3>行业分布</h3>
        <div class="chart-placeholder">行业环形图/持仓比例可视化</div>
      </div>

      <div class="card market-heatmap">
        <h3>行业热度</h3>
        <div class="chart-placeholder">涨跌幅TOP5行业/板块热度图</div>
      </div>

      <div class="card positions">
        <h3>持仓明细</h3>
        <div class="chart-placeholder">持仓股票表格</div>
      </div>

      <div class="card recent-orders">
        <h3>最新成交</h3>
        <div class="chart-placeholder">成交记录表格</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "TradeLayout"
}
</script>

<style lang="scss" scoped>
@use '@/assets/scss/global.scss';

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
  border-bottom: 1px solid var(--border-color);

  h2 {
    color: var(--text-primary);
    margin: 0;
  }
}

.summary {
  display: flex;
  gap: 20px;

  span {
    font-size: 14px;
    color: var(--text-secondary);

    strong {
      color: var(--text-primary);

      &.profit {
        color: var(--success-color);
      }
    }
  }
}

.grid-container {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: 300px 300px auto;
  gap: 20px;
}

.card {
  background: var(--secondary-bg);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  padding: 15px;
  display: flex;
  flex-direction: column;

  h3 {
    margin-top: 0;
    margin-bottom: 15px;
    font-size: 16px;
    color: var(--text-primary);
  }
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

.chart-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background-color: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
}
</style>