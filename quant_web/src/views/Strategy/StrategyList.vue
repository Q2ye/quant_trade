<!--策略列表-->
<template>
  <div class="strategy-list">
    <div class="header">
      <h2>策略管理</h2>
      <div class="actions">
        <el-button type="primary" @click="createStrategy">
          <i class="el-icon-plus"></i> 新建策略
        </el-button>
        <el-input
          v-model="searchKeyword"
          placeholder="搜索策略..."
          prefix-icon="el-icon-search"
          style="width: 200px; margin-left: 15px;"
        />
      </div>
    </div>

    <el-table :data="filteredStrategies" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="策略名称" width="200">
        <template #default="{ row }">
          <div class="strategy-name">
            <span>{{ row.name }}</span>
            <el-tag v-if="row.status === 'running'" size="mini" type="success">运行中</el-tag>
            <el-tag v-if="row.isTemplate" size="mini" type="info">模板</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="类别" width="120" />
      <el-table-column prop="lastBacktest" label="最近回测" width="180">
        <template #default="{ row }">
          <div v-if="row.lastBacktest">
            {{ row.lastBacktest.date }} ({{ row.lastBacktest.result }})
          </div>
          <span v-else>未回测</span>
        </template>
      </el-table-column>
      <el-table-column prop="modifiedAt" label="最后修改" width="150" />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editStrategy(row)">编辑</el-button>
          <el-button size="small" @click="runBacktest(row)">回测</el-button>
          <el-button
            size="small"
            :type="row.status === 'running' ? 'danger' : 'success'"
            @click="toggleStrategyStatus(row)"
          >
            {{ row.status === 'running' ? '停止' : '运行' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex';

export default {
  data() {
    return {
      loading: false,
      searchKeyword: ''
    };
  },
  computed: {
    ...mapState('strategy', ['strategies']),
    filteredStrategies() {
      if (!this.searchKeyword) return this.strategies;

      const keyword = this.searchKeyword.toLowerCase();
      return this.strategies.filter(strategy =>
        strategy.name.toLowerCase().includes(keyword) ||
        strategy.description?.toLowerCase().includes(keyword) ||
        strategy.category?.toLowerCase().includes(keyword)
      );
    }
  },
  methods: {
    ...mapActions('strategy', ['fetchStrategies', 'startStrategy', 'stopStrategy']),

    createStrategy() {
      this.$router.push({ name: 'StrategyCreate' });
    },

    editStrategy(strategy) {
      this.$router.push({ name: 'StrategyEdit', params: { id: strategy.id } });
    },

    runBacktest(strategy) {
      this.$router.push({
        name: 'BacktestConfig',
        query: { strategyId: strategy.id }
      });
    },

    toggleStrategyStatus(strategy) {
      if (strategy.status === 'running') {
        this.stopStrategy(strategy.id);
      } else {
        this.startStrategy(strategy.id);
      }
    },

    async loadData() {
      this.loading = true;
      try {
        await this.fetchStrategies();
      } catch (error) {
        this.$message.error('加载策略列表失败: ' + error.message);
      } finally {
        this.loading = false;
      }
    }
  },
  mounted() {
    this.loadData();
  }
}
</script>

<style scoped>
.strategy-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  align-items: center;
}

.strategy-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>