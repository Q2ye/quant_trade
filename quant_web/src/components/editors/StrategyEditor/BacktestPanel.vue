<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useStrategyStore } from '@/store/modules/strategy'
import { ElMessage } from 'element-plus'

const strategyStore = useStrategyStore()

// 回测配置
const backtestConfig = reactive({
  // 时间范围
  startDate: '2023-01-01',
  endDate: '2023-12-31',

  // 资金配置
  initialCapital: 1000000,
  commission: 0.0003, // 佣金率
  tax: 0.001, // 印花税
  slippage: 0.001, // 滑点

  // 回测选项
  frequency: 'daily', // daily, minutely
  benchmark: '000300.SH', // 基准指数

  // 高级选项
  enableShort: false,
  maxPositionRatio: 1.0
})

// 回测状态
const backtestStatus = ref<'idle' | 'running' | 'completed' | 'error'>('idle')
const backtestProgress = ref(0)
const backtestResult = ref<any>(null)

// 可用的基准指数
const benchmarkOptions = [
  { label: '沪深300', value: '000300.SH' },
  { label: '上证指数', value: '000001.SH' },
  { label: '深证成指', value: '399001.SZ' },
  { label: '创业板指', value: '399006.SZ' }
]

// 频率选项
const frequencyOptions = [
  { label: '日线', value: 'daily' },
  { label: '分钟线', value: 'minutely' }
]

// 验证配置
const validateConfig = () => {
  if (!backtestConfig.startDate || !backtestConfig.endDate) {
    ElMessage.error('请选择回测时间范围')
    return false
  }

  if (backtestConfig.initialCapital <= 0) {
    ElMessage.error('初始资金必须大于0')
    return false
  }

  if (new Date(backtestConfig.startDate) >= new Date(backtestConfig.endDate)) {
    ElMessage.error('开始时间必须早于结束时间')
    return false
  }

  return true
}

// 执行回测
const runBacktest = async () => {
  if (!validateConfig()) return

  backtestStatus.value = 'running'
  backtestProgress.value = 0

  try {
    // 模拟进度更新
    const progressInterval = setInterval(() => {
      backtestProgress.value += Math.random() * 10
      if (backtestProgress.value >= 100) {
        clearInterval(progressInterval)
        backtestProgress.value = 100
      }
    }, 200)

    // 调用回测API
    const result = await strategyStore.runBacktest(backtestConfig)
    backtestResult.value = result
    backtestStatus.value = 'completed'

    ElMessage.success('回测完成')
  } catch (error) {
    backtestStatus.value = 'error'
    ElMessage.error('回测执行失败')
  }
}

// 停止回测
const stopBacktest = () => {
  backtestStatus.value = 'idle'
  backtestProgress.value = 0
}

// 导出结果
const exportResult = () => {
  if (!backtestResult.value) {
    ElMessage.warning('没有可导出的结果')
    return
  }

  // 实现导出逻辑
  ElMessage.success('导出成功')
}

// 重置配置
const resetConfig = () => {
  Object.assign(backtestConfig, {
    startDate: '2023-01-01',
    endDate: '2023-12-31',
    initialCapital: 1000000,
    commission: 0.0003,
    tax: 0.001,
    slippage: 0.001,
    frequency: 'daily',
    benchmark: '000300.SH',
    enableShort: false,
    maxPositionRatio: 1.0
  })
}
</script>

<template>
  <div class="backtest-panel">
    <div class="panel-header">
      <h3>回测配置</h3>
      <div class="header-actions">
        <el-button
          size="small"
          @click="resetConfig"
          :disabled="backtestStatus === 'running'"
        >
          重置
        </el-button>
        <el-button
          type="primary"
          size="small"
          @click="runBacktest"
          :loading="backtestStatus === 'running'"
          :disabled="backtestStatus === 'running'"
        >
          {{ backtestStatus === 'running' ? '回测中...' : '执行回测' }}
        </el-button>
      </div>
    </div>

    <div class="config-form">
      <!-- 基本配置 -->
      <el-card class="config-section">
        <template #header>
          <span>基本配置</span>
        </template>

        <el-form :model="backtestConfig" label-width="120px">
          <el-form-item label="时间范围">
            <el-date-picker
              v-model="backtestConfig.startDate"
              type="date"
              placeholder="开始日期"
              style="width: 48%; margin-right: 4%;"
            />
            <el-date-picker
              v-model="backtestConfig.endDate"
              type="date"
              placeholder="结束日期"
              style="width: 48%;"
            />
          </el-form-item>

          <el-form-item label="初始资金">
            <el-input-number
              v-model="backtestConfig.initialCapital"
              :min="10000"
              :step="10000"
              controls-position="right"
            />
            <span class="unit">元</span>
          </el-form-item>

          <el-form-item label="回测频率">
            <el-select v-model="backtestConfig.frequency">
              <el-option
                v-for="item in frequencyOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="基准指数">
            <el-select v-model="backtestConfig.benchmark">
              <el-option
                v-for="item in benchmarkOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 交易成本 -->
      <el-card class="config-section">
        <template #header>
          <span>交易成本</span>
        </template>

        <el-form :model="backtestConfig" label-width="120px">
          <el-form-item label="佣金费率">
            <el-input-number
              v-model="backtestConfig.commission"
              :min="0"
              :step="0.0001"
              :precision="4"
              controls-position="right"
            />
            <span class="unit">%</span>
          </el-form-item>

          <el-form-item label="印花税">
            <el-input-number
              v-model="backtestConfig.tax"
              :min="0"
              :step="0.0001"
              :precision="4"
              controls-position="right"
            />
            <span class="unit">%</span>
          </el-form-item>

          <el-form-item label="滑点">
            <el-input-number
              v-model="backtestConfig.slippage"
              :min="0"
              :step="0.0001"
              :precision="4"
              controls-position="right"
            />
            <span class="unit">%</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 高级选项 -->
      <el-card class="config-section">
        <template #header>
          <span>高级选项</span>
        </template>

        <el-form :model="backtestConfig" label-width="120px">
          <el-form-item label="允许卖空">
            <el-switch v-model="backtestConfig.enableShort" />
          </el-form-item>

          <el-form-item label="最大持仓比例">
            <el-slider
              v-model="backtestConfig.maxPositionRatio"
              :min="0.1"
              :max="1"
              :step="0.1"
              show-stops
            />
            <span class="slider-value">{{ (backtestConfig.maxPositionRatio * 100).toFixed(0) }}%</span>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <!-- 进度显示 -->
    <div v-if="backtestStatus === 'running'" class="progress-section">
      <el-progress
        :percentage="backtestProgress"
        :status="backtestProgress === 100 ? 'success' : undefined"
        :show-text="false"
      />
      <div class="progress-text">回测进行中... {{ backtestProgress.toFixed(0) }}%</div>
      <el-button size="small" @click="stopBacktest">停止</el-button>
    </div>

    <!-- 结果展示 -->
    <div v-if="backtestStatus === 'completed' && backtestResult" class="result-section">
      <div class="result-header">
        <h4>回测结果</h4>
        <el-button size="small" @click="exportResult">导出结果</el-button>
      </div>

      <div class="result-metrics">
        <div class="metric-item">
          <div class="metric-label">年化收益率</div>
          <div class="metric-value" :class="{ positive: backtestResult.annualReturn > 0 }">
            {{ (backtestResult.annualReturn * 100).toFixed(2) }}%
          </div>
        </div>

        <div class="metric-item">
          <div class="metric-label">夏普比率</div>
          <div class="metric-value">{{ backtestResult.sharpeRatio.toFixed(2) }}</div>
        </div>

        <div class="metric-item">
          <div class="metric-label">最大回撤</div>
          <div class="metric-value negative">{{ (backtestResult.maxDrawdown * 100).toFixed(2) }}%</div>
        </div>

        <div class="metric-item">
          <div class="metric-label">总交易次数</div>
          <div class="metric-value">{{ backtestResult.totalTrades }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.backtest-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color);
}

.config-form {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.config-section {
  margin-bottom: 16px;
}

.config-section:last-child {
  margin-bottom: 0;
}

.unit {
  margin-left: 8px;
  color: var(--el-text-color-secondary);
}

.slider-value {
  margin-left: 16px;
  min-width: 40px;
  text-align: center;
}

.progress-section {
  padding: 16px;
  border-top: 1px solid var(--el-border-color);
  text-align: center;
}

.progress-text {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
}

.result-section {
  padding: 16px;
  border-top: 1px solid var(--el-border-color);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.result-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.metric-item {
  text-align: center;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
}

.metric-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
}

.metric-value.positive {
  color: #f56c6c;
}

.metric-value.negative {
  color: #67c23a;
}
</style>