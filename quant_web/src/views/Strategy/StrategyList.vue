<template>
  <div class="strategy-list">
    <div class="header">
      <h2>策略管理</h2>
      <el-button type="primary" icon="el-icon-plus" @click="createStrategy">
        新建策略
      </el-button>
    </div>

    <el-table :data="strategies" style="width: 100%">
      <el-table-column prop="id" label="ID" width="80"></el-table-column>
      <el-table-column prop="name" label="策略名称" width="150"></el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType[row.status]">
            {{ statusText[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="className" label="策略类" width="150"></el-table-column>
      <el-table-column label="基础绩效" width="120">
        <template #default="{ row }">
          {{ (row.performance?.annualReturn * 100 || 0).toFixed(2) }}%
        </template>
      </el-table-column>
      <el-table-column prop="updatedAt" label="更新时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.updatedAt) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button size="mini" @click="editStrategy(row)">编辑</el-button>
          <el-button
            size="mini"
            :type="row.status === 'running' ? 'danger' : 'success'"
            @click="toggleStrategy(row)"
          >
            {{ row.status === 'running' ? '停止' : '启动' }}
          </el-button>
          <el-button size="mini" @click="viewReport(row)">报告</el-button>
          <el-dropdown trigger="click">
            <el-button size="mini">
              更多<i class="el-icon-arrow-down el-icon--right"></i>
            </el-button>
            <el-dropdown-menu slot="dropdown">
              <el-dropdown-item @click.native="cloneStrategy(row)">克隆</el-dropdown-item>
              <el-dropdown-item @click.native="exportStrategy(row)">导出</el-dropdown-item>
              <el-dropdown-item
                class="danger-item"
                @click.native="deleteStrategy(row)"
              >
                删除
              </el-dropdown-item>
            </el-dropdown-menu>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建/编辑策略对话框 -->
    <el-dialog
      :title="dialogTitle"
      :visible.sync="showDialog"
      width="600px"
    >
      <el-form :model="currentStrategy" label-width="100px">
        <el-form-item label="策略名称" required>
          <el-input v-model="currentStrategy.name"></el-input>
        </el-form-item>
        <el-form-item label="策略描述">
          <el-input
            type="textarea"
            v-model="currentStrategy.description"
            :rows="3"
          ></el-input>
        </el-form-item>
        <el-form-item label="策略类型">
          <el-select v-model="currentStrategy.type">
            <el-option label="趋势跟踪" value="trend"></el-option>
            <el-option label="均值回归" value="mean_reversion"></el-option>
            <el-option label="套利策略" value="arbitrage"></el-option>
            <el-option label="市场中性" value="market_neutral"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="基础参数">
          <div class="param-grid">
            <div v-for="(param, key) in currentStrategy.parameters" :key="key" class="param-item">
              <div class="param-label">{{ paramLabels[key] }}</div>
              <el-input-number
                v-model="currentStrategy.parameters[key]"
                :min="paramMins[key]"
                :max="paramMaxs[key]"
                :step="paramSteps[key]"
                size="small"
              ></el-input-number>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <span slot="footer" class="dialog-footer">
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveStrategy">保存</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'

export default {
  name: 'StrategyList',
  data() {
    return {
      showDialog: false,
      isEditing: false,
      currentStrategy: this.getDefaultStrategy(),
      statusType: {
        running: 'success',
        stopped: 'info',
        error: 'danger'
      },
      statusText: {
        running: '运行中',
        stopped: '已停止',
        error: '异常'
      },
      paramLabels: {
        fastPeriod: '快线周期',
        slowPeriod: '慢线周期',
        tradeSize: '仓位比例'
      },
      paramMins: {
        fastPeriod: 1,
        slowPeriod: 5,
        tradeSize: 0.1
      },
      paramMaxs: {
        fastPeriod: 50,
        slowPeriod: 100,
        tradeSize: 1.0
      },
      paramSteps: {
        fastPeriod: 1,
        slowPeriod: 5,
        tradeSize: 0.05
      }
    }
  },
  computed: {
    ...mapState('strategy', ['strategies']),
    dialogTitle() {
      return this.isEditing ? '编辑策略' : '新建策略'
    }
  },
  methods: {
    ...mapActions('strategy', [
      'loadStrategies',
      'createStrategy',
      'updateStrategy',
      'deleteStrategy',
      'startStrategy',
      'stopStrategy'
    ]),

    getDefaultStrategy() {
      return {
        id: null,
        name: '',
        description: '',
        type: 'trend',
        className: 'DualMovingAverage',
        parameters: {
          fastPeriod: 5,
          slowPeriod: 20,
          tradeSize: 0.95
        },
        status: 'stopped'
      }
    },

    createStrategy() {
      this.currentStrategy = this.getDefaultStrategy()
      this.isEditing = false
      this.showDialog = true
    },

    editStrategy(strategy) {
      this.currentStrategy = { ...strategy }
      this.isEditing = true
      this.showDialog = true
    },

    async saveStrategy() {
      try {
        if (this.isEditing) {
          await this.updateStrategy(this.currentStrategy)
        } else {
          await this.createStrategy(this.currentStrategy)
        }
        this.showDialog = false
        this.$message.success('保存成功')
      } catch (error) {
        this.$message.error('保存失败: ' + error.message)
      }
    },

    async toggleStrategy(strategy) {
      try {
        if (strategy.status === 'running') {
          await this.stopStrategy(strategy.id)
        } else {
          await this.startStrategy(strategy.id)
        }
      } catch (error) {
        this.$message.error('操作失败: ' + error.message)
      }
    },

    viewReport(strategy) {
      this.$router.push({
        name: 'BacktestReport',
        params: { id: strategy.id }
      })
    },

    cloneStrategy(strategy) {
      this.currentStrategy = {
        ...strategy,
        id: null,
        name: strategy.name + '_副本'
      }
      this.isEditing = false
      this.showDialog = true
    },

    exportStrategy(strategy) {
      // 实现导出逻辑
      const dataStr = JSON.stringify(strategy, null, 2)
      const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr)

      const exportFileDefaultName = `${strategy.name}.json`

      const linkElement = document.createElement('a')
      linkElement.setAttribute('href', dataUri)
      linkElement.setAttribute('download', exportFileDefaultName)
      linkElement.click()
    },

    formatDate(date) {
      return new Date(date).toLocaleString()
    }
  },
  mounted() {
    this.loadStrategies()
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

.param-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.param-label {
  font-size: 12px;
  color: #606266;
}

.danger-item {
  color: #f56c6c;
}
</style>