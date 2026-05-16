<template>
  <div class="factor-library bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h1 class="page-title">
        <Icon icon="mdi:database-cog" />
        因子库管理
      </h1>
      <n-space :size="8">
        <n-button type="primary" @click="handleCreateFactor">
          <template #icon><Icon icon="mdi:plus" /></template>
          新建因子
        </n-button>
        <n-button @click="importFactors">
          <template #icon><Icon icon="mdi:upload" /></template>
          批量导入
        </n-button>
        <n-button @click="exportFactors">
          <template #icon><Icon icon="mdi:download" /></template>
          导出配置
        </n-button>
        <n-button
          @click="runBatchTest"
          :disabled="selectedFactors.length === 0"
        >
          <template #icon><Icon icon="mdi:play-circle" /></template>
          批量测试
        </n-button>
      </n-space>
    </div>

    <n-card class="library-management">
      <template #header>
        <div class="card-header">
          <span>因子库管理</span>
          <n-space :size="8">
            <n-input
              v-model:value="searchKeyword"
              placeholder="搜索因子名称、代码或描述"
              style="width: 200px"
              clearable
            >
              <template #prefix
                ><n-icon><Icon icon="mdi:magnify" /></n-icon
              ></template>
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

      <div v-if="selectedFactors.length > 0" class="batch-actions">
        <span class="selected-text"
          >已选择 {{ selectedFactors.length }} 个因子</span
        >
        <n-button size="small" @click="batchEnable">批量启用</n-button>
        <n-button size="small" @click="batchDisable">批量停用</n-button>
        <n-button size="small" type="error" @click="batchDelete"
          >批量删除</n-button
        >
      </div>

      <n-result
        v-if="error"
        status="500"
        title="操作失败"
        description="批量测试失败，请稍后重试"
      >
        <template #footer
          ><n-button @click="runBatchTest">重试</n-button></template
        >
      </n-result>

      <n-spin v-else :show="loading">
        <n-empty
          v-if="filteredFactors.length === 0"
          description="暂无因子数据"
        />
        <template v-else>
          <n-data-table
            :columns="factorColumns"
            :data="filteredFactors"
            :bordered="false"
            size="small"
            :row-key="(row: any) => row.id"
            @update:checked-row-keys="handleCheck"
          />
          <div class="pagination-container">
            <n-pagination
              v-model:page="pagination.currentPage"
              v-model:page-size="pagination.pageSize"
              :item-count="pagination.total"
            />
          </div>
        </template>
      </n-spin>
    </n-card>

    <n-card v-if="batchTestResults" class="batch-test-results">
      <template #header>
        <span>批量测试结果</span>
        <n-button text @click="exportBatchResults">导出报告</n-button>
      </template>

      <n-data-table
        :columns="batchTestColumns"
        :data="batchTestResults"
        :bordered="false"
        size="small"
      />
    </n-card>

    <n-card class="analysis-tools">
      <template #header><span>专业分析工具</span></template>

      <n-grid :x-gap="20" :cols="3">
        <n-grid-item>
          <n-card class="tool-card" @click="openFactorCorrelation">
            <div class="tool-content">
              <Icon icon="mdi:chart-scatter-plot" width="24" color="#409EFF" />
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
              <Icon icon="mdi:chart-timeline" width="24" color="#67C23A" />
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
              <Icon icon="mdi:chart-bell-curve" width="24" color="#E6A23C" />
              <div class="tool-info">
                <div class="tool-title">因子组合优化</div>
                <div class="tool-desc">寻找最优因子组合权重</div>
              </div>
            </div>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-card>

    <FactorEditDialog
      v-model="factorDialogVisible"
      :factor="editingFactor"
      :mode="editMode"
      @save="handleSaveFactor"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from "vue";
import {
  useMessage,
  useDialog,
  NTag,
  NButton,
  NSwitch,
  NResult,
} from "naive-ui";
import { Icon } from "@iconify/vue";
import PerformanceBadge from "@/components/research/PerformanceBadge.vue";
import FactorEditDialog from "@/components/research/FactorEditDialog.vue";

const message = useMessage();
const dialog = useDialog();

const loading = ref(false);
const error = ref(false);
const searchKeyword = ref("");
const filterCategory = ref("");
const filterStatus = ref("");
const selectedFactors = ref<any[]>([]);
const factorDialogVisible = ref(false);
const editingFactor = ref<any>(null);
const editMode = ref("create");
const batchTestResults = ref<any>(null);

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
  { type: "selection" as const },
  {
    title: "序号",
    key: "index",
    width: 60,
    render: (_: any, __: number) =>
      __ + 1 + (pagination.currentPage - 1) * pagination.pageSize,
  },
  { title: "因子名称", key: "name", width: 150 },
  { title: "因子代码", key: "code", width: 120 },
  {
    title: "类别",
    key: "category",
    width: 100,
    render: (row: any) =>
      h(
        NTag,
        { type: (categoryMap[row.category]?.tag || "info") as "default" | "primary" | "success" | "info" | "warning" | "error", size: "small" },
        { default: () => categoryMap[row.category]?.text || "其他" },
      ),
  },
  {
    title: "因子描述",
    key: "description",
    minWidth: 200,
    ellipsis: { tooltip: true },
  },
  {
    title: "数据字段",
    key: "dataFields",
    width: 120,
    render: (row: any) => `${row.dataFields.length}个字段`,
  },
  {
    title: "近期表现",
    key: "performance",
    width: 100,
    render: (row: any) => h(PerformanceBadge, { performance: row.performance }),
  },
  {
    title: "状态",
    key: "status",
    width: 80,
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
    title: "最后更新",
    key: "lastUpdate",
    width: 120,
    render: (row: any) => formatDate(row.lastUpdate),
  },
  {
    title: "操作",
    key: "op",
    width: 240,
    render: (row: any) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "small", onClick: () => handleEditFactor(row) },
          { default: () => "编辑" },
        ),
        h(
          NButton,
          { size: "small", onClick: () => handleTestFactor(row) },
          { default: () => "测试" },
        ),
        h(
          NButton,
          {
            size: "small",
            type: "error",
            onClick: () => handleDeleteFactor(row),
          },
          { default: () => "删除" },
        ),
      ]),
  },
];

const batchTestColumns = [
  { title: "因子名称", key: "factorName" },
  {
    title: "年化收益",
    key: "annualReturn",
    width: 100,
    render: (row: any) =>
      h(
        "span",
        { class: row.annualReturn >= 0 ? "positive" : "negative" },
        formatPercent(row.annualReturn),
      ),
  },
  {
    title: "夏普比率",
    key: "sharpeRatio",
    width: 100,
    render: (row: any) => row.sharpeRatio.toFixed(2),
  },
  {
    title: "最大回撤",
    key: "maxDrawdown",
    width: 100,
    render: (row: any) =>
      h("span", { class: "negative" }, formatPercent(row.maxDrawdown)),
  },
  {
    title: "胜率",
    key: "winRate",
    width: 80,
    render: (row: any) => formatPercent(row.winRate),
  },
  {
    title: "IC均值",
    key: "icMean",
    width: 80,
    render: (row: any) => row.icMean.toFixed(3),
  },
  {
    title: "操作",
    key: "op",
    width: 120,
    render: (row: any) =>
      h(
        NButton,
        { size: "small", onClick: () => viewFactorDetail(row) },
        { default: () => "详情" },
      ),
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
    id: "1",
    name: "市盈率因子",
    code: "PE",
    category: "value",
    description: "基于市盈率的估值因子，低市盈率表示价值被低估",
    dataFields: ["pe"],
    formula: "1 / pe if pe > 0 else 0",
    performance: { score: 85, trend: "up" },
    status: "active",
    lastUpdate: new Date("2024-01-15"),
  },
  {
    id: "2",
    name: "动量因子",
    code: "MOMENTUM_1M",
    category: "momentum",
    description: "一个月动量因子，计算过去一个月的收益率",
    dataFields: ["close"],
    formula: "close / close.shift(20) - 1",
    performance: { score: 72, trend: "stable" },
    status: "active",
    lastUpdate: new Date("2024-01-15"),
  },
  {
    id: "3",
    name: "波动率因子",
    code: "VOLATILITY_20D",
    category: "technical",
    description: "20日历史波动率因子",
    dataFields: ["close"],
    formula: "close.pct_change().rolling(20).std()",
    performance: { score: 68, trend: "down" },
    status: "inactive",
    lastUpdate: new Date("2024-01-14"),
  },
]);

const filteredFactors = computed(() => {
  let result = factors.value;
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase();
    result = result.filter(
      (f) =>
        f.name.toLowerCase().includes(kw) ||
        f.description.toLowerCase().includes(kw) ||
        f.code.toLowerCase().includes(kw),
    );
  }
  if (filterCategory.value)
    result = result.filter((f) => f.category === filterCategory.value);
  if (filterStatus.value)
    result = result.filter((f) => f.status === filterStatus.value);
  pagination.total = result.length;
  return result.slice(
    (pagination.currentPage - 1) * pagination.pageSize,
    pagination.currentPage * pagination.pageSize,
  );
});

const formatDate = (d: any) =>
  d ? new Date(d).toLocaleDateString("zh-CN") : "-";
const formatPercent = (v: number) => `${(v * 100).toFixed(2)}%`;

const handleCheck = (keys: string[]) =>
  (selectedFactors.value = factors.value.filter((f) => keys.includes(f.id)));

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
const handleTestFactor = (factor: Factor) =>
  message.info(`开始测试因子: ${factor.name}`);

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
  message.success(
    `因子 ${factor.name} 已${factor.status === "active" ? "启用" : "停用"}`,
  );

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

const batchEnable = () => {
  selectedFactors.value.forEach((f) => (f.status = "active"));
  message.success(`已启用 ${selectedFactors.value.length} 个因子`);
  selectedFactors.value = [];
};
const batchDisable = () => {
  selectedFactors.value.forEach((f) => (f.status = "inactive"));
  message.success(`已停用 ${selectedFactors.value.length} 个因子`);
  selectedFactors.value = [];
};

const batchDelete = () => {
  dialog.warning({
    title: "批量删除确认",
    content: `确定要删除选中的 ${selectedFactors.value.length} 个因子吗？`,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: () => {
      const idsToDelete = new Set(selectedFactors.value.map((f) => f.id));
      factors.value = factors.value.filter((f) => !idsToDelete.has(f.id));
      message.success(`已删除 ${selectedFactors.value.length} 个因子`);
      selectedFactors.value = [];
    },
  });
};

const runBatchTest = async () => {
  if (selectedFactors.value.length === 0) {
    message.warning("请选择要测试的因子");
    return;
  }
  loading.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    batchTestResults.value = selectedFactors.value.map((f: Factor) => ({
      factorId: f.id,
      factorName: f.name,
      annualReturn: Math.random() * 0.3 - 0.05,
      sharpeRatio: Math.random() * 2,
      maxDrawdown: Math.random() * -0.2 - 0.1,
      winRate: Math.random() * 0.3 + 0.5,
      icMean: Math.random() * 0.1,
    }));
    error.value = false;
    message.success(
      `批量测试完成，共测试 ${selectedFactors.value.length} 个因子`,
    );
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const exportBatchResults = () => message.info("导出批量测试报告");
const viewFactorDetail = (result: any) => {
  const f = factors.value.find((ff) => ff.id === result.factorId);
  if (f) handleTestFactor(f);
};
const importFactors = () => message.info("导入功能开发中");
const exportFactors = () => message.info("导出功能开发中");
const openFactorCorrelation = () => message.info("打开因子相关性分析工具");
const openStabilityAnalysis = () => message.info("打开因子稳定性分析工具");
const openCombinationAnalysis = () => message.info("打开因子组合优化工具");

onMounted(() => {
  pagination.total = factors.value.length;
});
</script>

<style lang="scss" scoped>
.factor-library {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  .page-title {
    margin: 0;
    color: var(--n-text-color-1);
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.library-management {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-actions {
  padding: 10px;
  background: var(--n-color-embedded);
  border-radius: 4px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  .selected-text {
    color: var(--n-text-color-2);
    margin-right: 10px;
  }
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

.batch-test-results,
.analysis-tools {
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
    .tool-info {
      .tool-title {
        font-weight: 500;
        margin-bottom: 4px;
      }
      .tool-desc {
        font-size: 12px;
        color: var(--n-text-color-3);
      }
    }
  }
}

.positive {
  color: #67c23a;
}
.negative {
  color: #f56c6c;
}
</style>
