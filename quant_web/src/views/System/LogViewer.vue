<!--日志查看-->
<template>
  <div class="log-viewer bg-gradient-mesh bg-noise">
    <n-card>
      <template #header>
        <n-grid :cols="24" :x-gap="12">
          <n-grid-item :span="8">
            <span>系统日志</span>
          </n-grid-item>
          <n-grid-item :span="16" style="text-align: right">
            <n-space justify="end" :size="8">
              <n-select
                v-model:value="logLevel"
                multiple
                placeholder="日志级别"
                size="small"
                style="width: 200px"
                :options="logLevelOptions"
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
            </n-space>
          </n-grid-item>
        </n-grid>
      </template>

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
      logLevelOptions: [
        { label: "INFO", value: "INFO" },
        { label: "WARNING", value: "WARNING" },
        { label: "ERROR", value: "ERROR" },
        { label: "DEBUG", value: "DEBUG" },
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
        return !(
          this.searchKeyword && !log.message.includes(this.searchKeyword)
        );
      });
    },
    clearLogs() {
      this.logs = [];
      this.filteredLogs = [];
    },
  },
  watch: {
    logLevel() {
      this.filterLogs();
    },
    searchKeyword() {
      this.filterLogs();
    },
  },
};
</script>

<style scoped>
.log-viewer {
  padding: 20px;
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
