<!--参数滑块组件-->
<script>
export default {
  name: "ParamSlider",
  props: {
    paramName: {
      type: String,
      required: true
    },
    config: {
      type: Object,
      required: true
    },
    value: {
      type: Number,
      required: true
    }
  },
  methods: {
    handleChange(value) {
      this.$emit('change', this.paramName, value)
    },

    formatLabel(value) {
      return value % 1 === 0 ? value : value.toFixed(2)
    }
  }
}
</script>

<template>
  <div class="param-slider">
    <div class="param-header">
      <span class="param-name">{{ paramName }}</span>
      <span class="param-value">{{ value.toFixed(2) }}</span>
    </div>

    <div class="slider-container">
      <span class="min-value">{{ formatLabel(config.min) }}</span>

      <el-slider
        v-model="value"
        :min="config.min"
        :max="config.max"
        :step="config.step"
        :format-tooltip="val => val.toFixed(2)"
        @change="handleChange" />

      <span class="max-value">{{ formatLabel(config.max) }}</span>
    </div>

    <div class="param-description">
      <span>默认值: {{ config.default.toFixed(2) }}</span>
    </div>
  </div>
</template>

<style scoped>
.param-slider {
  padding: 10px 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background-color: #fff;
}

.param-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.param-name {
  font-weight: 500;
  color: #303133;
  text-transform: capitalize;
}

.param-value {
  font-weight: bold;
  color: #409eff;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider-container .el-slider {
  flex: 1;
}

.min-value, .max-value {
  font-size: 12px;
  color: #909399;
  min-width: 40px;
  text-align: center;
}

.param-description {
  margin-top: 5px;
  font-size: 12px;
  color: #909399;
}
</style>