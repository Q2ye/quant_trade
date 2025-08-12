<!--日志查看-->
<!--日志查看-->
<template>
  <div class="log-viewer">
    <el-card>
      <div slot="header">
        <el-row>
          <el-col :span="8">
            <span>系统日志</span>
          </el-col>
          <el-col :span="16" style="text-align: right;">
            <el-select
              v-model="logLevel"
              multiple
              collapse-tags
              placeholder="日志级别"
              size="mini"
              style="width: 200px; margin-right: 10px;">
              <el-option label="INFO" value="INFO"></el-option>
              <el-option label="WARNING" value="WARNING"></el-option>
              <el-option label="ERROR" value="ERROR"></el-option>
              <el-option label="DEBUG" value="DEBUG"></el-option>
            </el-select>

            <el-input
              v-model="searchKeyword"
              placeholder="搜索日志内容"
              size="mini"
              style="width: 200px; margin-right: 10px;">
              <i slot="prefix" class="el-input__icon el-icon-search"></i>
            </el-input>

            <el-button
              type="primary"
              size="mini"
              @click="loadLogs">
              查询
            </el-button>

            <el-button
              size="mini"
              @click="clearLogs">
              清空
            </el-button>
          </el-col>
        </el-row>
      </div>

      <div class="log-container">
        <div
          v-for="(log, index) in filteredLogs"
          :key="index"
          class="log-item"
          :class="log.level.toLowerCase()">
          <span class="timestamp">{{ log.timestamp }}</span>
          <span class="level" :class="log.level.toLowerCase()">{{ log.level }}</span>
          <span class="source">[{{ log.source }}]</span>
          <span class="message">{{ log.message }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  name: "LogViewer",
  data() {
    return {
      logs: [],
      filteredLogs: [],
      logLevel: ['INFO', 'WARNING', 'ERROR'],
      searchKeyword: ''
    }
  },
  mounted() {
    this.loadLogs();
  },
  methods: {
    loadLogs() {
      // 模拟日志数据
      this.logs = [
        {
          timestamp: '2023-08-09 10:05:32',
          level: 'INFO',
          source: 'DataSync',
          message: '日线数据同步完成，新增记录 125 条'
        },
        {
          timestamp: '2023-08-09 09:45:18',
          level: 'WARNING',
          source: 'StrategyEngine',
          message: '策略 MA_Crossover 在股票 000001.SH 上产生交易信号'
        },
        {
          timestamp: '2023-08-09 09:30:05',
          level: 'INFO',
          source: 'TradeEngine',
          message: '交易引擎启动成功，连接券商服务器'
        },
        {
          timestamp: '2023-08-08 16:15:42',
          level: 'ERROR',
          source: 'BacktestEngine',
          message: '回测任务失败：策略代码语法错误'
        },
        {
          timestamp: '2023-08-08 15:00:22',
          level: 'DEBUG',
          source: 'RiskManager',
          message: '风险检查通过：单股仓位未超过阈值'
        }
      ];

      this.filterLogs();
    },
    filterLogs() {
      this.filteredLogs = this.logs.filter(log => {
        // 日志级别过滤
        if (this.logLevel.length > 0 && !this.logLevel.includes(log.level)) {
          return false;
        }

        // 关键词搜索
        if (this.searchKeyword && !log.message.includes(this.searchKeyword)) {
          return false;
        }

        return true;
      });
    },
    clearLogs() {
      this.logs = [];
      this.filteredLogs = [];
    }
  },
  watch: {
    logLevel() {
      this.filterLogs();
    },
    searchKeyword() {
      this.filterLogs();
    }
  }
}
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