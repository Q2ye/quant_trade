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
        </NGridItem>
      </NGrid>
    </div>

    <NSpin :show="loading">
      <NDataTable
        :data="pagedData"
        :columns="columns"
        :bordered="false"
        :default-sort="{ prop: 'detectedTime', order: 'descending' }"
      />
    </NSpin>

    <div class="pagination-container">
      <NPagination
        v-model:page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :item-count="total"
        show-size-picker
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch, h } from "vue";
import {
  NGrid,
  NGridItem,
  NInput,
  NSelect,
  NButton,
  NDataTable,
  NPagination,
  NSpin,
  NTag,
  useMessage,
} from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import type { DataIssue } from "@/api/data-sync";
import { usePagedList } from "@/composables/usePagedList";

const message = useMessage();

const props = defineProps<{
  issues: DataIssue[];
}>();

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
// 客户端分页：表格展示切片后的当前页
const {
  page: currentPage,
  pageSize,
  itemCount: total,
  pagedData,
} = usePagedList(tableData, 20);

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

const columns: DataTableColumn<DataAnomaly>[] = [
  {
    key: "tableName",
    title: "类型",
    width: 120,
    render: (row: DataAnomaly) =>
      h("span", { style: { fontWeight: 500 } }, row.tableName),
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
    width: 180,
    ellipsis: { tooltip: true },
  },
  {
    key: "affectedRecords",
    title: "影响记录数",
    width: 100,
    render: (row: DataAnomaly) =>
      row.affectedRecords ? row.affectedRecords.toLocaleString() + " 条" : "-",
  },
];

const loadTableData = async () => {
  loading.value = true;
  try {
    const data = props.issues.map((issue, i) => ({
      id: String(i + 1),
      tableName: issue.issue_type,
      anomalyType: issue.issue_type,
      description: issue.description,
      severity: issue.severity,
      detectedTime: new Date().toISOString(),
      status: "pending",
      suggestedAction:
        issue.severity === "critical" || issue.severity === "high"
          ? "请立即检查并修复数据"
          : "请关注并适时处理",
      affectedRecords: issue.count,
    }));
    tableData.value = data;
  } catch (error) {
    message.error("数据加载失败");
  } finally {
    loading.value = false;
  }
};

const handleFilter = () => {
  currentPage.value = 1;
  loadTableData();
};
const handleReset = () => {
  Object.assign(filterParams, { tableName: "", anomalyType: "", severity: "" });
  handleFilter();
};

watch(
  () => props.issues,
  () => {
    currentPage.value = 1;
    loadTableData();
  },
  { immediate: false },
);

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
