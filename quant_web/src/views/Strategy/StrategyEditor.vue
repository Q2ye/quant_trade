<!--策略编辑器-->
<template>
  <StrategyLayout>
    <template #editor>
      <CodeEditor
        v-model="strategy.code"
        language="python"
        :readOnly="isReadOnly"
        @save="saveStrategy"
      />
    </template>

    <template #config>
      <div class="config-section">
        <h3>策略参数</h3>
        <div v-for="(param, index) in strategy.params" :key="index" class="param-item">
          <label>{{ param.name }}</label>
          <el-slider
            v-model="param.value"
            :min="param.min"
            :max="param.max"
            :step="param.step"
            show-input
          />
        </div>
      </div>

      <div class="config-section">
        <h3>回测设置</h3>
        <el-form :model="backtestParams" label-width="120px">
          <el-form-item label="回测周期">
            <el-date-picker
              v-model="backtestDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="yyyy-MM-dd"
            />
          </el-form-item>

          <el-form-item label="初始资金">
            <el-input-number
              v-model="backtestParams.initialCapital"
              :min="10000"
              :step="10000"
            />
          </el-form-item>

          <el-form-item label="手续费">
            <el-input-number
              v-model="backtestParams.commission"
              :min="0"
              :step="0.0001"
              :precision="4"
            />
          </el-form-item>

          <el-form-item label="滑点">
            <el-input-number
              v-model="backtestParams.slippage"
              :min="0"
              :step="0.0001"
              :precision="4"
            />
          </el-form-item>
        </el-form>
      </div>

      <div class="action-bar">
        <el-button type="primary" @click="runBacktest">执行回测</el-button>
        <el-button @click="saveStrategy">保存策略</el-button>
        <el-button v-if="strategy.id" @click="cloneStrategy">克隆策略</el-button>
      </div>
    </template>

    <template #monitor>
      <div class="monitor-section">
        <h3>实时日志</h3>
        <BacktestLogs :logs="logs" />
      </div>

      <div class="monitor-section">
        <h3>变量监控</h3>
        <VariableMonitor :variables="variables" />
      </div>

      <div class="monitor-section">
        <h3>信号跟踪</h3>
        <SignalTimeline :signals="signals" />
      </div>
    </template>
  </StrategyLayout>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import StrategyLayout from '@/layouts/StrategyLayout.vue'
import CodeEditor from '@/components/strategy/CodeEditor.vue'
import BacktestLogs from '@/components/strategy/BacktestLogs.vue'
import VariableMonitor from '@/components/strategy/VariableMonitor.vue'
import SignalTimeline from '@/components/strategy/SignalTimeline.vue'

export default {
  components: {
    StrategyLayout,
    CodeEditor,
    BacktestLogs,
    VariableMonitor,
    SignalTimeline
  },

  props: {
    id: String
  },

  data() {
    return {
      logs: [],
      variables: [],
      signals: [],
      isReadOnly: false
    }
  },

  computed: {
    ...mapState('strategy', ['currentStrategy', 'backtestParams']),

    strategy() {
      return this.currentStrategy || this.defaultStrategy()
    },

    backtestDateRange: {
      get() {
        return [this.backtestParams.startDate, this.backtestParams.endDate]
      },
      set([start, end]) {
        this.$store.commit('strategy/SET_BACKTEST_PARAMS', {
          ...this.backtestParams,
          startDate: start,
          endDate: end
        })
      }
    }
  },

  methods: {
    ...mapActions('strategy', [
      'loadStrategy',
      'saveStrategy',
      'runBacktest',
      'cloneStrategy',
      'getStrategyLogs'
    ]),

    defaultStrategy() {
      return {
        id: null,
        name: '新策略',
        code: `# 策略初始化
def initialize(context):
    # 设置策略参数
    context.sma_short = 5
    context.sma_long = 20
    context.trade_size = 0.95

    # 设置交易标的
    context.security = '000001.SH'

    # 设置定时任务
    schedule(schedule_func=daily_task, time_rule='every_day')

# 每日交易任务
def daily_task(context, data):
    # 获取历史数据
    prices = data.history(context.security, 'close', context.sma_long, '1d')

    # 计算均线
    short_ma = prices[-context.sma_short:].mean()
    long_ma = prices.mean()

    # 生成交易信号
    if short_ma > long_ma:
        order_target_percent(context.security, context.trade_size)
    else:
        order_target_percent(context.security, 0)`,
        params: [
          { name: 'sma_short', value: 5, min: 1, max: 20, step: 1 },
          { name: 'sma_long', value: 20, min: 10, max: 50, step: 1 },
          { name: 'trade_size', value: 0.95, min: 0.1, max: 1.0, step: 0.05 }
        ]
      }
    },

    async runBacktest() {
      try {
        this.logs = []
        this.signals = []

        // 模拟回测日志
        this.addLog('开始策略回测...', 'info')

        // 执行回测
        const results = await this.$store.dispatch('strategy/runBacktest')

        this.addLog('回测完成!', 'success')
        this.addLog(`最终净值: ${results.finalValue.toFixed(2)}`, 'info')
        this.addLog(`年化收益: ${(results.annualReturn * 100).toFixed(2)}%`, 'info')
        this.addLog(`最大回撤: ${(results.maxDrawdown * 100).toFixed(2)}%`, 'info')

        // 导航到回测报告
        this.$router.push({
          name: 'BacktestReport',
          params: { id: results.id }
        })

      } catch (error) {
        this.addLog(`回测失败: ${error.message}`, 'error')
      }
    },

    addLog(message, level = 'info') {
      this.logs.push({
        id: Date.now(),
        timestamp: new Date().toLocaleTimeString(),
        level,
        message
      })
    },

    async fetchStrategyData() {
      if (this.id) {
        await this.loadStrategy(this.id)
        this.isReadOnly = this.strategy.status === 'running'

        // 加载策略日志
        this.logs = await this.getStrategyLogs(this.id)
      }
    }
  },

  mounted() {
    this.fetchStrategyData()
  }
}
</script>

<style scoped>
.config-section, .monitor-section {
  margin-bottom: 20px;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 4px;
}

.param-item {
  margin-bottom: 15px;
}

.param-item label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.action-bar {
  margin-top: 20px;
  text-align: center;
}
</style>