<!-- 在现有StrategyEditor.vue基础上添加以下功能 -->
<template>
  <StrategyLayout>
    <template #header>
      <div class="editor-header">
        <div class="strategy-info">
          <h2>{{ strategy.name }}</h2>
          <el-tag :type="statusType[strategy.status]">
            {{ statusText[strategy.status] }}
          </el-tag>
        </div>
        <div class="header-actions">
          <el-button-group>
            <el-button
              :type="strategy.status === 'running' ? 'danger' : 'success'"
              @click="toggleStrategy"
            >
              {{ strategy.status === 'running' ? '停止策略' : '启动策略' }}
            </el-button>
            <el-button type="primary" @click="saveStrategy">保存</el-button>
            <el-button @click="runBacktest">回测</el-button>
          </el-button-group>
        </div>
      </div>
    </template>

    <template #editor>
      <!-- 原有代码编辑器 -->
      <CodeEditor
        v-model="strategy.code"
        language="python"
        :readOnly="isReadOnly"
        @save="saveStrategy"
      />
    </template>

    <template #config>
      <!-- 增强参数配置 -->
      <div class="config-section">
        <h3>策略参数配置</h3>
        <el-form label-width="100px">
          <el-form-item
            v-for="(param, key) in strategy.parameters"
            :key="key"
            :label="paramLabels[key]"
          >
            <el-input-number
              v-model="strategy.parameters[key]"
              :min="paramMins[key]"
              :max="paramMaxs[key]"
              :step="paramSteps[key]"
              size="small"
            />
            <span class="param-desc">{{ paramDescs[key] }}</span>
          </el-form-item>
        </el-form>
      </div>

      <div class="config-section">
        <h3>股票池配置</h3>
        <StockPoolSelector
          v-model="strategy.stockPool"
          :multiple="true"
        />
      </div>

      <div class="config-section">
        <h3>回测设置</h3>
        <!-- 原有回测设置 -->
      </div>
    </template>

    <template #monitor>
      <!-- 实时监控增强 -->
      <div class="monitor-tabs">
        <el-tabs v-model="activeMonitorTab">
          <el-tab-pane label="实时日志" name="logs">
            <BacktestLogs :logs="logs" />
          </el-tab-pane>
          <el-tab-pane label="变量监控" name="variables">
            <VariableMonitor :variables="variables" />
          </el-tab-pane>
          <el-tab-pane label="信号跟踪" name="signals">
            <SignalTimeline :signals="signals" />
          </el-tab-pane>
          <el-tab-pane label="性能分析" name="performance">
            <RealTimePerformance :metrics="performanceMetrics" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>
  </StrategyLayout>
</template>

<script>
// 添加新的导入
import StockPoolSelector from '@/components/strategy/StockPoolSelector.vue'
import RealTimePerformance from '@/components/strategy/RealTimePerformance.vue'
import StrategyLayout from "@/layouts/StrategyLayout.vue";
import BacktestLogs from "@/components/strategy/BacktestLogs.vue";
import VariableMonitor from "@/components/strategy/VariableMonitor.vue";
import SignalTimeline from "@/views/Signal/SignalTimeline.vue";

export default {
  components: {
    SignalTimeline,
    VariableMonitor,
    BacktestLogs,
    StrategyLayout,
    // ...原有组件
    StockPoolSelector,
    RealTimePerformance
  },
  data() {
    return {
      activeMonitorTab: 'logs',
      performanceMetrics: {},
      // 参数描述信息
      paramLabels: {
        fastPeriod: '快线周期',
        slowPeriod: '慢线周期',
        tradeSize: '仓位比例'
      },
      paramDescs: {
        fastPeriod: '短期均线周期，通常5-20',
        slowPeriod: '长期均线周期，通常20-60',
        tradeSize: '每次交易仓位比例，0-1之间'
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
  methods: {
    async toggleStrategy() {
      try {
        if (this.strategy.status === 'running') {
          await this.stopStrategy(this.strategy.id)
        } else {
          await this.startStrategy(this.strategy.id)
        }
        this.$message.success('操作成功')
      } catch (error) {
        this.$message.error('操作失败: ' + error.message)
      }
    }
  }
}
</script>

<style scoped>
.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
}

.strategy-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.param-desc {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.monitor-tabs {
  height: 100%;
}
</style>