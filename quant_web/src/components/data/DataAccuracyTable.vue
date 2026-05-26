<template>
  <div class="data-accuracy-table">
    <div class="table-header">
      <NGrid :cols="24" :x-gap="16" class="filter-row">
        <NGridItem :span="6">
          <NInput
            v-model:value="filterParams.tableName"
            placeholder="搜索表名"
            clearable
            @clear="handleFilter"
            @keyup.enter="handleFilter"
          />
        </NGridItem>
        <NGridItem :span="6">
          <NSelect
            v-model:value="filterParams.accuracyStatus"
            :options="accuracyStatusOptions"
            placeholder="准确状态"
            clearable
            @update:value="handleFilter"
          />
        </NGridItem>
        <NGridItem :span="6">
          <NSelect
            v-model:value="filterParams.verificationType"
            :options="verificationTypeOptions"
            placeholder="验证类型"
            clearable
            @update:value="handleFilter"
          />
        </NGridItem>
        <NGridItem :span="6">
          <NButton type="primary" @click="handleFilter"
            ><Icon icon="mdi:magnify" class="button-icon" />查询</NButton
          >
          <NButton style="margin-left: 8px" @click="handleReset"
            ><Icon icon="mdi:refresh" class="button-icon" />重置</NButton
          >
          <NButton
            style="margin-left: 8px"
            type="success"
            @click="handleRunVerification"
            ><Icon icon="mdi:play" class="button-icon" />执行验证</NButton
          >
        </NGridItem>
      </NGrid>
    </div>

    <NSpin :show="loading">
      <NDataTable
        :data="tableData"
        :columns="columns"
        :bordered="false"
        :default-sort="{ prop: 'accuracyRate', order: 'descending' }"
        :row-key="(row: DataAccuracy) => row.id"
      />
    </NSpin>

    <div class="pagination-container">
      <NPagination
        :page="pagination.currentPage"
        :page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :item-count="pagination.total"
        show-size-picker
        @update:page="handleCurrentChange"
        @update:page-size="handleSizeChange"
      />
    </div>

    <NModal
      v-model:show="detailDialogVisible"
      preset="card"
      :title="`准确性验证详情 - ${currentVerification?.tableName || ''}`"
      style="width: 900px"
    >
      <AccuracyDetail
        v-if="detailDialogVisible"
        :verification-data="currentVerification"
      />
    </NModal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, h } from "vue";
import {
  NGrid,
  NGridItem,
  NInput,
  NSelect,
  NButton,
  NDataTable,
  NPagination,
  NModal,
  NSpin,
  NTag,
  NProgress,
  useMessage,
  useDialog,
} from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import AccuracyDetail from "@/components/data/AccuracyDetail.vue";

const message = useMessage();
const dialogs = useDialog();

interface DataAccuracy {
  id: string;
  tableName: string;
  verificationType: string;
  description: string;
  accuracyRate: number;
  checkedRecords: number;
  errorRecords: number;
  lastVerificationTime: string;
  status: string;
  isCoreTable: boolean;
  details?: {
    ruleDescription: string;
    errorExamples?: any[];
    passRate: number;
    validationRules?: string[];
  };
}

const loading = ref(false);
const tableData = ref<DataAccuracy[]>([]);
const filterParams = reactive({
  tableName: "",
  accuracyStatus: "",
  verificationType: "",
});
const pagination = reactive({ currentPage: 1, pageSize: 20, total: 0 });
const detailDialogVisible = ref(false);
const currentVerification = ref<DataAccuracy | null>(null);

const accuracyStatusOptions = [
  { label: "准确", value: "accurate" },
  { label: "警告", value: "warning" },
  { label: "错误", value: "error" },
];
const verificationTypeOptions = [
  { label: "数据一致性", value: "consistency" },
  { label: "业务逻辑", value: "business_logic" },
  { label: "数据范围", value: "data_range" },
  { label: "数据关联", value: "data_relation" },
];

const getVerificationTypeTagType = (type: string) => {
  const m: Record<string, "info" | "success" | "warning"> = {
    consistency: "info",
    business_logic: "success",
    data_range: "warning",
    data_relation: "info",
  };
  return m[type] || "default";
};
const getVerificationTypeText = (type: string) => {
  const m: Record<string, string> = {
    consistency: "数据一致性",
    business_logic: "业务逻辑",
    data_range: "数据范围",
    data_relation: "数据关联",
  };
  return m[type] || type;
};
const getRateTextClass = (rate: number) => {
  if (rate >= 99) return "rate-high";
  if (rate >= 95) return "rate-medium";
  return "rate-low";
};
const getStatusTagType = (status: string) => {
  const m: Record<string, "success" | "warning" | "error"> = {
    accurate: "success",
    warning: "warning",
    error: "error",
  };
  return m[status] || "default";
};
const getStatusText = (status: string) => {
  const m: Record<string, string> = {
    accurate: "准确",
    warning: "警告",
    error: "错误",
  };
  return m[status] || status;
};
const getErrorCountClass = (count: number) => {
  if (count === 0) return "error-zero";
  if (count < 1000) return "error-low";
  return "error-high";
};
const formatNumber = (num: number) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
};

const columns: DataTableColumn<any>[] = [
  {
    key: "index",
    title: "序号",
    width: 60,
    render: (_: any, index: number) => index + 1,
  },
  {
    key: "tableName",
    title: "数据表",
    width: 130,
    render: (row: DataAccuracy) =>
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h("span", { style: { fontWeight: 500 } }, row.tableName),
          row.isCoreTable
            ? h(
                NTag,
                { type: "success", size: "tiny" },
                { default: () => "核心" },
              )
            : null,
        ],
      ),
  },
  {
    key: "verificationType",
    title: "验证类型",
    width: 110,
    render: (row: DataAccuracy) =>
      h(
        NTag,
        {
          type: getVerificationTypeTagType(row.verificationType),
          size: "small",
        },
        { default: () => getVerificationTypeText(row.verificationType) },
      ),
  },
  {
    key: "description",
    title: "验证描述",
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    key: "accuracyRate",
    title: "准确率",
    width: 150,
    sorter: true,
    render: (row: DataAccuracy) =>
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            percentage: row.accuracyRate,
            status:
              row.accuracyRate >= 99
                ? "success"
                : row.accuracyRate >= 95
                  ? "warning"
                  : "error",
            showIndicator: false,
          }),
          h(
            "span",
            {
              class: getRateTextClass(row.accuracyRate),
              style: { fontSize: "12px", fontWeight: "500" },
            },
            row.accuracyRate.toFixed(1) + "%",
          ),
        ],
      ),
  },
  {
    key: "checkedRecords",
    title: "检查记录数",
    width: 110,
    align: "right",
    render: (row: DataAccuracy) => formatNumber(row.checkedRecords),
  },
  {
    key: "errorRecords",
    title: "错误记录数",
    width: 110,
    align: "right",
    render: (row: DataAccuracy) =>
      h(
        "span",
        { class: getErrorCountClass(row.errorRecords) },
        formatNumber(row.errorRecords),
      ),
  },
  {
    key: "lastVerificationTime",
    title: "最后验证时间",
    width: 130,
    sorter: true,
    render: (row: DataAccuracy) => row.lastVerificationTime.replace(" ", "\n"),
  },
  {
    key: "status",
    title: "验证状态",
    width: 90,
    render: (row: DataAccuracy) =>
      h(
        NTag,
        { type: getStatusTagType(row.status), size: "small" },
        { default: () => getStatusText(row.status) },
      ),
  },
  {
    key: "actions",
    title: "操作",
    width: 150,
    fixed: "right",
    render: (row: DataAccuracy) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "tiny", text: true, onClick: () => handleViewDetail(row) },
          { default: () => "详情" },
        ),
        h(
          NButton,
          {
            size: "tiny",
            text: true,
            type: "warning",
            onClick: () => handleRerunVerification(row),
          },
          { default: () => "重新验证" },
        ),
      ]),
  },
];

const loadTableData = async () => {
  loading.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const mockData: DataAccuracy[] = [
      {
        id: "1",
        tableName: "stock_daily",
        verificationType: "data_range",
        description: "价格数据范围验证",
        accuracyRate: 99.8,
        checkedRecords: 12500000,
        errorRecords: 25000,
        lastVerificationTime: "2024-01-15 18:00:00",
        status: "accurate",
        isCoreTable: true,
        details: {
          ruleDescription: "验证最高价 >= 开盘价/收盘价 >= 最低价",
          passRate: 99.8,
          validationRules: [
            "high >= open",
            "high >= close",
            "low <= open",
            "low <= close",
          ],
        },
      },
      {
        id: "2",
        tableName: "stock_basic",
        verificationType: "consistency",
        description: "股票基础信息一致性验证",
        accuracyRate: 98.5,
        checkedRecords: 5200,
        errorRecords: 78,
        lastVerificationTime: "2024-01-15 17:30:00",
        status: "warning",
        isCoreTable: true,
      },
      {
        id: "3",
        tableName: "stock_minutes",
        verificationType: "business_logic",
        description: "分钟数据时间连续性验证",
        accuracyRate: 97.2,
        checkedRecords: 185000000,
        errorRecords: 5180000,
        lastVerificationTime: "2024-01-15 16:45:00",
        status: "error",
        isCoreTable: true,
      },
      {
        id: "4",
        tableName: "stock_income_core",
        verificationType: "business_logic",
        description: "财务报表逻辑验证",
        accuracyRate: 95.8,
        checkedRecords: 85000,
        errorRecords: 3580,
        lastVerificationTime: "2024-01-15 15:20:00",
        status: "warning",
        isCoreTable: false,
      },
      {
        id: "5",
        tableName: "etf_daily",
        verificationType: "data_relation",
        description: "ETF净值与成分股关系验证",
        accuracyRate: 99.5,
        checkedRecords: 3200000,
        errorRecords: 16000,
        lastVerificationTime: "2024-01-15 14:15:00",
        status: "accurate",
        isCoreTable: false,
      },
      {
        id: "6",
        tableName: "stock_moneyflow",
        verificationType: "consistency",
        description: "资金流向数据内部一致性验证",
        accuracyRate: 98.9,
        checkedRecords: 9800000,
        errorRecords: 107800,
        lastVerificationTime: "2024-01-15 13:30:00",
        status: "accurate",
        isCoreTable: false,
      },
    ];
    tableData.value = mockData;
    pagination.total = mockData.length;
  } catch (error) {
    message.error("数据加载失败");
  } finally {
    loading.value = false;
  }
};

const handleFilter = () => {
  pagination.currentPage = 1;
  loadTableData();
};
const handleReset = () => {
  Object.assign(filterParams, {
    tableName: "",
    accuracyStatus: "",
    verificationType: "",
  });
  handleFilter();
};
const handleSizeChange = (size: number) => {
  pagination.pageSize = size;
  loadTableData();
};
const handleCurrentChange = (page: number) => {
  pagination.currentPage = page;
  loadTableData();
};
const handleViewDetail = (row: DataAccuracy) => {
  currentVerification.value = row;
  detailDialogVisible.value = true;
};

const handleRerunVerification = (row: DataAccuracy) => {
  dialogs.warning({
    title: "重新验证确认",
    content: `确定要重新验证 ${row.tableName} 的数据准确性吗？`,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: async () => {
      loading.value = true;
      await new Promise((resolve) => setTimeout(resolve, 2000));
      message.success(`已完成 ${row.tableName} 的准确性验证`);
      loadTableData();
      loading.value = false;
    },
  });
};

const handleRunVerification = () => {
  dialogs.warning({
    title: "执行验证确认",
    content: "确定要执行全量数据准确性验证吗？这可能需要较长时间。",
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: async () => {
      loading.value = true;
      await new Promise((resolve) => setTimeout(resolve, 3000));
      message.success("全量数据准确性验证已完成");
      loadTableData();
      loading.value = false;
    },
  });
};

onMounted(() => {
  loadTableData();
});
</script>

<style scoped>
.data-accuracy-table {
  padding: 0;
}
.table-header {
  margin-bottom: 16px;
}
.filter-row {
  margin-bottom: 16px;
}
.button-icon {
  margin-right: 4px;
}
.rate-high {
  color: #67c23a;
}
.rate-medium {
  color: #e6a23c;
}
.rate-low {
  color: #f56c6c;
}
.error-zero {
  color: #67c23a;
}
.error-low {
  color: #e6a23c;
}
.error-high {
  color: #f56c6c;
  font-weight: 500;
}
.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 16px 0;
}
</style>
