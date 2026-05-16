<template>
  <div class="backtest-logs">
    <div class="log-controls">
      <button class="clear-btn" @click="clearLogs">清空日志</button>
      <button class="export-btn" @click="exportLogs">导出日志</button>
      <div class="log-filter">
        <label>
          <input v-model="filterLevels.info" type="checkbox" /> 信息
        </label>
        <label>
          <input v-model="filterLevels.warning" type="checkbox" /> 警告
        </label>
        <label>
          <input v-model="filterLevels.error" type="checkbox" /> 错误
        </label>
        <label>
          <input v-model="filterLevels.trade" type="checkbox" /> 交易
        </label>
      </div>
    </div>

    <div class="log-container">
      <div
        v-for="(log, index) in filteredLogs"
        :key="index"
        class="log-item"
        :class="logLevelClass(log.level)"
      >
        <span class="log-time">[{{ log.time }}]</span>
        <span class="log-level">{{ logLevelText(log.level) }}</span>
        <span class="log-message">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "BacktestLogs",
  props: {
    logs: {
      type: Array,
      default: () => [
        {
          time: "2023-08-12 09:30:05",
          level: "info",
          message: "回测初始化完成",
        },
        {
          time: "2023-08-12 09:35:22",
          level: "trade",
          message: "买入 600519.SH @1800.50 数量:100",
        },
        {
          time: "2023-08-12 10:15:47",
          level: "warning",
          message: "波动率超过阈值",
        },
        { time: "2023-08-12 11:30:00", level: "info", message: "午间休市" },
        {
          time: "2023-08-12 13:00:05",
          level: "trade",
          message: "卖出 000001.SZ @14.80 数量:200",
        },
        {
          time: "2023-08-12 14:20:15",
          level: "error",
          message: "连接超时，重试中...",
        },
      ],
    },
  },
  data() {
    return {
      filterLevels: {
        info: true,
        warning: true,
        error: true,
        trade: true,
      },
    };
  },
  computed: {
    filteredLogs() {
      return this.logs.filter((log) => this.filterLevels[log.level]);
    },
  },
  methods: {
    logLevelClass(level) {
      return `log-${level}`;
    },
    logLevelText(level) {
      const map = {
        info: "信息",
        warning: "警告",
        error: "错误",
        trade: "交易",
      };
      return map[level] || level;
    },
    clearLogs() {
      this.$emit("clear-logs");
    },
    exportLogs() {
      this.$emit("export-logs");
    },
  },
};
</script>

<style scoped>
.backtest-logs {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  font-family: "Consolas", "Courier New", monospace;
  font-size: 12px;
}

.log-controls {
  padding: 8px 10px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  align-items: center;
  gap: 15px;
}

.clear-btn,
.export-btn {
  padding: 5px 10px;
  background-color: #409eff;
  color: white;
  border: none;
  border-radius: 3px;
  cursor: pointer;
}

.export-btn {
  background-color: #67c23a;
}

.log-filter {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.log-filter label {
  display: flex;
  align-items: center;
  gap: 3px;
}

.log-container {
  flex: 1;
  overflow-y: auto;
  padding: 5px;
  background-color: #f8f8f8;
}

.log-item {
  padding: 5px 3px;
  border-bottom: 1px solid #eee;
  line-height: 1.4;
  display: flex;
  gap: 10px;
}

.log-time {
  color: #909399;
  min-width: 140px;
}

.log-level {
  min-width: 40px;
  font-weight: bold;
}

.log-info {
  color: #606266;
}

.log-trade {
  color: #67c23a;
}

.log-warning {
  color: #e6a23c;
}

.log-error {
  color: #f56c6c;
}
</style>
