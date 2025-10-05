<template>
  <div class="performance-table">
    <el-table :data="tableData" stripe style="width: 100%">
      <el-table-column prop="strategy" label="策略名称" width="120" />
      <el-table-column prop="totalReturn" label="总收益率" width="100" align="right">
        <template #default="scope">
          {{ formatPercent(scope.row.totalReturn) }}
        </template>
      </el-table-column>
      <el-table-column prop="annualReturn" label="年化收益率" width="100" align="right">
        <template #default="scope">
          {{ formatPercent(scope.row.annualReturn) }}
        </template>
      </el-table-column>
      <el-table-column prop="maxDrawdown" label="最大回撤" width="100" align="right">
        <template #default="scope">
          {{ formatPercent(scope.row.maxDrawdown) }}
        </template>
      </el-table-column>
      <el-table-column prop="sharpeRatio" label="夏普比率" width="100" align="right">
        <template #default="scope">
          {{ scope.row.sharpeRatio.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="calmarRatio" label="卡玛比率" width="100" align="right">
        <template #default="scope">
          {{ scope.row.calmarRatio.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="winRate" label="胜率" width="100" align="right">
        <template #default="scope">
          {{ formatPercent(scope.row.winRate) }}
        </template>
      </el-table-column>
      <el-table-column prop="profitLossRatio" label="盈亏比" width="100" align="right">
        <template #default="scope">
          {{ scope.row.profitLossRatio.toFixed(2) }}
        </template>
      </el-table-column>
      <el-table-column prop="totalTrades" label="总交易次数" width="100" align="right" />
    </el-table>
  </div>
</template>

<script>
export default {
  name: 'PerformanceTable',
  props: {
    data: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    tableData() {
      return this.data.map(item => ({
        strategy: item.strategyName,
        totalReturn: item.totalReturn || 0,
        annualReturn: item.annualReturn || 0,
        maxDrawdown: item.maxDrawdown || 0,
        sharpeRatio: item.sharpeRatio || 0,
        calmarRatio: item.calmarRatio || 0,
        winRate: item.winRate || 0,
        profitLossRatio: item.profitLossRatio || 0,
        totalTrades: item.totalTrades || 0
      }))
    }
  },
  methods: {
    formatPercent(value) {
      return `${(value * 100).toFixed(2)}%`
    }
  }
}
</script>

<style scoped>
.performance-table {
  margin-top: 20px;
}
</style>