<!--因子选择器-->
<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { NInput, NSelect, NButton, NTag } from "naive-ui";

interface Factor {
  id: string;
  name: string;
  category: string;
}

const props = withDefaults(
  defineProps<{
    factors?: Factor[];
    selected?: string[];
  }>(),
  {
    factors: () => [
      { id: "pe", name: "市盈率(PE)", category: "估值" },
      { id: "pb", name: "市净率(PB)", category: "估值" },
      { id: "roe", name: "净资产收益率(ROE)", category: "盈利能力" },
      { id: "rev_growth", name: "营收增长率", category: "成长能力" },
      { id: "debt_ratio", name: "资产负债率", category: "偿债能力" },
      { id: "beta", name: "贝塔系数", category: "风险指标" },
      { id: "rsi", name: "相对强弱指数(RSI)", category: "技术指标" },
      { id: "macd", name: "MACD指标", category: "技术指标" },
    ],
    selected: () => [],
  },
);

const emit = defineEmits<{
  "update:selected": [value: string[]];
  change: [value: string[]];
}>();

const localSelected = ref<string[]>([...props.selected]);
const searchText = ref("");
const categoryFilter = ref("all");

const categories = [
  "all",
  "估值",
  "盈利能力",
  "成长能力",
  "偿债能力",
  "风险指标",
  "技术指标",
];
const categoryOptions = categories.map((c) => ({
  label: c === "all" ? "全部分类" : c,
  value: c,
}));

watch(
  () => props.selected,
  (newVal) => {
    localSelected.value = [...newVal];
  },
);

const filteredFactors = computed(() => {
  return props.factors.filter((factor) => {
    const matchesSearch = factor.name
      .toLowerCase()
      .includes(searchText.value.toLowerCase());
    const matchesCategory =
      categoryFilter.value === "all" ||
      factor.category === categoryFilter.value;
    return matchesSearch && matchesCategory;
  });
});

const groupedFactors = computed(() => {
  const groups: Record<string, Factor[]> = {};
  filteredFactors.value.forEach((factor) => {
    if (!groups[factor.category]) {
      groups[factor.category] = [];
    }
    groups[factor.category].push(factor);
  });
  return groups;
});

const emitChange = () => {
  const copy = [...localSelected.value];
  emit("update:selected", copy);
  emit("change", copy);
};

const toggleFactor = (factorId: string) => {
  const index = localSelected.value.indexOf(factorId);
  if (index === -1) {
    localSelected.value.push(factorId);
  } else {
    localSelected.value.splice(index, 1);
  }
  emitChange();
};

const clearSelection = () => {
  localSelected.value = [];
  emitChange();
};
</script>

<template>
  <div class="factor-selector">
    <div class="filter-bar">
      <NInput
        v-model:value="searchText"
        placeholder="搜索因子..."
        size="small"
        clearable
      />

      <NSelect
        v-model:value="categoryFilter"
        :options="categoryOptions"
        size="small"
        class="category-select"
      />

      <NButton size="small" text @click="clearSelection"> 清空已选 </NButton>
    </div>

    <div v-if="localSelected.length > 0" class="selected-factors">
      <div class="selected-title">已选因子 ({{ localSelected.length }})</div>
      <div class="selected-list">
        <NTag
          v-for="id in localSelected"
          :key="id"
          closable
          size="small"
          @close="toggleFactor(id)"
        >
          {{ factors.find((f) => f.id === id)?.name }}
        </NTag>
      </div>
    </div>

    <div class="factor-groups">
      <div
        v-for="(group, category) in groupedFactors"
        :key="category"
        class="factor-group"
      >
        <div class="group-title">{{ category }}</div>
        <div class="group-items">
          <div
            v-for="factor in group"
            :key="factor.id"
            class="factor-item"
            :class="{ selected: localSelected.includes(factor.id) }"
            @click="toggleFactor(factor.id)"
          >
            <div class="factor-name">{{ factor.name }}</div>
            <div class="factor-id">{{ factor.id }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.factor-selector {
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  padding: 10px;
  background-color: var(--n-color);
}

.filter-bar {
  display: flex;
  margin-bottom: 15px;
  gap: 10px;
}

.category-select {
  width: 120px;
}

.selected-factors {
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--n-border-color);
}

.selected-title {
  font-size: 13px;
  color: var(--n-text-color-3);
  margin-bottom: 8px;
}

.selected-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.factor-groups {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 5px;
}

.factor-group {
  margin-bottom: 20px;
}

.group-title {
  font-weight: bold;
  color: var(--n-text-color-2);
  padding: 5px 0;
  border-bottom: 1px dashed var(--n-border-color);
  margin-bottom: 10px;
}

.group-items {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.factor-item {
  padding: 10px;
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  background-color: var(--n-color-embedded);
}

.factor-item:hover {
  border-color: var(--n-color-target);
  background-color: var(--n-color-target-1);
}

.factor-item.selected {
  border-color: var(--n-color-target);
  background-color: var(--n-color-target-2);
}

.factor-name {
  font-size: 13px;
  margin-bottom: 3px;
  color: var(--n-text-color-1);
}

.factor-id {
  font-size: 12px;
  color: var(--n-text-color-3);
  font-family: monospace;
}
</style>
