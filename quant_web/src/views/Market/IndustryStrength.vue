<template>
  <div class="industry-strength">
    <el-table :data="industries" height="250">
      <el-table-column prop="name" label="板块" width="100"></el-table-column>
      <el-table-column label="涨跌幅">
        <template #default="{ row }">
          <span :class="row.change >= 0 ? 'up' : 'down'">
            {{ row.change >= 0 ? '+' : '' }}{{ row.change }}%
          </span>
        </template>
      </el-table-column>
      <el-table-column label="强度指数">
        <template #default="{ row }">
          <el-progress
            :percentage="row.strength"
            :color="getStrengthColor(row.strength)"
            :show-text="false"></el-progress>
          <div class="strength-value">
            <span>{{ row.strength }}</span>
            <span class="strength-label">{{ getStrengthLabel(row.strength) }}</span>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script>
import { defineComponent } from 'vue';

export default defineComponent({
  name: "IndustryStrength",
  props: {
    industries: Array
  },
  setup() {
    const getStrengthColor = (strength) => {
      if (strength > 85) return '#f56c6c';
      if (strength > 70) return '#e6a23c';
      if (strength > 50) return '#5cb87a';
      return '#909399';
    };

    const getStrengthLabel = (strength) => {
      if (strength > 85) return '过热';
      if (strength > 70) return '强势';
      if (strength > 50) return '正常';
      return '弱势';
    };

    return {
      getStrengthColor,
      getStrengthLabel
    };
  }
});
</script>

<style scoped>
.industry-strength {
  height: 100%;
}

.up {
  color: #f56c6c;
  font-weight: bold;
}

.down {
  color: #5cb87a;
  font-weight: bold;
}

.strength-value {
  display: flex;
  justify-content: space-between;
  margin-top: 5px;
  font-size: 12px;
}

.strength-label {
  color: #606266;
}
</style>