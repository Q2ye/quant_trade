<template>
  <div class="strategy-layout">
    <div class="editor-pane">
      <div class="content-header">
        <h3>策略代码编辑器</h3>
      </div>
      <n-input
        type="textarea"
        class="code-editor"
        :autosize="{ minRows: 20, maxRows: 30 }"
        :value="code"
        @update:value="handleCodeChange"
      />
    </div>

    <div class="config-pane">
      <h3>回测参数配置</h3>
      <div class="param-row">
        <div class="param-label">回测周期</div>
        <n-select
          class="param-input"
          :options="timeRangeOptions"
          :value="selectedTimeRange"
          @update:value="handleTimeRangeChange"
        />
      </div>
      <div class="param-row">
        <div class="param-label">初始资金</div>
        <n-input
          class="param-input"
          type="text"
          :value="initialCapital"
          @update:value="handleCapitalChange"
        />
      </div>
      <div class="param-row">
        <div class="param-label">手续费</div>
        <n-input
          class="param-input"
          type="text"
          :value="commission"
          @update:value="handleCommissionChange"
        />
      </div>
      <div class="param-row">
        <div class="param-label">滑点</div>
        <n-input
          class="param-input"
          type="text"
          :value="slippage"
          @update:value="handleSlippageChange"
        />
      </div>
      <div class="param-row">
        <div class="param-label">基准指数</div>
        <n-select
          class="param-input"
          :options="benchmarkOptions"
          :value="selectedBenchmark"
          @update:value="handleBenchmarkChange"
        />
      </div>
      <div class="action-bar">
        <n-button type="primary" class="btn btn-primary" @click="runBacktest">
          <template #icon>
            <n-icon><PlayArrow /></n-icon>
          </template>
          执行回测
        </n-button>
        <n-button class="btn btn-secondary" @click="saveStrategy">
          <template #icon>
            <n-icon><Save /></n-icon>
          </template>
          保存策略
        </n-button>
      </div>
    </div>

    <div class="monitor-pane">
      <n-tabs type="line" class="results-tabs">
        <n-tab-pane name="results" tab="回测结果">
          <div class="tab-content">
            回测结果图表和指标将显示在这里
            <div style="margin-top: 15px;">
              <div>年化收益率: <span style="color: var(--success-color);">+28.7%</span></div>
              <div>夏普比率: 0.92</div>
              <div>最大回撤: <span style="color: var(--danger-color);">-15.3%</span></div>
              <div>胜率: 55.6%</div>
            </div>
          </div>
        </n-tab-pane>
        <n-tab-pane name="trades" tab="交易明细">
          <div class="tab-content">
            交易明细将显示在这里
          </div>
        </n-tab-pane>
        <n-tab-pane name="logs" tab="日志输出">
          <div class="tab-content">
            日志输出将显示在这里
          </div>
        </n-tab-pane>
      </n-tabs>
    </div>
  </div>
</template>

<script>
import { NInput, NSelect, NButton, NIcon, NTabs, NTabPane } from 'naive-ui'
import { PlayArrow, Save } from '@vicons/material'

export default {
  name: "StrategyLayout",
  components: {
    NInput,
    NSelect,
    NButton,
    NIcon,
    NTabs,
    NTabPane,
    PlayArrow,
    Save
  },
  data() {
    return {
      code: `# 双均线策略示例代码
def initialize(context):
    context.security = '000001.SH'
    context.SHORTPERIOD = 10
    context.LONGPERIOD = 30

def handle_data(context, data):
    prices = data.history(context.security, 'price',
                         context.LONGPERIOD + 1, '1d')

    short_avg = prices[-context.SHORTPERIOD:].mean()
    long_avg = prices.mean()

    if short_avg > long_avg:
        order_target_percent(context.security, 0.9)
    else:
        order_target_percent(context.security, 0.1)

    record(short_mavg=short_avg, long_mavg=long_avg)`,
      selectedTimeRange: '2020-01-01 至 2023-08-20',
      initialCapital: '1000000',
      commission: '0.0003',
      slippage: '0.0001',
      selectedBenchmark: '000001.SH (上证指数)',
      timeRangeOptions: [
        { label: '2020-01-01 至 2023-08-20', value: '2020-01-01 至 2023-08-20' },
        { label: '2019-01-01 至 2023-08-20', value: '2019-01-01 至 2023-08-20' },
        { label: '2018-01-01 至 2023-08-20', value: '2018-01-01 至 2023-08-20' }
      ],
      benchmarkOptions: [
        { label: '000001.SH (上证指数)', value: '000001.SH (上证指数)' },
        { label: '399001.SZ (深证成指)', value: '399001.SZ (深证成指)' },
        { label: '399006.SZ (创业板指)', value: '399006.SZ (创业板指)' }
      ]
    }
  },
  methods: {
    handleCodeChange(value) {
      this.code = value
    },
    handleTimeRangeChange(value) {
      this.selectedTimeRange = value
    },
    handleCapitalChange(value) {
      this.initialCapital = value
    },
    handleCommissionChange(value) {
      this.commission = value
    },
    handleSlippageChange(value) {
      this.slippage = value
    },
    handleBenchmarkChange(value) {
      this.selectedBenchmark = value
    },
    runBacktest() {
      console.log('执行回测')
    },
    saveStrategy() {
      console.log('保存策略')
    }
  }
}
</script>

<style lang="scss" scoped>
@use '@/assets/scss/global.scss';

.strategy-layout {
  display: flex;
  height: calc(100vh - var(--header-height) - 40px);
  overflow: hidden;
}

.editor-pane {
  flex: 4;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;

  .content-header {
    padding: 15px;
    border-bottom: 1px solid var(--border-color);
  }

  .code-editor {
    flex: 1;
    border: none;
    padding: 15px;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
    font-size: 14px;
    line-height: 1.5;
    resize: none;
    background-color: var(--secondary-bg);
    color: var(--text-primary);
  }
}

.config-pane {
  flex: 3;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  padding: 15px;

  h3 {
    margin-top: 0;
    margin-bottom: 20px;
    color: var(--text-primary);
  }

  .param-row {
    display: flex;
    align-items: center;
    margin-bottom: 15px;

    .param-label {
      width: 80px;
      color: var(--text-secondary);
      font-size: 14px;
    }

    .param-input {
      flex: 1;
    }
  }

  .action-bar {
    margin-top: auto;
    padding-top: 15px;
    text-align: center;
    display: flex;
    gap: 10px;

    .btn {
      flex: 1;
    }
  }
}

.monitor-pane {
  flex: 3;
  display: flex;
  flex-direction: column;

  :deep(.n-tabs) {
    display: flex;
    flex-direction: column;
    height: 100%;

    .n-tabs-nav {
      border-bottom: 1px solid var(--border-color);
    }

    .n-tabs-pane-wrapper {
      flex: 1;
      overflow: auto;
    }
  }

  .tab-content {
    flex: 1;
    padding: 15px;
    color: var(--text-primary);
  }
}
</style>