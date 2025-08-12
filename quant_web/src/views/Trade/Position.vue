<!--持仓明细-->
<template>
  <div class="position">
    <el-card>
      <div slot="header" class="clearfix">
        <span>当前持仓</span>
        <el-button
          style="float: right; padding: 3px 0"
          type="text"
          icon="el-icon-refresh"
          @click="refreshPositions">
          刷新
        </el-button>
      </div>

      <el-table :data="positions" style="width: 100%" height="500">
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="quantity" label="数量" width="100" align="right" />
        <el-table-column prop="costPrice" label="成本价" width="120" align="right">
          <template slot-scope="scope">
            {{ scope.row.costPrice.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="currentPrice" label="当前价" width="120" align="right">
          <template slot-scope="scope">
            <span :style="{color: scope.row.change >= 0 ? '#f56c6c' : '#67c23a'}">
              {{ scope.row.currentPrice.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="change" label="涨跌幅" width="120" align="right">
          <template slot-scope="scope">
            <span :style="{color: scope.row.change >= 0 ? '#f56c6c' : '#67c23a'}">
              {{ (scope.row.change * 100).toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="marketValue" label="市值" width="120" align="right">
          <template slot-scope="scope">
            {{ scope.row.marketValue.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="浮动盈亏" width="150" align="right">
          <template slot-scope="scope">
            <span :style="{color: scope.row.pnl >= 0 ? '#f56c6c' : '#67c23a'}">
              {{ scope.row.pnl.toFixed(2) }} ({{ (scope.row.pnlRatio * 100).toFixed(2) }}%)
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template slot-scope="scope">
            <el-button
              size="mini"
              type="danger"
              v-if="scope.row.quantity > 0"
              @click="handleSell(scope.row)">
              卖出
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
export default {
  name: "Position",
  data() {
    return {
      positions: [
        {
          symbol: '600519.SH',
          name: '贵州茅台',
          quantity: 200,
          costPrice: 1700.25,
          currentPrice: 1850.50,
          change: 0.028,
          marketValue: 370100.00,
          pnl: 30050.00,
          pnlRatio: 0.088
        },
        {
          symbol: '000858.SZ',
          name: '五粮液',
          quantity: 500,
          costPrice: 165.80,
          currentPrice: 172.30,
          change: 0.015,
          marketValue: 86150.00,
          pnl: 3250.00,
          pnlRatio: 0.039
        },
        {
          symbol: '601318.SH',
          name: '中国平安',
          quantity: 1000,
          costPrice: 48.75,
          currentPrice: 50.20,
          change: 0.012,
          marketValue: 50200.00,
          pnl: 1450.00,
          pnlRatio: 0.030
        }
      ]
    }
  },
  methods: {
    refreshPositions() {
      // 实际项目中调用API获取最新持仓
      this.$message.success('持仓数据已刷新');
    },
    handleSell(position) {
      this.$emit('trade', {
        symbol: position.symbol,
        name: position.name,
        price: position.currentPrice,
        defaultQuantity: -Math.min(100, position.quantity)
      });
    }
  }
}
</script>

<style scoped>
.position {
  padding: 20px;
}
</style>