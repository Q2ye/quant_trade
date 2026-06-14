<!--日志查看-->
<template>
  <div class="log-viewer bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">系统日志</h1>
        </div>
        <div class="header-actions">
          <n-select
            v-model:value="logLevel"
            multiple
            placeholder="日志级别"
            size="small"
            style="width: 180px"
            :options="logLevelOptions"
          />
          <n-select
            v-model:value="filterModule"
            placeholder="模块"
            size="small"
            clearable
            style="width: 140px"
            :options="moduleOptions"
          />
          <n-date-picker
            v-model:value="filterDate"
            type="date"
            placeholder="日期"
            size="small"
            clearable
            style="width: 140px"
          />
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索日志内容"
            size="small"
            clearable
            style="width: 200px"
          />
          <n-button type="primary" size="small" @click="loadLogs"
            >查询</n-button
          >
          <n-button size="small" @click="clearLogs">清空</n-button>
          <n-button size="small" @click="exportCSV">导出CSV</n-button>
        </div>
      </div>
    </div>
    <div class="main-content">
      <n-card>
        <div class="log-container">
          <n-spin :show="loading">
            <n-result
              v-if="error"
              status="500"
              title="数据加载失败"
              description="请检查网络连接后重试"
            >
              <template #footer>
                <n-button type="primary" @click="loadLogs">重试</n-button>
              </template>
            </n-result>

            <template v-else>
              <div
                v-for="(log, index) in filteredLogs"
                :key="index"
                class="log-item"
                :class="log.level.toLowerCase()"
              >
                <span class="timestamp">{{ log.timestamp }}</span>
                <span class="level" :class="log.level.toLowerCase()">{{
                  log.level
                }}</span>
                <span class="source">[{{ log.source }}]</span>
                <span class="message">{{ log.message }}</span>
              </div>
              <n-empty
                v-if="filteredLogs.length === 0"
                description="暂无日志记录"
              />
            </template>
          </n-spin>
        </div>
      </n-card>
    </div>
    <!-- .main-content -->
  </div>
</template>

<script>
export default {
  name: "LogViewer",
  data() {
    return {
      loading: false,
      error: false,
      logs: [],
      filteredLogs: [],
      logLevel: ["INFO", "WARNING", "ERROR"],
      searchKeyword: "",
      filterModule: null,
      filterDate: null,
      logLevelOptions: [
        { label: "INFO", value: "INFO" },
        { label: "WARNING", value: "WARNING" },
        { label: "ERROR", value: "ERROR" },
        { label: "DEBUG", value: "DEBUG" },
      ],
      moduleOptions: [
        { label: "数据同步", value: "DataSync" },
        { label: "策略引擎", value: "StrategyEngine" },
        { label: "交易引擎", value: "TradeEngine" },
        { label: "风控引擎", value: "RiskEngine" },
        { label: "回测引擎", value: "BacktestEngine" },
        { label: "系统", value: "System" },
      ],
    };
  },
  mounted() {
    this.loadLogs();
  },
  methods: {
    async loadLogs() {
      this.loading = true;
      this.error = false;
      try {
        await new Promise((r) => setTimeout(r, 300));
        this.logs = [
          {
            timestamp: "2023-08-09 10:05:32",
            level: "INFO",
            source: "DataSync",
            message: "日线数据同步完成，新增记录 125 条",
          },
          {
            timestamp: "2023-08-09 09:45:18",
            level: "WARNING",
            source: "StrategyEngine",
            message: "策略 MA_Crossover 在股票 000001.SH 上产生交易信号",
          },
          {
            timestamp: "2023-08-09 09:30:05",
            level: "INFO",
            source: "TradeEngine",
            message: "交易引擎启动成功，连接券商服务器",
          },
          {
            timestamp: "2023-08-08 16:15:42",
            level: "ERROR",
            source: "BacktestEngine",
            message: "回测任务失败：策略代码语法错误",
          },
          {
            timestamp: "2023-08-08 15:00:22",
            level: "DEBUG",
            source: "RiskManager",
            message: "风险检查通过：单股仓位未超过阈值",
          },
        ];
        this.filterLogs();
      } catch {
        this.error = true;
      } finally {
        this.loading = false;
      }
    },
    filterLogs() {
      this.filteredLogs = this.logs.filter((log) => {
        if (this.logLevel.length > 0 && !this.logLevel.includes(log.level))
          return false;
        if (this.searchKeyword && !log.message.includes(this.searchKeyword))
          return false;
        if (this.filterModule && log.source !== this.filterModule)
          return false;
        if (this.filterDate) {
          const logDate = (log.timestamp || "").slice(0, 10);
          const filterDateStr = new Date(this.filterDate).toISOString().slice(0, 10);
          if (logDate !== filterDateStr) return false;
        }
        return true;
      });
    },
    clearLogs() {
      this.logs = [];
      this.filteredLogs = [];
    },
    exportCSV() {
      const data = this.filteredLogs;
      if (!data.length) return;
      const header = "时间,级别,来源,消息\n";
      const rows = data
        .map((l) => `${l.timestamp},${l.level},${l.source},"${l.message}"`)
        .join("\n");
      const blob = new Blob(["﻿" + header + rows], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `logs_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    },
  },
  watch: {
    logLevel() { this.filterLogs(); },
    searchKeyword() { this.filterLogs(); },
    filterModule() { this.filterLogs(); },
    filterDate() { this.filterLogs(); },
  },
};
</script>

<style scoped>
.log-viewer {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.log-container {
  height: 600px;
  overflow-y: auto;
  font-family: monospace;
  font-size: 14px;
  line-height: 1.5;
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 10px;
  border-radius: 4px;
}

.log-item {
  padding: 4px 0;
  border-bottom: 1px solid #333;
}

.timestamp {
  color: #6a9955;
  margin-right: 15px;
}

.level {
  font-weight: bold;
  margin-right: 10px;
  padding: 2px 5px;
  border-radius: 3px;
}

.level.info {
  color: #3794ff;
}
.level.warning {
  color: #d7ba7d;
}
.level.error {
  color: #f44747;
}
.level.debug {
  color: #b5cea8;
}

.source {
  color: #ce9178;
  margin-right: 10px;
}
</style>
