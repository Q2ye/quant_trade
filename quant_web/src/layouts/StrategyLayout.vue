<!--策略工作室三屏布局-->
<template>
  <div class="strategy-layout">
    <div class="editor-pane">
      <StrategyEditor :strategy="currentStrategy" />
    </div>
    <div class="config-pane">
      <BacktestConfig :config="backtestConfig" />
      <div class="action-bar">
        <el-button type="primary" @click="runBacktest">执行回测</el-button>
        <el-button @click="saveStrategy">保存策略</el-button>
      </div>
    </div>
    <div class="monitor-pane">
      <BacktestLogs :logs="logs" />
      <VariableMonitor :variables="monitorVariables" />
    </div>
  </div>
</template>

<script>
import StrategyEditor from '@/components/strategy/StrategyEditor.vue'
import BacktestConfig from '@/components/strategy/BacktestConfig.vue'
import BacktestLogs from '@/components/strategy/BacktestLogs.vue'
import VariableMonitor from '@/components/strategy/VariableMonitor.vue'
export default {
  components: {
    StrategyEditor,
    BacktestConfig,
    BacktestLogs,
    VariableMonitor
  },
  data() {
    return {
      currentStrategy: {
        id: 'strategy_001',
        name: '双均线策略',
        code: `// 双均线策略示例
def initialize(context):
    context.sma_short = 5
    context.sma_long = 20

def handle_data(context, data):
    prices = data.history('close', context.sma_long)
    short_ma = prices[-context.sma_short:].mean()
    long_ma = prices.mean()

    if short_ma > long_ma:
        order_target_percent('000001.SH', 1.0)
    else:
        order_target_percent('000001.SH', 0.0)`,
        params: [
          { name: 'sma_short', value: 5, min: 1, max: 20, step: 1 },
          { name: 'sma_long', value: 20, min: 10, max: 50, step: 1 }
        ]
      },
      backtestConfig: {
        startDate: '2020-01-01',
        endDate: '2023-12-31',
        initialCapital: 100000,
        commission: 0.0003,
        slippage: 0.01
      },
      logs: [
        { time: '09:30:01', level: 'info', message: '策略初始化完成' },
        { time: '09:30:05', level: 'signal', message: '生成买入信号: 000001.SH' }
      ],
      monitorVariables: [
        { name: 'current_price', value: 15.32 },
        { name: 'position', value: 1000 },
        { name: 'cash', value: 50000.00 }
      ]
    }
  },
  methods: {
    runBacktest() {
      // 调用API执行回测
      console.log('执行回测:', this.currentStrategy, this.backtestConfig)
      // 模拟回测日志更新
      this.logs.push({
        time: new Date().toLocaleTimeString(),
        level: 'info',
        message: '开始回测...'
      })
    },
    saveStrategy() {
      console.log('保存策略:', this.currentStrategy)
    }
  }
}
</script>

<style scoped>
.strategy-layout {
  display: flex;
  height: calc(100vh - 60px);
  overflow: hidden;
}

.editor-pane {
  flex: 4;
  border-right: 1px solid #eaeaea;
  display: flex;
  flex-direction: column;
}

.config-pane {
  flex: 3;
  border-right: 1px solid #eaeaea;
  display: flex;
  flex-direction: column;
  padding: 15px;
}

.monitor-pane {
  flex: 3;
  display: flex;
  flex-direction: column;
}

.action-bar {
  margin-top: auto;
  padding-top: 15px;
  text-align: center;
}
</style>