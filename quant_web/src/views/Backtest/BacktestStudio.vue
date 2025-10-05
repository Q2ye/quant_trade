<template>
  <div class="backtest-studio">
    <div class="studio-header">
      <h2>回测工作室</h2>
      <div class="studio-actions">
        <el-button type="primary" @click="runMultiBacktest">多策略回测</el-button>
        <el-button @click="parameterOptimization">参数优化</el-button>
        <el-button @click="exportResults">导出结果</el-button>
      </div>
    </div>

    <div class="studio-content">
      <!-- 策略选择区域 -->
      <div class="strategy-selection">
        <h3>选择对比策略</h3>
        <el-transfer
          v-model="selectedStrategies"
          :data="strategyOptions"
          :titles="['可用策略', '已选策略']"
        ></el-transfer>
      </div>

      <!-- 回测参数配置 -->
      <div class="backtest-config">
        <h3>回测参数</h3>
        <el-form :model="backtestParams" label-width="120px">
          <el-form-item label="回测周期">
            <el-date-picker
              v-model="backtestDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
          </el-form-item>
          <el-form-item label="初始资金">
            <el-input-number
              v-model="backtestParams.initialCapital"
              :min="10000"
              :step="10000"
            />
          </el-form-item>
          <el-form-item label="基准指数">
            <el-select v-model="backtestParams.benchmark">
              <el-option
                v-for="index in benchmarkOptions"
                :key="index.code"
                :label="index.name"
                :value="index.code"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </div>

      <!-- 多策略对比图表 -->
      <div class="comparison-charts" v-if="comparisonResults.length > 0">
        <h3>策略对比分析</h3>
        <el-tabs type="border-card">
          <el-tab-pane label="净值曲线">
            <MultiStrategyChart :data="comparisonResults" />
          </el-tab-pane>
          <el-tab-pane label="绩效指标">
            <PerformanceTable :data="comparisonResults" />
          </el-tab-pane>
          <el-tab-pane label="回撤对比">
            <DrawdownComparison :data="comparisonResults" />
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 参数优化面板 -->
      <div class="optimization-panel" v-if="showOptimization">
        <h3>参数优化</h3>
        <ParameterOptimizer
          :strategy="optimizationStrategy"
          @optimize="runOptimization"
        />

        <div v-if="optimizationResults" class="optimization-results">
          <h4>优化结果</h4>
          <HeatmapChart :data="optimizationResults" />
          <ParameterTable :data="optimizationResults.bestParameters" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { mapState } from 'vuex'
import MultiStrategyChart from '@/components/backtest/MultiStrategyChart.vue'
import PerformanceTable from '@/components/backtest/PerformanceTable.vue'
import DrawdownComparison from '@/components/backtest/DrawdownComparison.vue'
import ParameterOptimizer from '@/components/backtest/ParameterOptimizer.vue'
import HeatmapChart from '@/components/backtest/HeatmapChart.vue'
import ParameterTable from '@/components/backtest/ParameterTable.vue'

export default {
  name: 'BacktestStudio',
  components: {
    MultiStrategyChart,
    PerformanceTable,
    DrawdownComparison,
    ParameterOptimizer,
    HeatmapChart,
    ParameterTable
  },
  data() {
    return {
      selectedStrategies: [],
      comparisonResults: [],
      backtestParams: {
        initialCapital: 1000000,
        benchmark: '000300.SH',
        startDate: '2020-01-01',
        endDate: '2023-12-31'
      },
      showOptimization: false,
      optimizationStrategy: null,
      optimizationResults: null,
      benchmarkOptions: [
        { code: '000001.SH', name: '上证指数' },
        { code: '000300.SH', name: '沪深300' },
        { code: '000905.SH', name: '中证500' },
        { code: '399006.SZ', name: '创业板指' }
      ]
    }
  },
  computed: {
    ...mapState('strategy', ['strategies']),
    strategyOptions() {
      return this.strategies.map(s => ({
        key: s.id,
        label: s.name,
        disabled: s.status === 'running'
      }))
    },
    backtestDateRange: {
      get() {
        return [this.backtestParams.startDate, this.backtestParams.endDate]
      },
      set([start, end]) {
        this.backtestParams.startDate = start
        this.backtestParams.endDate = end
      }
    }
  },
  methods: {
    async runMultiBacktest() {
      if (this.selectedStrategies.length < 2) {
        this.$message.warning('请选择至少两个策略进行对比')
        return
      }

      try {
        this.comparisonResults = await this.$api.backtest.runMultiple({
          strategyIds: this.selectedStrategies,
          params: this.backtestParams
        })
        this.$message.success('多策略回测完成')
      } catch (error) {
        this.$message.error('回测失败: ' + error.message)
      }
    },

    parameterOptimization() {
      if (this.selectedStrategies.length !== 1) {
        this.$message.warning('请选择一个策略进行参数优化')
        return
      }

      this.optimizationStrategy = this.strategies.find(
        s => s.id === this.selectedStrategies[0]
      )
      this.showOptimization = true
    },

    async runOptimization(parameters) {
      try {
        this.optimizationResults = await this.$api.backtest.optimizeParameters({
          strategyId: this.optimizationStrategy.id,
          parameters,
          backtestParams: this.backtestParams
        })
        this.$message.success('参数优化完成')
      } catch (error) {
        this.$message.error('优化失败: ' + error.message)
      }
    },

    exportResults() {
      // 实现导出逻辑
      const data = this.comparisonResults.length > 0 ?
        this.comparisonResults :
        this.optimizationResults

      if (!data) {
        this.$message.warning('没有可导出的数据')
        return
      }

      this.$utils.exportToCSV(data, 'backtest_results')
    }
  }
}
</script>

<style scoped>
.backtest-studio {
  padding: 20px;
}

.studio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 15px;
  border-bottom: 1px solid #e6e6e6;
}

.studio-content {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 30px;
}

.strategy-selection,
.backtest-config {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.comparison-charts,
.optimization-panel {
  grid-column: 1 / -1;
  background: #fff;
  padding: 20px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  margin-top: 20px;
}

.optimization-results {
  margin-top: 20px;
}
</style>