<template>
  <div class="parameter-optimizer">
    <el-form :model="optimizationParams" label-width="120px">
      <el-form-item label="优化参数">
        <div v-for="(param, index) in optimizationParams.parameters" :key="index" class="param-item">
          <el-input v-model="param.name" placeholder="参数名" style="width: 120px" />
          <el-input-number v-model="param.min" :min="0" :step="1" placeholder="最小值" />
          <el-input-number v-model="param.max" :min="param.min + 1" :step="1" placeholder="最大值" />
          <el-input-number v-model="param.step" :min="1" :step="1" placeholder="步长" />
          <el-button type="danger" @click="removeParameter(index)">删除</el-button>
        </div>
        <el-button type="primary" @click="addParameter">添加参数</el-button>
      </el-form-item>

      <el-form-item label="优化目标">
        <el-select v-model="optimizationParams.objective">
          <el-option label="夏普比率" value="sharpe" />
          <el-option label="年化收益率" value="annualReturn" />
          <el-option label="卡玛比率" value="calmar" />
          <el-option label="最大回撤" value="maxDrawdown" />
        </el-select>
      </el-form-item>

      <el-form-item label="最大迭代次数">
        <el-input-number v-model="optimizationParams.maxIterations" :min="10" :max="1000" />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="runOptimization" :loading="optimizing">
          开始优化
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
export default {
  name: 'ParameterOptimizer',
  props: {
    strategy: {
      type: Object,
      default: null
    }
  },
  data() {
    return {
      optimizationParams: {
        parameters: [],
        objective: 'sharpe',
        maxIterations: 100
      },
      optimizing: false
    }
  },
  methods: {
    addParameter() {
      this.optimizationParams.parameters.push({
        name: '',
        min: 0,
        max: 100,
        step: 1
      })
    },
    removeParameter(index) {
      this.optimizationParams.parameters.splice(index, 1)
    },
    async runOptimization() {
      if (this.optimizationParams.parameters.length === 0) {
        this.$message.warning('请至少添加一个优化参数')
        return
      }

      this.optimizing = true
      try {
        // 触发父组件的优化事件
        this.$emit('optimize', this.optimizationParams)
      } catch (error) {
        this.$message.error('优化失败: ' + error.message)
      } finally {
        this.optimizing = false
      }
    }
  },
  mounted() {
    // 初始化一个默认参数
    this.addParameter()
  }
}
</script>

<style scoped>
.parameter-optimizer {
  padding: 20px;
  background: #f9f9f9;
  border-radius: 4px;
}

.param-item {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}
</style>