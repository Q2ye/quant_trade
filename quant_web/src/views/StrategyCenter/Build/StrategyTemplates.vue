<template>
  <div class="strategy-templates bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略模板库</h1>
          <p class="page-description">预置的策略模板，快速创建交易策略</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result
        v-if="pageState === 'error'"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-if="pageState === 'loading'">
        <div class="section-block">
          <n-grid
            :x-gap="16"
            :y-gap="16"
            :cols="4"
            responsive="screen"
            class="templates-grid"
          >
            <n-grid-item v-for="i in 4" :key="i">
              <n-card class="template-card">
                <n-skeleton :text="true" :repeat="6" />
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>
      </template>

      <template v-else-if="pageState === 'data'">
        <div class="section-block">
          <n-grid :x-gap="16" :cols="3" class="filter-row">
            <n-grid-item>
              <n-input
                v-model:value="searchKeyword"
                placeholder="搜索策略模板..."
                clearable
              >
                <template #prefix
                  ><n-icon><SmartIcon name="Search" /></n-icon
                ></template>
              </n-input>
            </n-grid-item>
            <n-grid-item>
              <n-select
                v-model:value="filterCategory"
                placeholder="策略类别"
                clearable
                :options="categoryOptions"
              />
            </n-grid-item>
            <n-grid-item>
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
            <n-grid-item
              v-for="template in filteredTemplates"
              :key="template.id"
            >
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
                      <SmartIcon name="ChartLine" />
                      <span
                        :class="
                          template.performance.annualReturn >= 0
                            ? 'text-up'
                            : 'text-down'
                        "
                        >年化收益:
                        {{ template.performance.annualReturn }}%</span
                      >
                    </div>
                    <div class="meta-item">
                      <SmartIcon name="ChartTrending" />
                      <span class="text-down"
                        >最大回撤: {{ template.performance.maxDrawdown }}%</span
                      >
                    </div>
                    <div class="meta-item">
                      <SmartIcon name="ShieldCheckmark" />
                      <span
                        :class="
                          template.performance.sharpeRatio >= 1
                            ? 'text-up'
                            : 'text-down'
                        "
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
            style="width: 640px"
            @positive-click="selectedTemplate && useTemplate(selectedTemplate)"
          >
            <div class="dialog-body-scroll">
              <TemplateDetail
                v-if="selectedTemplate"
                :template="selectedTemplate"
              />
            </div>
          </n-modal>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useMessage } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import TemplateDetail from "@/components/strategy/TemplateDetail.vue";

const message = useMessage();
const router = useRouter();
type PageState = "loading" | "error" | "empty" | "data";
const pageState = ref<PageState>("loading");

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

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/strategy/build");
};

const loadData = async () => {
  pageState.value = "loading";
  try {
    await new Promise((r) => setTimeout(r, 300));
    pageState.value = "data";
  } catch {
    pageState.value = "error";
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
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.section-block {
  margin-bottom: 24px;
}
/* .page-header 已迁移至全局样式（global.scss） */
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

.dialog-body-scroll {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}
</style>
