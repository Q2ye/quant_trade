<!--交易执行-->
<template>
  <div class="trade-execution">
    <h2>交易执行</h2>

    <el-card class="execution-card">
      <div slot="header" class="clearfix">
        <span>交易信号</span>
        <el-button
          style="float: right; padding: 3px 0"
          type="text"
          @click="refreshSignals"
        >
          刷新
        </el-button>
      </div>
      <SignalTable :signals="signals" @execute="openTradeDialog" />
    </el-card>

    <el-card class="execution-card">
      <div slot="header" class="clearfix">
        <span>篮子交易</span>
      </div>
      <BasketSelector @select="openBasketTrade" />
    </el-card>

    <el-dialog
      :title="`执行交易 - ${currentSymbol}`"
      :visible.sync="tradeDialogVisible"
      width="600px"
    >
      <TradeForm
        :symbol="currentSymbol"
        :price="currentPrice"
        :default-quantity="defaultQuantity"
        @submit="executeTrade"
      />
    </el-dialog>
  </div>
</template>

<script>
import SignalTable from '../../components/trade/SignalTable.vue'
import BasketSelector from '../basket/BasketSelector.vue'
import TradeForm from '../../components/trade/TradeForm.vue'

export default {
  components: {
    SignalTable,
    BasketSelector,
    TradeForm
  },

  data() {
    return {
      signals: [
        {
          id: 1,
          strategy: '双均线策略',
          symbol: '600519.SH',
          name: '贵州茅台',
          signal: '买入',
          strength: 0.85,
          price: 1850.50,
          timestamp: '2023-08-09 10:05:32'
        },
        {
          id: 2,
          strategy: '动量反转策略',
          symbol: '000001.SH',
          name: '上证指数',
          signal: '卖出',
          strength: 0.72,
          price: 3245.67,
          timestamp: '2023-08-09 09:45:18'
        }
      ],
      tradeDialogVisible: false,
      currentSymbol: '',
      currentPrice: 0,
      defaultQuantity: 0
    }
  },

  methods: {
    refreshSignals() {
      // 实际项目中调用API获取最新信号
      this.$message.success('信号已刷新')
    },

    openTradeDialog(signal) {
      this.currentSymbol = signal.symbol
      this.currentPrice = signal.price
      this.defaultQuantity = signal.signal === '买入' ? 100 : -100
      this.tradeDialogVisible = true
    },

    openBasketTrade(basket) {
      this.currentSymbol = basket.id
      this.currentPrice = basket.currentValue
      this.defaultQuantity = 0
      this.tradeDialogVisible = true
    },

    executeTrade(order) {
      // 实际项目中调用交易API
      console.log('执行交易:', order)

      this.tradeDialogVisible = false
      this.$message.success('交易指令已发送')

      // 添加到交易历史
      this.$store.commit('trade/ADD_TRADE', {
        ...order,
        id: Date.now(),
        status: '已报',
        timestamp: new Date().toISOString()
      })
    }
  }
}
</script>

<style scoped>
.trade-execution {
  padding: 20px;
}

.execution-card {
  margin-bottom: 20px;
}
</style>