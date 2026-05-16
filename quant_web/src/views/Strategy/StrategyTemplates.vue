<template>
  <div class="strategy-templates bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h1>策略模板库</h1>
      <p>预置的策略模板，快速创建交易策略</p>
    </div>

    <n-spin :show="loading">
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <n-grid :x-gap="16" :cols="14" class="filter-row">
          <n-grid-item :span="6">
            <n-input
              v-model:value="searchKeyword"
              placeholder="搜索策略模板..."
              clearable
            >
              <template #prefix
                ><n-icon><Icon icon="mdi:magnify" /></n-icon
              ></template>
            </n-input>
          </n-grid-item>
          <n-grid-item :span="4">
            <n-select
              v-model:value="filterCategory"
              placeholder="策略类别"
              clearable
              :options="categoryOptions"
            />
          </n-grid-item>
          <n-grid-item :span="4">
            <n-select
              v-model:value="filterComplexity"
              placeholder="复杂度"
              clearable
              :options="complexityOptions"
            />
          </n-grid-item>
        </n-grid>

        <n-grid
          :x-gap="16"
          :y-gap="16"
          :cols="4"
          responsive="screen"
          class="templates-grid"
        >
          <n-grid-item v-for="template in filteredTemplates" :key="template.id">
            <n-card class="template-card">
              <template #header>
                <div class="template-header">
                  <span class="template-name">{{ template.name }}</span>
                  <n-tag
                    :type="getComplexityTag(template.complexity) as any"
                    size="small"
                  >
                    {{ template.complexity }}
                  </n-tag>
                </div>
              </template>

              <div class="template-content">
                <p class="template-desc">{{ template.description }}</p>

                <div class="template-meta">
                  <div class="meta-item">
                    <Icon icon="mdi:chart-line" />
                    <span
                      >年化收益: {{ template.performance.annualReturn }}%</span
                    >
                  </div>
                  <div class="meta-item">
                    <Icon icon="mdi:trending-down" />
                    <span
                      >最大回撤: {{ template.performance.maxDrawdown }}%</span
                    >
                  </div>
                  <div class="meta-item">
                    <Icon icon="mdi:shield" />
                    <span
                      >夏普比率: {{ template.performance.sharpeRatio }}</span
                    >
                  </div>
                </div>

                <div class="template-tags">
                  <n-tag
                    v-for="tag in template.tags"
                    :key="tag"
                    size="small"
                    type="info"
                    class="tag-item"
                  >
                    {{ tag }}
                  </n-tag>
                </div>
              </div>

              <template #footer>
                <div class="template-actions">
                  <n-button
                    type="primary"
                    size="small"
                    @click="useTemplate(template)"
                    >使用模板</n-button
                  >
                  <n-button size="small" @click="viewDetails(template)"
                    >查看详情</n-button
                  >
                </div>
              </template>
            </n-card>
          </n-grid-item>
        </n-grid>

        <n-empty
          v-if="filteredTemplates.length === 0"
          description="没有找到匹配的策略模板"
        />

        <n-modal
          v-model:show="detailVisible"
          preset="dialog"
          :title="selectedTemplate?.name"
          positive-text="使用此模板"
          negative-text="取消"
          @positive-click="selectedTemplate && useTemplate(selectedTemplate)"
        >
          <TemplateDetail v-if="selectedTemplate" :template="selectedTemplate" />
        </n-modal>
      </template>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useMessage, NSpin, NResult } from "naive-ui";
import { Icon } from "@iconify/vue";
import TemplateDetail from "@/components/strategy/TemplateDetail.vue";

const message = useMessage();
const router = useRouter();
const loading = ref(false);
const error = ref(false);

interface StrategyTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  complexity: string;
  performance: {
    annualReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
  };
  tags: string[];
}

const searchKeyword = ref("");
const filterCategory = ref("");
const filterComplexity = ref("");
const detailVisible = ref(false);
const selectedTemplate = ref<StrategyTemplate>();

const categoryOptions = [
  { label: "趋势跟踪", value: "trend" },
  { label: "均值回归", value: "mean_reversion" },
  { label: "因子策略", value: "factor" },
  { label: "机器学习", value: "ml" },
];
const complexityOptions = [
  { label: "简单", value: "simple" },
  { label: "中等", value: "medium" },
  { label: "复杂", value: "complex" },
];

const templates = ref<StrategyTemplate[]>([
  {
    id: "1",
    name: "双均线策略",
    description: "基于快速均线和慢速均线的金叉死叉信号进行交易",
    category: "trend",
    complexity: "simple",
    performance: { annualReturn: 15.2, maxDrawdown: -12.5, sharpeRatio: 1.2 },
    tags: ["趋势跟踪", "均线", "技术指标"],
  },
  {
    id: "2",
    name: "布林带突破",
    description: "利用布林带上下轨的突破信号进行趋势交易",
    category: "trend",
    complexity: "simple",
    performance: { annualReturn: 18.7, maxDrawdown: -15.3, sharpeRatio: 1.4 },
    tags: ["突破", "波动率", "技术指标"],
  },
]);

const filteredTemplates = computed(() =>
  templates.value.filter((t) => {
    const m = searchKeyword.value.toLowerCase();
    const matchesSearch =
      !m ||
      t.name.toLowerCase().includes(m) ||
      t.description.toLowerCase().includes(m);
    const matchesCategory =
      !filterCategory.value || t.category === filterCategory.value;
    const matchesComplexity =
      !filterComplexity.value || t.complexity === filterComplexity.value;
    return matchesSearch && matchesCategory && matchesComplexity;
  }),
);

const getComplexityTag = (c: string) =>
  (
    ({ simple: "success", medium: "warning", complex: "error" }) as Record<
      string,
      string
    >
  )[c] || "default";

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 300));
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const useTemplate = (template: StrategyTemplate) => {
  message.success(`正在使用模板: ${template.name}`);
  router.push({ path: "/strategies/create", query: { template: template.id } });
};
const viewDetails = (template: StrategyTemplate) => {
  selectedTemplate.value = template;
  detailVisible.value = true;
};

onMounted(() => loadData());
</script>

<style scoped>
.strategy-templates {
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h1 {
  margin: 0;
  color: var(--n-text-color-1);
}
.page-header p {
  color: var(--n-text-color-3);
  margin-top: 4px;
}
.filter-row {
  margin-bottom: 24px;
}
.templates-grid {
  margin-top: 16px;
}

.template-card {
  margin-bottom: 16px;
  height: 320px;
  display: flex;
  flex-direction: column;
}
.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.template-name {
  font-weight: 600;
  font-size: 16px;
}
.template-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.template-desc {
  color: var(--n-text-color-2);
  font-size: 14px;
  line-height: 1.4;
  margin-bottom: 16px;
  flex: 1;
}
.template-meta {
  margin-bottom: 12px;
}
.meta-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--n-text-color-3);
}
.meta-item :deep(.iconify) {
  margin-right: 4px;
}
.template-tags {
  margin-bottom: 12px;
}
.tag-item {
  margin-right: 4px;
  margin-bottom: 4px;
}
.template-actions {
  display: flex;
  justify-content: space-between;
}
</style>
