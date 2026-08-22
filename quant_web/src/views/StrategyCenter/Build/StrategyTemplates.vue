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
          <n-grid :x-gap="16" :cols="1" class="filter-row">
            <n-grid-item>
              <n-input v-model:value="searchKeyword" placeholder="搜索策略模板..." clearable>
                <template #prefix><n-icon><SmartIcon name="Search" /></n-icon></template>
              </n-input>
            </n-grid-item>
          </n-grid>

          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen" class="templates-grid">
            <n-grid-item v-for="tpl in filteredTemplates" :key="tpl.id">
              <n-card class="template-card" @click="useTemplate(tpl)">
                <template #header>
                  <div class="template-header">
                    <span class="template-name">{{ tplDisplayName(tpl) }}</span>
                    <n-tag size="small" type="info">{{ tpl.template_type || '策略' }}</n-tag>
                  </div>
                </template>
                <div class="template-content">
                  <p class="template-desc">{{ tplDescription(tpl) }}</p>
                </div>
                <template #footer>
                  <div class="template-actions">
                    <n-button type="primary" size="small" @click.stop="useTemplate(tpl)">查看详情</n-button>
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
            :title="selectedTemplate ? tplDisplayName(selectedTemplate) : ''"
            positive-text="查看详情"
            negative-text="关闭"
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
import request from "@/utils/request";

const message = useMessage();
const router = useRouter();
type PageState = "loading" | "error" | "empty" | "data";
const pageState = ref<PageState>("loading");

// v3.0: 内置策略中文映射
const BUILTIN_META: Record<string, { name: string; desc: string; params?: Record<string,string> }> = {
  MLStrategy: { name: '机器学习策略', desc: '基于随机森林、XGBoost 等传统 ML 算法的交易策略。' },
  DLStrategy: { name: '深度学习策略', desc: '基于 LSTM、Transformer 等深度学习模型的交易策略。' },
  IndustryRotationStrategy: { name: 'ETF 行业轮动策略', desc: '申万31行业多因子评分（趋势动量+资金量价+估值空间），板块去重，每周轮动 Top5 行业 ETF。' },
};

const extractCN = (tpl: any) => {
  const m = (tpl.code_template || '').match(/class\s+(\w+)\s*[(:]/);
  return m?.[1] || '';
};
const tplDisplayName = (tpl: any) => BUILTIN_META[extractCN(tpl)]?.name || tpl.template_name || tpl.name || '';
const tplDescription = (tpl: any) => BUILTIN_META[extractCN(tpl)]?.desc || tpl.description || '';

const searchKeyword = ref("");
const templates = ref<any[]>([]);
const detailVisible = ref(false);
const selectedTemplate = ref<any>(null);

const filteredTemplates = computed(() =>
  templates.value.filter((t) => {
    const m = searchKeyword.value.toLowerCase();
    return !m || tplDisplayName(t).toLowerCase().includes(m) || tplDescription(t).toLowerCase().includes(m);
  }),
);

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/strategies");
};

const loadData = async () => {
  pageState.value = "loading";
  try {
    const res = await request.get('/quantTrade/strategy/templates', { params: { is_builtin: true, page_size: 50 } });
    templates.value = res?.data || [];
    pageState.value = templates.value.length > 0 ? "data" : "empty";
  } catch {
    pageState.value = "error";
  }
};

const useTemplate = (tpl: any) => router.push('/strategies/template/' + tpl.id);
const viewDetails = (tpl: any) => {
  selectedTemplate.value = tpl;
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
