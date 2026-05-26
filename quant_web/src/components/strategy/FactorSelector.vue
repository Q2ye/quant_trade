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
        <div class="factor-checkbox" @click.stop>
          <NCheckbox
            :checked="isSelected(factor)"
            @update:checked="(val: boolean) => toggleFactor(factor, val)"
          />
        </div>
        <div class="factor-info">
          <div class="factor-name">{{ factor.name }}</div>
          <div class="factor-desc">{{ factor.description }}</div>
          <div class="factor-category">
            <NTag size="small" :type="getCategoryTag(factor.category)">
              {{ getCategoryText(factor.category) }}
            </NTag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { NCheckbox, NTag } from "naive-ui";

interface Factor {
  id: string;
  name: string;
  description: string;
  category: string;
}

const props = defineProps<{
  factors: Factor[];
  modelValue: Factor[];
  category?: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: Factor[]];
}>();

const selectedFactors = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const isSelected = (factor: Factor) => {
  return selectedFactors.value.some((f: Factor) => f.id === factor.id);
};

const toggleFactor = (factor: Factor, checked?: boolean) => {
  if (checked === undefined) {
    checked = !isSelected(factor);
  }

  if (checked) {
    selectedFactors.value = [...selectedFactors.value, factor];
  } else {
    selectedFactors.value = selectedFactors.value.filter(
      (f: Factor) => f.id !== factor.id,
    );
  }
};

const getCategoryTag = (category: string) => {
  const map: Record<string, "success" | "warning" | "info" | "error"> = {
    value: "success",
    growth: "warning",
    quality: "info",
    momentum: "error",
    technical: "info",
  };
  return map[category] || "default";
};

const getCategoryText = (category: string) => {
  const map: Record<string, string> = {
    value: "价值",
    growth: "成长",
    quality: "质量",
    momentum: "动量",
    technical: "技术",
  };
  return map[category] || "其他";
};
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
    border: 1px solid var(--n-border-color);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background-color: var(--n-color-embedded);
      border-color: var(--n-border-color-hover);
    }

    &.selected {
      background-color: var(--n-color-target-1);
      border-color: var(--n-color-target);
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
        color: var(--n-text-color-1);
      }

      .factor-desc {
        font-size: 12px;
        color: var(--n-text-color-3);
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
