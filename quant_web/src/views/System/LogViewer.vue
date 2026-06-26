<!--日志查看-->
<template>
  <div class="log-viewer bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">系统日志</h1>
            <p class="page-description">查看、搜索和导出系统运行日志</p>
        </div>
        <div class="header-actions">
          <n-select
            v-model:value="logLevel"
            multiple
            :max-tag-count="1"
            placeholder="日志级别"
            size="small"
            style="width: 160px"
            :options="logLevelOptions"
            @update:value="searchLogs"
          />
          <n-input
            v-model:value="searchKeyword"
            placeholder="搜索日志内容"
            size="small"
            clearable
            style="width: 200px"
            @keyup.enter="searchLogs"
          />
          <n-date-picker
            v-model:value="filterDate"
            type="date"
            placeholder="日期"
            size="small"
            clearable
            style="width: 140px"
            @update:value="searchLogs"
          />
          <n-button type="primary" size="small" @click="searchLogs">查询</n-button>
          <n-button size="small" @click="exportCSV">导出CSV</n-button>
        </div>
      </div>
    </div>
    <div class="main-content">
      <n-card :class="tokens.surface.card">
        <div class="log-container">
          <n-spin :show="loading">
            <n-result
              v-if="error"
              status="500"
              title="数据加载失败"
              description="请检查网络连接后重试"
            >
              <template #footer>
                <n-button type="primary" @click="searchLogs">重试</n-button>
              </template>
            </n-result>

            <template v-else>
              <div v-if="filteredLogs.length === 0 && !loading" class="empty-hint">
                <n-empty description="暂无日志记录" />
              </div>
              <div
                v-for="(log, index) in filteredLogs"
                :key="index"
                class="log-item"
                :class="log.level"
              >
                <span class="log-time">{{ formatTime(log.created_at) }}</span>
                <span class="log-level" :class="log.level">{{ log.level || 'INFO' }}</span>
                <span class="log-action">{{ log.action || '-' }}</span>
                <span class="log-msg">{{ log.details || log.message || '' }}</span>
              </div>
            </template>
          </n-spin>
        </div>
        <!-- 分页 -->
        <div class="log-pagination" v-if="total > pageSize">
          <n-pagination
            v-model:page="currentPage"
            :page-size="pageSize"
            :item-count="total"
            size="small"
            @update:page="searchLogs"
          />
        </div>
      </n-card>
    </div>
  </div>
</template>

<script>
import { tokens } from "@/styles/design-tokens"
import systemAPI from "@/api/system"

export default {
  name: "LogViewer",
  setup() {
    return { tokens }
  },
  data() {
    return {
      loading: false,
      error: false,
      filteredLogs: [],
      logLevel: ["INFO", "WARNING", "ERROR"],
      searchKeyword: "",
      filterDate: null,
      currentPage: 1,
      pageSize: 50,
      total: 0,
      logLevelOptions: [
        { label: "INFO", value: "INFO" },
        { label: "WARNING", value: "WARNING" },
        { label: "ERROR", value: "ERROR" },
        { label: "DEBUG", value: "DEBUG" },
      ],
    }
  },
  mounted() {
    this.searchLogs()
  },
  methods: {
    async searchLogs() {
      this.loading = true
      this.error = false
      try {
        const params = {
          page: this.currentPage,
          limit: this.pageSize,
        }
        if (this.logLevel.length > 0 && this.logLevel.length < 4) {
          params.level = this.logLevel[0] // API 接受单个 level
        }
        if (this.filterDate) {
          const d = new Date(this.filterDate)
          params.start_time = d.toISOString()
          params.end_time = new Date(d.getTime() + 86400000).toISOString()
        }

        const res = await systemAPI.getSystemLogs(params)
        // 应对两种响应格式：{ data, pagination } 或 { logs, total }
        this.filteredLogs = (res.data || res.logs || []).map(log => ({
          ...log,
          level: (log.log_level || log.level || "INFO").toLowerCase(),
        }))
        this.total = res.pagination?.total || res.total || this.filteredLogs.length
      } catch {
        this.error = true
      } finally {
        this.loading = false
      }
    },
    formatTime(ts) {
      if (!ts) return "--"
      return ts.replace("T", " ").slice(0, 19)
    },
    exportCSV() {
      const data = this.filteredLogs
      if (!data.length) return
      const header = "时间,级别,操作,详情\n"
      const rows = data
        .map(l => `${l.created_at || ""},${l.level},"${l.action || ""}","${(l.details || l.message || "").replace(/"/g, '""')}"`)
        .join("\n")
      const blob = new Blob(["﻿" + header + rows], { type: "text/csv;charset=utf-8" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `logs_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  },
}
</script>

<style scoped>
.log-viewer {
  padding: 0;
  padding-bottom: 24px;
  height: 100%;
  overflow-y: auto;
}

.log-container {
  height: 520px;
  overflow-y: auto;
  font-family: "Cascadia Code", "Fira Code", monospace;
  font-size: 13px;
  line-height: 1.6;
  background-color: var(--n-color-embedded, #1a1a2e);
  color: var(--n-text-color-2, #d4d4d4);
  padding: 12px;
  border-radius: 6px;
}

.log-item {
  padding: 3px 0;
  border-bottom: 1px solid var(--n-border-color, #333);
  display: flex;
  gap: 12px;
}

.log-time {
  color: var(--n-text-color-3, #6a9955);
  white-space: nowrap;
  min-width: 140px;
}

.log-level {
  font-weight: 600;
  min-width: 60px;
  text-align: center;
}
.log-level.info { color: #3794ff; }
.log-level.warning { color: #d7ba7d; }
.log-level.error { color: #f44747; }
.log-level.debug { color: #b5cea8; }

.log-action {
  color: #ce9178;
  min-width: 80px;
}
.log-msg {
  flex: 1;
  word-break: break-all;
}

.log-pagination {
  display: flex;
  justify-content: center;
  margin-top: 12px;
}

.empty-hint {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400px;
}
</style>
