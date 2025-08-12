<!--数据同步-->
<template>
  <div class="data-sync">
    <h2>数据同步管理</h2>

    <el-card class="sync-status">
      <div slot="header" class="clearfix">
        <span>数据源状态</span>
      </div>
      <div class="status-grid">
        <div class="status-item" v-for="source in dataSources" :key="source.name">
          <div class="source-name">{{ source.name }}</div>
          <div class="source-status">
            <el-tag :type="source.status === 'connected' ? 'success' : 'danger'">
              {{ source.status === 'connected' ? '已连接' : '未连接' }}
            </el-tag>
          </div>
          <div class="last-sync">最后同步: {{ source.lastSync || '从未同步' }}</div>
          <el-button
            size="small"
            type="primary"
            @click="syncDataSource(source.name)"
            :loading="source.syncing"
            :disabled="source.status === 'disconnected'"
          >
            {{ source.status === 'disconnected' ? '无法同步' : '同步数据' }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="sync-history">
      <div slot="header" class="clearfix">
        <span>同步历史</span>
        <div style="float: right; display: flex; gap: 10px; align-items: center;">
          <el-select
            v-model="filterStatus"
            placeholder="全部状态"
            clearable
            style="width: 120px;"
          >
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>

          <el-select
            v-model="filterSource"
            placeholder="全部数据源"
            clearable
            style="width: 140px;"
          >
            <el-option
              v-for="source in dataSources"
              :key="source.name"
              :label="source.name"
              :value="source.name"
            />
          </el-select>

          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="yyyy-MM-dd"
          />
        </div>
      </div>

      <el-table
        :data="paginatedHistory"
        height="400"
        v-loading="loading"
        :empty-text="emptyText"
      >
        <el-table-column prop="date" label="日期" width="120" sortable />
        <el-table-column prop="source" label="数据源" width="120" />
        <el-table-column prop="type" label="数据类型" width="120" />
        <el-table-column prop="status" label="状态" width="100" sortable :sort-method="sortStatus">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="records" label="记录数" width="100" sortable />
        <el-table-column prop="duration" label="耗时" width="100" sortable />
        <el-table-column prop="message" label="消息" />
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
          :current-page="currentPage"
          :page-sizes="[5, 10, 20, 50]"
          :page-size="pageSize"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredHistory.length"
        />
      </div>
    </el-card>
  </div>
</template>

<script>
export default {
  data() {
    return {
      dataSources: [
        {
          name: 'Tushare',
          status: 'connected',
          lastSync: '2023-08-08 15:30:21',
          syncing: false
        },
        {
          name: 'Baostock',
          status: 'connected',
          lastSync: '2023-08-08 15:32:45',
          syncing: false
        },
        {
          name: 'Wind',
          status: 'disconnected',
          lastSync: null,
          syncing: false
        }
      ],
      dateRange: [],
      filterStatus: null,
      filterSource: null,
      syncHistory: [
        // 初始历史数据保持不变
      ],
      currentPage: 1,
      pageSize: 10,
      loading: false
    };
  },
  computed: {
    // 计算筛选后的历史记录
    filteredHistory() {
      return this.syncHistory.filter(item => {
        // 日期筛选
        const datePass = this.dateRange.length === 0 ||
          (item.date >= this.dateRange[0] && item.date <= this.dateRange[1]);

        // 状态筛选
        const statusPass = !this.filterStatus || item.status === this.filterStatus;

        // 数据源筛选
        const sourcePass = !this.filterSource || item.source === this.filterSource;

        return datePass && statusPass && sourcePass;
      });
    },

    // 分页数据
    paginatedHistory() {
      const start = (this.currentPage - 1) * this.pageSize;
      const end = start + this.pageSize;
      return this.filteredHistory.slice(start, end);
    },

    // 空状态提示文本
    emptyText() {
      if (this.filteredHistory.length === 0) {
        const filters = [];
        if (this.dateRange.length > 0) filters.push('日期筛选');
        if (this.filterStatus) filters.push('状态筛选');
        if (this.filterSource) filters.push('数据源筛选');

        return filters.length > 0
          ? `没有找到${filters.join('+')}的同步记录`
          : '暂无同步历史数据';
      }
      return '暂无数据';
    }
  },
  methods: {
    syncDataSource(sourceName) {
      const source = this.dataSources.find(s => s.name === sourceName);
      if (source) {
        source.syncing = true;
        this.loading = true;

        // 模拟同步过程
        setTimeout(() => {
          source.syncing = false;
          this.loading = false;

          // 更新最后同步时间
          const now = new Date();
          const dateStr = now.toISOString().split('T')[0];
          const timeStr = now.toTimeString().split(' ')[0];
          source.lastSync = `${dateStr} ${timeStr}`;

          // 添加到历史记录
          this.syncHistory.unshift({
            date: dateStr,
            source: sourceName,
            type: '全部数据',
            status: Math.random() > 0.2 ? 'success' : 'failed',
            records: Math.floor(Math.random() * 10000) + 5000,
            duration: `${Math.floor(Math.random() * 50) + 10}s`,
            message: Math.random() > 0.2 ? '同步成功' : '网络连接超时'
          });

          this.$message.success(`${sourceName} 数据同步完成`);
        }, 2000);
      }
    },

    // 状态排序方法
    sortStatus(a, b) {
      const statusOrder = { 'success': 1, 'failed': 2 };
      return statusOrder[a.status] - statusOrder[b.status];
    },

    handleSizeChange(size) {
      this.pageSize = size;
      this.currentPage = 1;
    },

    handleCurrentChange(page) {
      this.currentPage = page;
    }
  },
  // 初始化时加载更多测试数据
  created() {
    // 生成30天的随机历史数据
    const sources = ['Tushare', 'Baostock'];
    const types = ['日线行情', '财务数据', '分钟行情', '公司信息', '宏观经济'];

    for (let i = 0; i < 30; i++) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];

      this.syncHistory.push({
        date: dateStr,
        source: sources[Math.floor(Math.random() * sources.length)],
        type: types[Math.floor(Math.random() * types.length)],
        status: Math.random() > 0.3 ? 'success' : 'failed',
        records: Math.floor(Math.random() * 20000) + 1000,
        duration: `${Math.floor(Math.random() * 120) + 5}s`,
        message: Math.random() > 0.3 ? '同步成功' : ['网络超时', '数据格式错误', '认证失败'][Math.floor(Math.random()*3)]
      });
    }
  }
}
</script>

<style scoped>
.data-sync {
  padding: 20px;
}

.sync-status, .sync-history {
  margin-bottom: 20px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.status-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.3s;
}

.status-item:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transform: translateY(-3px);
}

.source-name {
  font-weight: bold;
  font-size: 16px;
}

.source-status {
  margin: 5px 0;
}

.last-sync {
  font-size: 12px;
  color: #909399;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>