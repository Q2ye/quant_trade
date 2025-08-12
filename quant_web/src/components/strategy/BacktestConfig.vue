<!--回测配置面板-->
<script>
import TimeRangeSlider from '../data/TimeRangeSlider.vue'
import ParamSlider from '../strategy/ParamSlider.vue'

export default {
  name: "BacktestConfig",
  components: {
    TimeRangeSlider,
    ParamSlider
  },
  props: {
    strategy: {
      type: Object,
      required: true
    }
  },
  data() {
    return {
      config: {
        capital: 1000000,
        commission: 0.0003,
        slippage: 0.001,
        timeRange: [
          new Date(new Date().setFullYear(new Date().getFullYear() - 1)),
          new Date()
        ],
        frequency: 'daily',
        benchmark: '000300.SH',
        params: {}
      },
      frequencyOptions: [
        { value: 'daily', label: '日线' },
        { value: 'weekly', label: '周线' },
        { value: 'monthly', label: '月线' },
        { value: '60min', label: '60分钟' },
        { value: '30min', label: '30分钟' }
      ],
      benchmarkOptions: [
        { value: '000001.SH', label: '上证指数' },
        { value: '399001.SZ', label: '深证成指' },
        { value: '000300.SH', label: '沪深300' },
        { value: '000905.SH', label: '中证500' },
        { value: '399006.SZ', label: '创业板指' }
      ]
    }
  },
  watch: {
    strategy: {
      immediate: true,
      handler(newVal) {
        if (newVal && newVal.params) {
          // 初始化参数
          for (const [key, param] of Object.entries(newVal.params)) {
            this.$set(this.config.params, key, param.default)
          }
        }
      }
    }
  },
  methods: {
    handleTimeRangeChange(range) {
      this.config.timeRange = range
    },

    handleParamChange(paramName, value) {
      this.$set(this.config.params, paramName, value)
    },

    startBacktest() {
      this.$emit('start', {...this.config})
    }
  }
}
</script>

<template>
  <div class="backtest-config">
    <h3 class="section-title">回测配置</h3>

    <div class="config-section">
      <h4>资金设置</h4>
      <div class="config-row">
        <div class="config-item">
          <label>初始资金 (元)</label>
          <el-input-number
            v-model="config.capital"
            :min="10000"
            :step="10000"
            :precision="0"
            controls-position="right" />
        </div>

        <div class="config-item">
          <label>手续费 (%)</label>
          <el-input-number
            v-model="config.commission"
            :min="0"
            :max="0.05"
            :step="0.0001"
            :precision="4"
            controls-position="right" />
        </div>

        <div class="config-item">
          <label>滑点 (%)</label>
          <el-input-number
            v-model="config.slippage"
            :min="0"
            :max="0.05"
            :step="0.0001"
            :precision="4"
            controls-position="right" />
        </div>
      </div>
    </div>

    <div class="config-section">
      <h4>时间范围</h4>
      <time-range-slider
        v-model="config.timeRange"
        @change="handleTimeRangeChange" />
    </div>

    <div class="config-section">
      <h4>回测周期</h4>
      <div class="config-row">
        <div class="config-item">
          <label>数据频率</label>
          <el-select v-model="config.frequency">
            <el-option
              v-for="item in frequencyOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value" />
          </el-select>
        </div>

        <div class="config-item">
          <label>基准指数</label>
          <el-select v-model="config.benchmark">
            <el-option
              v-for="item in benchmarkOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value" />
          </el-select>
        </div>
      </div>
    </div>

    <div class="config-section" v-if="strategy.params">
      <h4>策略参数</h4>
      <div class="params-grid">
        <param-slider
          v-for="(param, name) in strategy.params"
          :key="name"
          :param-name="name"
          :config="param"
          :value="config.params[name]"
          @change="handleParamChange" />
      </div>
    </div>

    <div class="action-bar">
      <el-button
        type="primary"
        icon="el-icon-video-play"
        @click="startBacktest">
        开始回测
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.backtest-config {
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}

.section-title {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #eaeaea;
  color: #303133;
}

.config-section {
  margin-bottom: 25px;
}

.config-section h4 {
  margin: 0 0 15px 0;
  font-size: 14px;
  font-weight: 600;
  color: #606266;
}

.config-row {
  display: flex;
  gap: 20px;
}

.config-item {
  flex: 1;
}

.config-item label {
  display: block;
  margin-bottom: 8px;
  font-size: 13px;
  color: #909399;
}

.params-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 15px;
}

.action-bar {
  margin-top: 20px;
  text-align: center;
}
</style>