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
  NProgress,
  useMessage,
} from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import type { QualityMetric } from "@/api/data-sync";

const message = useMessage();

const props = defineProps<{
  metrics: QualityMetric[];
}>();

interface DataAccuracy {
  id: string;
  tableName: string;
  description: string;
  accuracyRate: number;
  threshold: number;
  status: string;
}

const loading = ref(false);
const tableData = ref<DataAccuracy[]>([]);
const filterParams = reactive({
  tableName: "",
  accuracyStatus: "",
  verificationType: "",
});
const pagination = reactive({ currentPage: 1, pageSize: 20, total: 0 });

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

const getRateTextClass = (rate: number) => {
  if (rate >= 98) return "rate-high";
  if (rate >= 90) return "rate-medium";
  return "rate-low";
};
const getStatusTagType = (status: string) => {
  const m: Record<string, "success" | "warning" | "error"> = {
    pass: "success",
    warning: "warning",
    fail: "error",
  };
  return m[status] || "default";
};
const getStatusText = (status: string) => {
  const m: Record<string, string> = {
    pass: "通过",
    warning: "警告",
    fail: "未通过",
  };
  return m[status] || status;
};

const columns: DataTableColumn<DataAccuracy>[] = [
  {
    key: "index",
    title: "序号",
    width: 60,
    render: (_: any, index: number) => index + 1,
  },
  {
    key: "tableName",
    title: "指标名称",
    width: 150,
    render: (row: DataAccuracy) =>
      h("div", { style: { fontWeight: 500 } }, row.tableName),
  },
  {
    key: "description",
    title: "指标详情",
    minWidth: 200,
    ellipsis: { tooltip: true },
  },
  {
    key: "accuracyRate",
    title: "数值",
    width: 160,
    sorter: true,
    render: (row: DataAccuracy) =>
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            percentage: row.accuracyRate,
            status:
              row.status === "pass"
                ? "success"
                : row.status === "warning"
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
    key: "threshold",
    title: "阈值",
    width: 80,
    render: (row: DataAccuracy) =>
      h("span", {}, row.threshold > 0 ? String(row.threshold) : "-"),
  },
  {
    key: "status",
    title: "状态",
    width: 80,
    render: (row: DataAccuracy) =>
      h(
        NTag,
        { type: getStatusTagType(row.status), size: "small" },
        { default: () => getStatusText(row.status) },
      ),
  },
];

const loadTableData = async () => {
  loading.value = true;
  try {
    const data = props.metrics.map((m, i) => ({
      id: String(i + 1),
      tableName: m.metric_name,
      description: `阈值: ${m.threshold ?? "-"}, 当前值: ${m.metric_value}`,
      accuracyRate: Math.min(m.metric_value, 100),
      threshold: m.threshold ?? 0,
      status: m.status,
    }));
    tableData.value = data;
    pagination.total = data.length;
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

watch(
  () => props.metrics,
  () => {
    pagination.currentPage = 1;
    loadTableData();
  },
  { immediate: false },
);

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
