<!--回测报告-->
<template>
  <ReportLayout>
    <template #header>
      <div class="report-header">
        <h2>{{ strategy.name }} - 回测报告</h2>
        <div class="summary-stats">
          <StatCard title="年化收益" :value="`${(report.summary.annualReturn * 100).toFixed(2)}%`"
                    :trend="report.summary.annualReturn > 0 ? 'up' : 'down'"/>
          <StatCard title="累计收益" :value="`${(report.summary.totalReturn * 100).toFixed(2)}%`"
                    :trend="report.summary.totalReturn > 0 ? 'up' : 'down'"/>
          <StatCard title="最大回撤" :value="`${(report.summary.maxDrawdown * 100).toFixed(2)}%`" trend="down"/>
          <StatCard title="夏普比率" :value="report.summary.sharpeRatio.toFixed(2)"/>
          <StatCard title="胜率" :value="`${(report.summary.winRate * 100).toFixed(1)}%`"/>
        </div>
      </div>
    </template>

    <template #content>
      <div class="section">
        <h3>净值曲线</h3>
        <NetValueChart :data="report.equityCurve" :benchmark="report.benchmark" />
      </div>

      <div class="metrics-grid">
        <div class="metric-card">
          <h3>回撤分析</h3>
          <DrawdownChart :data="report.drawdown" />
        </div>

        <div class="metric-card">
          <h3>月度收益</h3>
          <MonthlyReturnChart :data="report.monthlyReturns" />
        </div>
      </div>

      <div class="section">
        <h3>交易分析</h3>
        <el-tabs v-model="activeTradeTab">
          <el-tab-pane label="交易列表" name="trades">
            <TradeTable :trades="report.trades" />
          </el-tab-pane>
          <el-tab-pane label="收益分布" name="distribution">
            <ProfitDistributionChart :data="report.profitDistribution" />
          </el-tab-pane>
          <el-tab-pane label="持仓分析" name="holdings">
            <HoldingAnalysisChart :data="report.holdings" />
          </el-tab-pane>
        </el-tabs>
      </div>

      <div class="section">
        <h3>参数敏感性分析</h3>
        <ParameterSensitivity :data="report.parameterSensitivity" />
      </div>
    </template>

    <template #footer>
      <div class="report-footer">
        <el-button type="primary" @click="saveReport">保存报告</el-button>
        <el-button @click="exportPDF">导出PDF</el-button>
        <el-button @click="addToBasket">加入股票篮子</el-button>
      </div>
    </template>
  </ReportLayout>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import ReportLayout from '@/layouts/ReportLayout.vue'
import NetValueChart from '@/components/charts/NetValueChart.vue'
import DrawdownChart from '@/components/charts/DrawdownChart.vue'
import MonthlyReturnChart from '@/components/charts/MonthlyReturnChart.vue'
import ProfitDistributionChart from '@/components/charts/ProfitDistributionChart.vue'
import HoldingAnalysisChart from '@/components/charts/HoldingAnalysisChart.vue'
import ParameterSensitivity from '@/components/charts/ParameterSensitivity.vue'
import TradeTable from '@/components/data/TradeTable.vue'
import StatCard from '@/components/ui/StatCard.vue'

export default {
  components: {
    ReportLayout,
    NetValueChart,
    DrawdownChart,
    MonthlyReturnChart,
    ProfitDistributionChart,
    HoldingAnalysisChart,
    ParameterSensitivity,
    TradeTable,
    StatCard
  },

  props: {
    id: String
  },

  data() {
    return {
      activeTradeTab: 'trades',
      report: {
        summary: {
          annualReturn: 0.152,
          totalReturn: 0.482,
          maxDrawdown: -0.215,
          sharpeRatio: 1.28,
          winRate: 0.65,
          profitFactor: 1.82,
          tradesCount: 142,
          avgTradeReturn: 0.012
        },
        equityCurve: [
          { date: '2022-01', value: 100000 },
          { date: '2022-02', value: 102500 },
          // ... 更多数据
        ],
        benchmark: [
          { date: '2022-01', value: 100000 },
          { date: '2022-02', value: 101200 },
          // ... 更多数据
        ],
        drawdown: [
          { date: '2022-01', value: -0.05 },
          { date: '2022-02', value: -0.12 },
          // ... 更多数据
        ],
        monthlyReturns: [
          { month: '2022-01', return: 0.025 },
          { month: '2022-02', return: 0.018 },
          // ... 更多数据
        ],
        profitDistribution: {
          bins: [-0.05, -0.03, -0.01, 0.01, 0.03, 0.05],
          counts: [5, 12, 28, 35, 42, 20]
        },
        holdings: [
          { symbol: '600519.SH', name: '贵州茅台', weight: 0.15, return: 0.32 },
          { symbol: '000858.SZ', name: '五粮液', weight: 0.12, return: 0.28 },
          // ... 更多数据
        ],
        trades: [
          {
            id: 1,
            symbol: '600519.SH',
            name: '贵州茅台',
            direction: 'buy',
            date: '2022-01-15',
            price: 1850.50,
            quantity: 100,
            amount: 185050,
            fee: 55.52
          },
          // ... 更多交易
        ],
        parameterSensitivity: {
          params: ['sma_short', 'sma_long', 'trade_size'],
          metrics: ['annualReturn', 'maxDrawdown', 'sharpeRatio'],
          data: [
            { param: 'sma_short', value: 5, annualReturn: 0.152, maxDrawdown: -0.215, sharpeRatio: 1.28 },
            { param: 'sma_short', value: 7, annualReturn: 0.168, maxDrawdown: -0.198, sharpeRatio: 1.35 },
            // ... 更多数据
          ]
        }
      }
    }
  },

  computed: {
    ...mapState('strategy', ['currentStrategy']),

    strategy() {
      return this.currentStrategy || { name: '未知策略' }
    }
  },

  methods: {
    ...mapActions('strategy', ['loadBacktestReport', 'saveBacktestReport']),
    ...mapActions('basket', ['createBasketFromReport']),

    async loadReport() {
      if (this.id) {
        this.report = await this.loadBacktestReport(this.id)
      }
    },

    saveReport() {
      this.saveBacktestReport({
        id: this.id,
        report: this.report
      })
      this.$message.success('回测报告已保存')
    },

    exportPDF() {
      // 实际项目中调用PDF导出服务
      this.$message.info('PDF导出功能正在开发中')
    },

    addToBasket() {
      const basketName = `${this.strategy.name}_股票池`
      this.createBasketFromReport({
        reportId: this.id,
        basketName
      })
      this.$message.success(`已创建股票篮子: ${basketName}`)
    }
  },

  mounted() {
    this.loadReport()
  }
}
</script>

<style scoped>
.report-header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 15px;
  margin-top: 20px;
}

.section {
  margin-bottom: 30px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
}

.metric-card {
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.report-footer {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #eee;
  text-align: center;
}
</style>