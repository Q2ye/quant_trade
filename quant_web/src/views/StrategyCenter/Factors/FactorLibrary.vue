<template>
  <div class="factor-library bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">因子库管理</h1>
          <p class="page-description">管理量化因子库，支持新建、导入导出和编辑</p>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="handleCreateFactor">
            <template #icon><SmartIcon name="Plus" /></template>
            新建因子
          </n-button>
          <n-button @click="importFactors">
            <template #icon><SmartIcon name="Upload" /></template>
            批量导入
          </n-button>
          <n-button @click="exportFactors">
            <template #icon><SmartIcon name="Download" /></template>
            导出配置
          </n-button>
          <n-button class="action-btn" @click="refreshPage" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
          <n-button class="action-btn" @click="handleBack" quaternary>
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Loading -->
      <template v-if="pageState === 'loading'">
        <n-card class="library-management">
          <template #header><n-skeleton :text="true" width="40%" /></template>
          <n-skeleton :text="true" :repeat="10" />
        </n-card>
      </template>

      <!-- Error -->
      <n-result
        v-else-if="pageState === 'error'"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadFactors">重试</n-button>
        </template>
      </n-result>

      <!-- Empty -->
      <n-card v-else-if="pageState === 'empty'" class="library-management">
        <n-empty description="暂无因子数据">
          <template #extra>
            <n-button type="primary" @click="handleCreateFactor">
              <template #icon><SmartIcon name="Plus" /></template>
              新建因子
            </n-button>
          </template>
        </n-empty>
      </n-card>

      <!-- Data -->
      <template v-else>
        <div class="section-block">
          <n-card class="library-management">
            <template #header>
              <div class="card-header">
                <span>因子库管理</span>
                <n-space :size="8" :wrap="false">
                  <n-input
                    v-model:value="searchKeyword"
                    placeholder="搜索因子名称、代码或描述"
                    style="width: 200px"
                    clearable
                  >
                    <template #prefix>
                      <n-icon><SmartIcon name="Search" /></n-icon>
                    </template>
                  </n-input>
                  <n-select
                    v-model:value="filterCategory"
                    placeholder="因子类别"
                    style="width: 120px"
                    clearable
                    :options="categoryOptions"
                  />
                  <n-select
                    v-model:value="filterStatus"
                    placeholder="状态"
                    style="width: 100px"
                    clearable
                    :options="factorStatusOptions"
                  />
                </n-space>
              </div>
            </template>

            <n-data-table
              :columns="factorColumns"
              :data="pagedFactors"
              :bordered="false"
              size="small"
              :row-key="(row: any) => row.id"
            />

            <div class="pagination-container">
              <n-pagination
                v-model:page="pagination.currentPage"
                v-model:page-size="pagination.pageSize"
                :item-count="pagination.total"
              />
            </div>
          </n-card>
        </div>

        <div class="section-block">
          <n-card class="analysis-tools">
            <template #header><span>专业分析工具</span></template>

            <n-grid :x-gap="20" :cols="3">
              <n-grid-item>
                <n-card class="tool-card" @click="openFactorCorrelation">
                  <div class="tool-content">
                    <SmartIcon name="ChartScatter" :size="24" class="tool-icon blue" />
                    <div class="tool-info">
                      <div class="tool-title">因子相关性分析</div>
                      <div class="tool-desc">分析因子间的相关性矩阵</div>
                    </div>
                  </div>
                </n-card>
              </n-grid-item>
              <n-grid-item>
                <n-card class="tool-card" @click="openStabilityAnalysis">
                  <div class="tool-content">
                    <SmartIcon name="ChartLine" :size="24" class="tool-icon green" />
                    <div class="tool-info">
                      <div class="tool-title">因子稳定性分析</div>
                      <div class="tool-desc">检验因子表现的稳定性</div>
                    </div>
                  </div>
                </n-card>
              </n-grid-item>
              <n-grid-item>
                <n-card class="tool-card" @click="openCombinationAnalysis">
                  <div class="tool-content">
                    <SmartIcon name="ChartBar" :size="24" class="tool-icon orange" />
                    <div class="tool-info">
                      <div class="tool-title">因子组合优化</div>
                      <div class="tool-desc">寻找最优因子组合权重</div>
                    </div>
                  </div>
                </n-card>
              </n-grid-item>
            </n-grid>
          </n-card>
        </div>
      </template>
    </div>

    <FactorEditDialog
      v-model="factorDialogVisible"
      :factor="editingFactor"
      :mode="editMode"
      @save="handleSaveFactor"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import { useMessage, useDialog, NTag, NButton, NSwitch } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import PerformanceBadge from "@/components/strategy/PerformanceBadge.vue";
import FactorEditDialog from "@/components/strategy/FactorEditDialog.vue";

const message = useMessage();
const router = useRouter();
const dialog = useDialog();

type PageState = "loading" | "error" | "empty" | "data";

const pageState = ref<PageState>("loading");
const searchKeyword = ref("");
const filterCategory = ref("");
const filterStatus = ref("");
const factorDialogVisible = ref(false);
const editingFactor = ref<any>(null);
const editMode = ref("create");

const pagination = reactive({ currentPage: 1, pageSize: 10, total: 0 });

const categoryOptions = [
  { label: "全部", value: "" },
  { label: "价值因子", value: "value" },
  { label: "成长因子", value: "growth" },
  { label: "质量因子", value: "quality" },
  { label: "动量因子", value: "momentum" },
];
const factorStatusOptions = [
  { label: "全部", value: "" },
  { label: "启用", value: "active" },
  { label: "停用", value: "inactive" },
];

const categoryMap: Record<string, { tag: string; text: string }> = {
  value: { tag: "success", text: "价值因子" },
  growth: { tag: "warning", text: "成长因子" },
  quality: { tag: "info", text: "质量因子" },
  momentum: { tag: "error", text: "动量因子" },
  technical: { tag: "default", text: "技术因子" },
};

const factorColumns = [
  {
    title: "序号", key: "index", width: 60,
    render: (_: any, __: number) => __ + 1 + (pagination.currentPage - 1) * pagination.pageSize,
  },
  { title: "因子名称", key: "name", width: 150 },
  { title: "因子代码", key: "code", width: 120 },
  {
    title: "类别", key: "category", width: 100,
    render: (row: any) =>
      h(NTag, {
        type: (categoryMap[row.category]?.tag || "info") as any,
        size: "small",
      }, { default: () => categoryMap[row.category]?.text || "其他" }),
  },
  {
    title: "因子描述", key: "description", minWidth: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: "数据字段", key: "dataFields", width: 120,
    render: (row: any) => `${row.dataFields.length}个字段`,
  },
  {
    title: "近期表现", key: "performance", width: 100,
    render: (row: any) => h(PerformanceBadge, { performance: row.performance }),
  },
  {
    title: "状态", key: "status", width: 80,
    render: (row: any) =>
      h(NSwitch, {
        value: row.status === "active",
        onUpdateValue: (v: boolean) => {
          row.status = v ? "active" : "inactive";
          handleStatusChange(row);
        },
      }),
  },
  {
    title: "最后更新", key: "lastUpdate", width: 120,
    render: (row: any) => formatDate(row.lastUpdate),
  },
  {
    title: "操作", key: "op", width: 240,
    render: (row: any) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(NButton, { size: "small", onClick: () => handleEditFactor(row) }, { default: () => "编辑" }),
        h(NButton, { size: "small", onClick: () => handleTestFactor(row) }, { default: () => "测试" }),
        h(NButton, { size: "small", type: "error", onClick: () => handleDeleteFactor(row) }, { default: () => "删除" }),
      ]),
  },
];

interface Factor {
  id: string;
  name: string;
  code: string;
  category: string;
  description: string;
  dataFields: string[];
  formula: string;
  performance: { score: number; trend: string };
  status: string;
  lastUpdate: Date;
}

const factors = ref<Factor[]>([
  {
    id: "1", name: "市盈率因子", code: "PE", category: "value",
    description: "基于市盈率的估值因子，低市盈率表示价值被低估",
    dataFields: ["pe"], formula: "1 / pe if pe > 0 else 0",
    performance: { score: 85, trend: "up" }, status: "active", lastUpdate: new Date("2024-01-15"),
  },
  {
    id: "2", name: "动量因子", code: "MOMENTUM_1M", category: "momentum",
    description: "一个月动量因子，计算过去一个月的收益率",
    dataFields: ["close"], formula: "close / close.shift(20) - 1",
    performance: { score: 72, trend: "stable" }, status: "active", lastUpdate: new Date("2024-01-15"),
  },
  {
    id: "3", name: "波动率因子", code: "VOLATILITY_20D", category: "technical",
    description: "20日历史波动率因子",
    dataFields: ["close"], formula: "close.pct_change().rolling(20).std()",
    performance: { score: 68, trend: "down" }, status: "inactive", lastUpdate: new Date("2024-01-14"),
  },
]);

const filteredFactors = computed(() => {
  let result = factors.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (f) => f.name.toLowerCase().includes(kw) || f.description.toLowerCase().includes(kw) || f.code.toLowerCase().includes(kw),
    );
  }
  if (filterCategory.value) result = result.filter((f) => f.category === filterCategory.value);
  if (filterStatus.value) result = result.filter((f) => f.status === filterStatus.value);
  return result;
});

const pagedFactors = computed(() =>
  filteredFactors.value.slice(
    (pagination.currentPage - 1) * pagination.pageSize,
    pagination.currentPage * pagination.pageSize,
  ),
);

// 筛选变更→复位分页+同步总数
watch([searchKeyword, filterCategory, filterStatus], () => {
  pagination.currentPage = 1;
  pagination.total = filteredFactors.value.length;
});

watch(filteredFactors, (list) => {
  pagination.total = list.length;
  if (pagination.currentPage > 1 && pagedFactors.value.length === 0) {
    pagination.currentPage = Math.max(1, Math.ceil(list.length / pagination.pageSize));
  }
});

const formatDate = (d: any) => (d ? new Date(d).toLocaleDateString("zh-CN") : "-");

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push("/strategy/factors");
};

const refreshPage = async () => {
  await loadFactors();
  message.success("数据已刷新");
};

const handleCreateFactor = () => {
  editMode.value = "create";
  editingFactor.value = null;
  factorDialogVisible.value = true;
};

const handleEditFactor = (factor: Factor) => {
  editMode.value = "edit";
  editingFactor.value = { ...factor };
  factorDialogVisible.value = true;
};

const handleTestFactor = (factor: Factor) => message.info(`开始测试因子: ${factor.name}`);

const handleDeleteFactor = (factor: Factor) => {
  dialog.warning({
    title: "删除确认",
    content: `确定要删除因子 "${factor.name}" 吗？`,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: () => {
      const idx = factors.value.findIndex((f) => f.id === factor.id);
      if (idx > -1) {
        factors.value.splice(idx, 1);
        message.success("因子删除成功");
      }
    },
  });
};

const handleStatusChange = (factor: Factor) =>
  message.success(`因子 ${factor.name} 已${factor.status === "active" ? "启用" : "停用"}`);

const handleSaveFactor = (factorData: any) => {
  if (editMode.value === "create") {
    factors.value.push({
      ...factorData,
      id: Date.now().toString(),
      lastUpdate: new Date(),
      performance: { score: 0, trend: "stable" },
    });
    message.success("因子创建成功");
  } else {
    const idx = factors.value.findIndex((f) => f.id === editingFactor.value.id);
    if (idx > -1) {
      factors.value[idx] = { ...factorData, lastUpdate: new Date() };
      message.success("因子更新成功");
    }
  }
  factorDialogVisible.value = false;
};

const importFactors = () => message.info("导入功能开发中");
const exportFactors = () => message.info("导出功能开发中");
const openFactorCorrelation = () => message.info("打开因子相关性分析工具");
const openStabilityAnalysis = () => message.info("打开因子稳定性分析工具");
const openCombinationAnalysis = () => message.info("打开因子组合优化工具");

const loadFactors = async () => {
  pageState.value = "loading";
  try {
    await new Promise((r) => setTimeout(r, 300));
    pagination.total = factors.value.length;
    pageState.value = factors.value.length === 0 ? "empty" : "data";
  } catch {
    pageState.value = "error";
  }
};

onMounted(() => loadFactors());
</script>

<style lang="scss" scoped>
.factor-library {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
}

.section-block {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
  overflow: hidden;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.tool-card {
  cursor: pointer;
  transition: all 0.3s;
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  }
  .tool-content {
    display: flex;
    align-items: center;
    gap: 12px;
    .tool-icon {
      flex-shrink: 0;
      &.blue   { color: var(--color-primary, #448AFF); }
      &.green  { color: var(--color-stock-up, #FF5252); }
      &.orange { color: var(--n-warning-color); }
    }
    .tool-info {
      .tool-title { font-weight: 500; margin-bottom: 4px; }
      .tool-desc { font-size: 12px; color: var(--n-text-color-3); }
    }
  }
}

// 响应式
@media (max-width: 768px) {
  .section-block {
    margin-bottom: 16px;
  }
}
</style>
