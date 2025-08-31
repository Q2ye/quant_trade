<template>
  <div class="strategy-layout">
    <div class="editor-pane">
      <div class="content-header">
        <h3>策略代码编辑器</h3>
      </div>
      <textarea class="code-editor"># 双均线策略示例代码
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

    record(short_mavg=short_avg, long_mavg=long_avg)</textarea>
    </div>

    <div class="config-pane">
      <h3>回测参数配置</h3>
      <div class="param-row">
        <div class="param-label">回测周期</div>
        <select class="param-input">
          <option>2020-01-01 至 2023-08-20</option>
          <option>2019-01-01 至 2023-08-20</option>
          <option>2018-01-01 至 2023-08-20</option>
        </select>
      </div>
      <div class="param-row">
        <div class="param-label">初始资金</div>
        <input type="text" class="param-input" value="1000000">
      </div>
      <div class="param-row">
        <div class="param-label">手续费</div>
        <input type="text" class="param-input" value="0.0003">
      </div>
      <div class="param-row">
        <div class="param-label">滑点</div>
        <input type="text" class="param-input" value="0.0001">
      </div>
      <div class="param-row">
        <div class="param-label">基准指数</div>
        <select class="param-input">
          <option>000001.SH (上证指数)</option>
          <option>399001.SZ (深证成指)</option>
          <option>399006.SZ (创业板指)</option>
        </select>
      </div>
      <div class="action-bar">
        <button class="btn btn-primary">
          <i class="fas fa-play"></i> 执行回测
        </button>
        <button class="btn btn-secondary">
          <i class="fas fa-save"></i> 保存策略
        </button>
      </div>
    </div>

    <div class="monitor-pane">
      <div class="results-tabs">
        <div class="tab active">回测结果</div>
        <div class="tab">交易明细</div>
        <div class="tab">日志输出</div>
      </div>
      <div class="tab-content">
        回测结果图表和指标将显示在这里
        <div style="margin-top: 15px;">
          <div>年化收益率: <span style="color: var(--success-color);">+28.7%</span></div>
          <div>夏普比率: 0.92</div>
          <div>最大回撤: <span style="color: var(--danger-color);">-15.3%</span></div>
          <div>胜率: 55.6%</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "StrategyLayout"
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
      padding: 8px 12px;
      border: 1px solid var(--border-color);
      border-radius: 4px;
      background-color: var(--secondary-bg);
      color: var(--text-primary);
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

  .results-tabs {
    display: flex;
    border-bottom: 1px solid var(--border-color);

    .tab {
      padding: 10px 15px;
      cursor: pointer;
      color: var(--text-secondary);

      &.active {
        color: var(--accent-color);
        border-bottom: 2px solid var(--accent-color);
      }
    }
  }

  .tab-content {
    flex: 1;
    padding: 15px;
    color: var(--text-primary);
  }
}
</style>