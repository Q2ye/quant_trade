<!--数据同步-->
<template>
  <div class="data-sync bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">数据同步管理</h1>
          <p class="page-description">配置和管理各数据源的同步任务，查看同步状态与历史记录</p>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-card title="数据源状态" class="sync-card">
        <div class="status-grid">
        <div
          class="status-item"
          v-for="source in dataSources"
          :key="source.name"
        >
          <div class="source-name">{{ source.name }}</div>
          <div class="source-status">
            <n-tag :type="source.status === 'connected' ? 'success' : 'error'">
              {{ source.status === "connected" ? "已连接" : "未连接" }}
            </n-tag>
          </div>
          <div class="last-sync">
            最后同步: {{ source.lastSync || "从未同步" }}
          </div>
          <n-button
            size="small"
            type="primary"
            @click="syncDataSource(source.name)"
            :loading="source.syncing"
            :disabled="source.status === 'disconnected'"
          >
            {{ source.status === "disconnected" ? "无法同步" : "同步数据" }}
          </n-button>
        </div>
      </div>
    </n-card>

    <n-card title="同步历史" class="sync-card">
      <template #header-extra>
        <div class="filter-controls">
          <n-select
            v-model:value="filterStatus"
            placeholder="全部状态"
            clearable
            size="small"
            style="width: 100px"
            :options="statusOptions"
          />
          <n-select
            v-model:value="filterSource"
            placeholder="全部数据源"
            clearable
            size="small"
            style="width: 120px"
            :options="sourceOptions"
          />
          <n-date-picker
            v-model:value="dateRange"
            type="daterange"
            clearable
            size="small"
            value-format="yyyy-MM-dd"
          />
        </div>
      </template>

      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="filteredHistory"
          :pagination="paginationConfig"
          :max-height="400"
          :bordered="false"
          size="small"
        >
          <template #empty>
            <n-empty :description="emptyText" />
          </template>
        </n-data-table>
      </n-spin>
    </n-card>
    </div><!-- .main-content -->
  </div>
</template>

<script>
import { h } from "vue";
import { NTag } from "naive-ui";

export default {
  data() {
    return {
      dataSources: [
        {
          name: "Tushare",
          status: "connected",
          lastSync: "2023-08-08 15:30:21",
          syncing: false,
        },
        {
          name: "Baostock",
          status: "connected",
          lastSync: "2023-08-08 15:32:45",
          syncing: false,
        },
        {
          name: "Wind",
          status: "disconnected",
          lastSync: null,
          syncing: false,
        },
      ],
      dateRange: null,
      filterStatus: null,
      filterSource: null,
      syncHistory: [],
      loading: false,
      statusOptions: [
        { label: "成功", value: "success" },
        { label: "失败", value: "failed" },
      ],
      paginationConfig: {
        pageSize: 10,
        pageSizes: [5, 10, 20, 50],
        showSizePicker: true,
        showQuickJumper: true,
      },
    };
  },
  computed: {
    sourceOptions() {
      return this.dataSources.map((s) => ({ label: s.name, value: s.name }));
    },
    columns() {
      return [
        { title: "日期", key: "date", width: 120, sorter: true },
        { title: "数据源", key: "source", width: 120 },
        { title: "数据类型", key: "type", width: 120 },
        {
          title: "状态",
          key: "status",
          width: 100,
          render: (row) =>
            h(
              NTag,
              {
                type: row.status === "success" ? "success" : "error",
                size: "small",
              },
              { default: () => (row.status === "success" ? "成功" : "失败") },
            ),
        },
        {
          title: "记录数",
          key: "records",
          width: 100,
          sorter: (a, b) => a.records - b.records,
        },
        { title: "耗时", key: "duration", width: 100 },
        { title: "消息", key: "message" },
      ];
    },
    filteredHistory() {
      return this.syncHistory.filter((item) => {
        const datePass =
          !this.dateRange ||
          this.dateRange.length === 0 ||
          (item.date >= this.dateRange[0] && item.date <= this.dateRange[1]);
        const statusPass =
          !this.filterStatus || item.status === this.filterStatus;
        const sourcePass =
          !this.filterSource || item.source === this.filterSource;
        return datePass && statusPass && sourcePass;
      });
    },
    emptyText() {
      if (this.filteredHistory.length === 0) {
        const filters = [];
        if (this.dateRange && this.dateRange.length > 0)
          filters.push("日期筛选");
        if (this.filterStatus) filters.push("状态筛选");
        if (this.filterSource) filters.push("数据源筛选");
        return filters.length > 0
          ? `没有找到${filters.join("+")}的同步记录`
          : "暂无同步历史数据";
      }
      return "暂无数据";
    },
  },
  methods: {
    syncDataSource(sourceName) {
      const source = this.dataSources.find((s) => s.name === sourceName);
      if (source) {
        source.syncing = true;
        this.loading = true;
        setTimeout(() => {
          source.syncing = false;
          this.loading = false;
          const now = new Date();
          source.lastSync = `${now.toISOString().split("T")[0]} ${now.toTimeString().split(" ")[0]}`;
          this.syncHistory.unshift({
            date: now.toISOString().split("T")[0],
            source: sourceName,
            type: "全部数据",
            status: Math.random() > 0.2 ? "success" : "failed",
            records: Math.floor(Math.random() * 10000) + 5000,
            duration: `${Math.floor(Math.random() * 50) + 10}s`,
            message: Math.random() > 0.2 ? "同步成功" : "网络连接超时",
          });
          this.$message.success(`${sourceName} 数据同步完成`);
        }, 2000);
      }
    },
  },
  created() {
    const sources = ["Tushare", "Baostock"];
    const types = ["日线行情", "财务数据", "分钟行情", "公司信息", "宏观经济"];
    for (let i = 0; i < 30; i++) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      this.syncHistory.push({
        date: date.toISOString().split("T")[0],
        source: sources[Math.floor(Math.random() * sources.length)],
        type: types[Math.floor(Math.random() * types.length)],
        status: Math.random() > 0.3 ? "success" : "failed",
        records: Math.floor(Math.random() * 20000) + 1000,
        duration: `${Math.floor(Math.random() * 120) + 5}s`,
        message:
          Math.random() > 0.3
            ? "同步成功"
            : ["网络超时", "数据格式错误", "认证失败"][
                Math.floor(Math.random() * 3)
              ],
      });
    }
  },
};
</script>

<style scoped>
.data-sync {
  padding: 0;
  height: 100%;
  overflow-y: auto;
}

.sync-card {
  margin-bottom: 20px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.status-item {
  border: 1px solid var(--n-border-color);
  border-radius: 6px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.3s;
}

.status-item:hover {
  box-shadow: var(--n-box-shadow-2);
  transform: translateY(-3px);
}

.source-name {
  font-weight: bold;
  font-size: 16px;
  color: var(--n-text-color-1);
}

.source-status {
  margin: 5px 0;
}

.last-sync {
  font-size: 12px;
  color: var(--n-text-color-3);
}

.filter-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
