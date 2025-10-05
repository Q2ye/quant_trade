<template>
  <div class="parameter-table">
    <h4>最优参数组合</h4>
    <el-table :data="tableData" stripe style="width: 100%">
      <el-table-column prop="parameter" label="参数名" width="150" />
      <el-table-column prop="value" label="最优值" width="120" align="right" />
      <el-table-column prop="performance" label="性能指标" width="120" align="right">
        <template #default="scope">
          {{ scope.row.performance.toFixed(4) }}
        </template>
      </el-table-column>
      <el-table-column prop="range" label="参数范围" width="200">
        <template #default="scope">
          {{ scope.row.range }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
export default {
  name: 'ParameterTable',
  props: {
    data: {
      type: Array,
      default: () => []
    }
  },
  computed: {
    tableData() {
      return this.data.map(item => ({
        parameter: item.name,
        value: item.value,
        performance: item.performance,
        range: `${item.min} - ${item.max}`
      }))
    }
  }
}
</script>

<style scoped>
.parameter-table {
  margin-top: 20px;
}

.parameter-table h4 {
  margin-bottom: 15px;
  color: #333;
}
</style>