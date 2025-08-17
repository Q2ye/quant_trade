<template>
  <div class="variable-monitor">
    <div class="tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { 'active': activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="tab-content">
      <div
        v-if="activeTab === 'logs'"
        class="log-container"
      >
        <div
          v-for="(log, index) in logs"
          :key="index"
          class="log-item"
        >
          <span class="log-time">[{{ log.time }}]</span>
          <span :class="['log-message', logLevelClass(log.level)]">{{ log.message }}</span>
        </div>
      </div>

      <div
        v-if="activeTab === 'variables'"
        class="variables-container"
      >
        <div class="variables-grid">
          <div class="grid-header">
            变量名
          </div>
          <div class="grid-header">
            值
          </div>
          <div class="grid-header">
            类型
          </div>

          <template
            v-for="(value, key) in variables"
            :key="key"
          >
            <div class="grid-item">
              {{ key }}
            </div>
            <div class="grid-item">
              {{ formatValue(value) }}
            </div>
            <div class="grid-item">
              {{ typeof value }}
            </div>
          </template>
        </div>
      </div>

      <div
        v-if="activeTab === 'signals'"
        class="signals-container"
      >
        <div class="signal-timeline">
          <div
            v-for="signal in signals"
            :key="signal.id"
            class="signal-event"
            :class="signal.type"
          >
            <div class="signal-time">
              {{ signal.time }}
            </div>
            <div class="signal-info">
              <span class="signal-symbol">{{ signal.symbol }}</span>
              <span class="signal-type">{{ signalTypeText(signal.type) }}</span>
              <span class="signal-price">{{ signal.price.toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "VariableMonitor",
  data() {
    return {
      activeTab: 'logs',
      tabs: [
        { id: 'logs', label: '运行日志' },
        { id: 'variables', label: '变量监控' },
        { id: 'signals', label: '信号时间轴' }
      ],
      logs: [
        { time: '09:30:05', level: 'info', message: '策略初始化完成' },
        { time: '09:35:22', level: 'trade', message: '买入 600519.SH @1800.50 数量:100' },
        { time: '10:15:47', level: 'warning', message: '波动率超过阈值' }
      ],
      variables: {
        security: '600519.SH',
        short_ma: 1795.34,
        long_ma: 1782.15,
        position: 100,
        cash: 24567.89,
        portfolio_value: 180245.67
      },
      signals: [
        { id: 1, time: '09:35:22', symbol: '600519.SH', type: 'buy', price: 1800.50 },
        { id: 2, time: '10:15:47', symbol: '000001.SZ', type: 'sell', price: 14.80 },
        { id: 3, time: '11:20:15', symbol: '600036.SH', type: 'buy', price: 35.25 }
      ]
    }
  },
  methods: {
    logLevelClass(level) {
      return {
        'log-info': level === 'info',
        'log-trade': level === 'trade',
        'log-warning': level === 'warning',
        'log-error': level === 'error'
      }
    },
    formatValue(value) {
      if (typeof value === 'number') {
        return value.toFixed(2);
      }
      return value;
    },
    signalTypeText(type) {
      return type === 'buy' ? '买入信号' : '卖出信号';
    }
  }
}
</script>

<style scoped>
.variable-monitor {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  font-size: 12px;
}

.tabs {
  display: flex;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
}

.tab-btn {
  padding: 8px 15px;
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}

.tab-btn.active {
  border-bottom: 2px solid #409eff;
  color: #409eff;
  font-weight: bold;
}

.tab-content {
  flex: 1;
  overflow: auto;
  padding: 5px;
  background-color: #f8f8f8;
}

.log-container {
  display: flex;
  flex-direction: column;
}

.log-item {
  padding: 5px 3px;
  border-bottom: 1px solid #eee;
  line-height: 1.4;
}

.log-time {
  color: #909399;
  margin-right: 8px;
}

.log-message {
  font-family: 'Consolas', monospace;
}

.log-info {
  color: #606266;
}

.log-trade {
  color: #67c23a;
  font-weight: bold;
}

.log-warning {
  color: #e6a23c;
}

.log-error {
  color: #f56c6c;
  font-weight: bold;
}

.variables-grid {
  display: grid;
  grid-template-columns: 1fr 1.5fr 0.8fr;
  gap: 1px;
  background-color: #dcdfe6;
}

.grid-header, .grid-item {
  padding: 6px 8px;
  background-color: white;
}

.grid-header {
  font-weight: bold;
  background-color: #f5f7fa;
}

.signal-event {
  padding: 8px 5px;
  border-left: 3px solid;
  margin-bottom: 8px;
  background-color: white;
}

.buy {
  border-left-color: #f56c6c;
}

.sell {
  border-left-color: #67c23a;
}

.signal-time {
  color: #909399;
  font-size: 11px;
  margin-bottom: 3px;
}

.signal-info {
  display: flex;
  gap: 10px;
}

.signal-symbol {
  font-weight: bold;
}
</style>