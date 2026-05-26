<template>
  <div class="data-anomalies-table">
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
            v-model:value="filterParams.anomalyType"
            :options="anomalyTypeOptions"
            placeholder="异常类型"
            clearable
            @update:value="handleFilter"
          />
        </NGridItem>
        <NGridItem :span="6">
          <NSelect
            v-model:value="filterParams.severity"
            :options="severityOptions"
            placeholder="严重程度"
            clearable
            @update:value="handleFilter"
          />
        </NGridItem>
        <NGridItem :span="6">
          <NButton type="primary" @click="handleFilter">
            <Icon icon="mdi:magnify" class="button-icon" />查询
          </NButton>
          <NButton style="margin-left: 8px" @click="handleReset">
            <Icon icon="mdi:refresh" class="button-icon" />重置
          </NButton>
          <NButton
            style="margin-left: 8px"
            type="warning"
            @click="handleExportAnomalies"
          >
            <Icon icon="mdi:file-export" class="button-icon" />导出异常报告
          </NButton>
        </NGridItem>
      </NGrid>
    </div>

    <NSpin :show="loading">
      <NDataTable
        :data="tableData"
        :columns="columns"
        :bordered="false"
        :default-sort="{ prop: 'detectedTime', order: 'descending' }"
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
      :title="`异常详情 - ${currentAnomaly?.tableName || ''}`"
      style="width: 900px"
    >
      <AnomalyDetail
        v-if="detailDialogVisible"
        :anomaly-data="currentAnomaly"
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
  useMessage,
  useDialog,
} from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import AnomalyDetail from "@/components/data/AnomalyDetail.vue";

const message = useMessage();
const dialogs = useDialog();

interface DataAnomaly {
  id: string;
  tableName: string;
  anomalyType: string;
  description: string;
  severity: string;
  detectedTime: string;
  status: string;
  suggestedAction: string;
  affectedRecords?: number;
  isCoreTable: boolean;
  details?: {
    fieldName?: string;
    expectedValue?: any;
    actualValue?: any;
    errorCount?: number;
    sampleRecords?: any[];
  };
}

interface FilterParams {
  tableName: string;
  anomalyType: string;
  severity: string;
}

const loading = ref(false);
const tableData = ref<DataAnomaly[]>([]);
const filterParams = reactive<FilterParams>({
  tableName: "",
  anomalyType: "",
  severity: "",
});
const pagination = reactive({ currentPage: 1, pageSize: 20, total: 0 });
const detailDialogVisible = ref(false);
const currentAnomaly = ref<DataAnomaly | null>(null);

const anomalyTypeOptions = [
  { label: "数据缺失", value: "missing" },
  { label: "数据异常", value: "outlier" },
  { label: "格式错误", value: "format" },
  { label: "逻辑错误", value: "logic" },
  { label: "重复数据", value: "duplicate" },
];
const severityOptions = [
  { label: "低", value: "low" },
  { label: "中", value: "medium" },
  { label: "高", value: "high" },
  { label: "严重", value: "critical" },
];

const getAnomalyTypeTagType = (type: string) => {
  const m: Record<string, "warning" | "error" | "info"> = {
    missing: "warning",
    outlier: "error",
    format: "info",
    logic: "error",
    duplicate: "warning",
  };
  return m[type] || "default";
};
const getAnomalyTypeText = (type: string) => {
  const m: Record<string, string> = {
    missing: "数据缺失",
    outlier: "数据异常",
    format: "格式错误",
    logic: "逻辑错误",
    duplicate: "重复数据",
  };
  return m[type] || type;
};
const getSeverityTagType = (s: string) => {
  const m: Record<string, "info" | "warning" | "error"> = {
    low: "info",
    medium: "warning",
    high: "error",
    critical: "error",
  };
  return m[s] || "default";
};
const getSeverityText = (s: string) => {
  const m: Record<string, string> = {
    low: "低",
    medium: "中",
    high: "高",
    critical: "严重",
  };
  return m[s] || s;
};
const getStatusTagType = (s: string) => {
  const m: Record<string, "warning" | "success" | "info"> = {
    pending: "warning",
    resolved: "success",
    ignored: "info",
  };
  return m[s] || "default";
};
const getStatusText = (s: string) => {
  const m: Record<string, string> = {
    pending: "待处理",
    resolved: "已解决",
    ignored: "已忽略",
  };
  return m[s] || s;
};

const columns: DataTableColumn<any>[] = [
  {
    key: "tableName",
    title: "表名",
    width: 130,
    render: (row: DataAnomaly) =>
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
    key: "anomalyType",
    title: "异常类型",
    width: 100,
    render: (row: DataAnomaly) =>
      h(
        NTag,
        {
          type: getAnomalyTypeTagType(row.anomalyType),
          size: "small",
        },
        { default: () => getAnomalyTypeText(row.anomalyType) },
      ),
  },
  {
    key: "description",
    title: "异常描述",
    width: 200,
    ellipsis: { tooltip: true },
  },
  {
    key: "severity",
    title: "严重程度",
    width: 90,
    render: (row: DataAnomaly) =>
      h(
        NTag,
        {
          type: getSeverityTagType(row.severity),
          size: "small",
        },
        { default: () => getSeverityText(row.severity) },
      ),
  },
  {
    key: "detectedTime",
    title: "检测时间",
    width: 130,
    sorter: true,
    render: (row: DataAnomaly) => row.detectedTime.replace(" ", "\n"),
  },
  {
    key: "status",
    title: "状态",
    width: 80,
    render: (row: DataAnomaly) =>
      h(
        NTag,
        {
          type: getStatusTagType(row.status),
          size: "small",
        },
        { default: () => getStatusText(row.status) },
      ),
  },
  {
    key: "suggestedAction",
    title: "建议操作",
    width: 160,
    ellipsis: { tooltip: true },
  },
  {
    key: "affectedRecords",
    title: "影响记录数",
    width: 100,
    render: (row: DataAnomaly) =>
      row.affectedRecords ? row.affectedRecords.toLocaleString() + " 条" : "-",
  },
  {
    key: "actions",
    title: "操作",
    width: 180,
    fixed: "right",
    render: (row: DataAnomaly) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "tiny", text: true, onClick: () => handleViewDetail(row) },
          { default: () => "详情" },
        ),
        row.status === "pending"
          ? h(
              NButton,
              {
                size: "tiny",
                text: true,
                type: "success",
                onClick: () => handleMarkResolved(row),
              },
              { default: () => "标记解决" },
            )
          : null,
        row.status === "pending"
          ? h(
              NButton,
              {
                size: "tiny",
                text: true,
                type: "warning",
                onClick: () => handleIgnoreAnomaly(row),
              },
              { default: () => "忽略" },
            )
          : null,
      ]),
  },
];

const loadTableData = async () => {
  loading.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const mockData: DataAnomaly[] = [
      {
        id: "1",
        tableName: "stock_daily",
        anomalyType: "outlier",
        description: "收盘价异常波动，超过3倍标准差",
        severity: "high",
        detectedTime: "2024-01-15 18:30:00",
        status: "pending",
        suggestedAction: "检查数据源，验证异常价格",
        affectedRecords: 23,
        isCoreTable: true,
      },
      {
        id: "2",
        tableName: "stock_basic",
        anomalyType: "missing",
        description: "新上市股票基础信息缺失",
        severity: "medium",
        detectedTime: "2024-01-15 17:45:00",
        status: "pending",
        suggestedAction: "同步最新股票基础信息",
        affectedRecords: 5,
        isCoreTable: true,
      },
      {
        id: "3",
        tableName: "stock_minutes",
        anomalyType: "format",
        description: "分钟数据时间戳格式错误",
        severity: "low",
        detectedTime: "2024-01-15 16:20:00",
        status: "resolved",
        suggestedAction: "已修复时间戳格式",
        affectedRecords: 1200,
        isCoreTable: true,
      },
      {
        id: "4",
        tableName: "stock_income_core",
        anomalyType: "logic",
        description: "利润表数据逻辑错误：营业收入 < 营业成本",
        severity: "critical",
        detectedTime: "2024-01-15 15:30:00",
        status: "pending",
        suggestedAction: "验证财务数据准确性",
        affectedRecords: 8,
        isCoreTable: false,
      },
      {
        id: "5",
        tableName: "etf_daily",
        anomalyType: "duplicate",
        description: "ETF日线数据重复记录",
        severity: "medium",
        detectedTime: "2024-01-15 14:15:00",
        status: "ignored",
        suggestedAction: "清理重复数据",
        affectedRecords: 45,
        isCoreTable: false,
      },
      {
        id: "6",
        tableName: "stock_moneyflow",
        anomalyType: "outlier",
        description: "资金流向数据异常：净流入量异常大",
        severity: "high",
        detectedTime: "2024-01-15 13:45:00",
        status: "pending",
        suggestedAction: "检查资金流向计算逻辑",
        affectedRecords: 12,
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
  Object.assign(filterParams, { tableName: "", anomalyType: "", severity: "" });
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
const handleViewDetail = (row: DataAnomaly) => {
  currentAnomaly.value = row;
  detailDialogVisible.value = true;
};

const handleMarkResolved = (row: DataAnomaly) => {
  dialogs.warning({
    title: "标记解决确认",
    content: "确定要将该异常标记为已解决吗？",
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: async () => {
      loading.value = true;
      await new Promise((resolve) => setTimeout(resolve, 500));
      row.status = "resolved";
      message.success("异常已标记为已解决");
      loading.value = false;
    },
  });
};

const handleIgnoreAnomaly = (row: DataAnomaly) => {
  dialogs.warning({
    title: "忽略异常确认",
    content: "确定要忽略该异常吗？忽略后将从监控列表中移除。",
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: async () => {
      loading.value = true;
      await new Promise((resolve) => setTimeout(resolve, 500));
      row.status = "ignored";
      message.success("异常已忽略");
      loading.value = false;
    },
  });
};

const handleExportAnomalies = () => message.success("开始导出异常报告...");

onMounted(() => {
  loadTableData();
});
</script>

<style scoped>
.data-anomalies-table {
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
.table-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.name-text {
  font-weight: 500;
}
.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 16px 0;
}
</style>
