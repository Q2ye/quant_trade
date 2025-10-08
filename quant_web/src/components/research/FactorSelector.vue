<!-- components/Research/FactorSelector.vue -->
<!--因子选择器，支持多选和分类显示-->
<template>
  <div class="factor-selector">
    <div class="factor-list">
      <div
        v-for="factor in factors"
        :key="factor.id"
        class="factor-item"
        :class="{ selected: isSelected(factor) }"
        @click="toggleFactor(factor)"
      >
        <div class="factor-checkbox">
          <el-checkbox :model-value="isSelected(factor)" @change="(val) => toggleFactor(factor, val)" />
        </div>
        <div class="factor-info">
          <div class="factor-name">{{ factor.name }}</div>
          <div class="factor-desc">{{ factor.description }}</div>
          <div class="factor-category">
            <el-tag size="small" :type="getCategoryTag(factor.category)">
              {{ getCategoryText(factor.category) }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  factors: {
    type: Array,
    required: true
  },
  modelValue: {
    type: Array,
    default: () => []
  },
  category: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

const selectedFactors = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const isSelected = (factor) => {
  return selectedFactors.value.some(f => f.id === factor.id)
}

const toggleFactor = (factor, checked) => {
  if (checked === undefined) {
    checked = !isSelected(factor)
  }

  if (checked) {
    selectedFactors.value = [...selectedFactors.value, factor]
  } else {
    selectedFactors.value = selectedFactors.value.filter(f => f.id !== factor.id)
  }
}

const getCategoryTag = (category) => {
  const map = {
    value: 'success',
    growth: 'warning',
    quality: 'primary',
    momentum: 'danger',
    technical: 'info'
  }
  return map[category] || 'info'
}

const getCategoryText = (category) => {
  const map = {
    value: '价值',
    growth: '成长',
    quality: '质量',
    momentum: '动量',
    technical: '技术'
  }
  return map[category] || '其他'
}
</script>

<style lang="scss" scoped>
.factor-selector {
  .factor-list {
    max-height: 250px;
    overflow-y: auto;
  }

  .factor-item {
    display: flex;
    align-items: flex-start;
    padding: 8px;
    margin-bottom: 4px;
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background-color: #f5f7fa;
      border-color: #c0c4cc;
    }

    &.selected {
      background-color: #ecf5ff;
      border-color: #409eff;
    }

    .factor-checkbox {
      margin-right: 8px;
      margin-top: 2px;
    }

    .factor-info {
      flex: 1;

      .factor-name {
        font-weight: 500;
        margin-bottom: 2px;
      }

      .factor-desc {
        font-size: 12px;
        color: #909399;
        margin-bottom: 4px;
        line-height: 1.2;
      }

      .factor-category {
        margin-top: 4px;
      }
    }
  }
}
</style>