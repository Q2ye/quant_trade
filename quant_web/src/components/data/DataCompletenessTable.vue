<template>
  <div class="data-completeness-table">
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
            v-model:value="filterParams.dataType"
            :options="dataTypeOptions"
            placeholder="数据类型"
            clearable
            @update:value="handleFilter"
          />
        </NGridItem>
        <NGridItem :span="6">
          <NSelect
            v-model:value="filterParams.completenessStatus"
            :options="completenessOptions"
            placeholder="完整状态"
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
        :default-sort="{ prop: 'completenessRate', order: 'descending' }"
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
  NProgress,
  useMessage,
} from "naive-ui";
import { Icon } from "@iconify/vue";
import type { DataTableColumn } from "naive-ui";
import type { QualityMetric } from "@/api/data-sync";
import { usePagedList } from "@/composables/usePagedList";

const message = useMessage();

const props = defineProps<{
  metrics: QualityMetric[];
}>();

interface TableCompleteness {
  id: string;
  tableName: string;
  tableDescription: string;
  dataType: string;
  totalRecords: number;
  expectedRecords: number;
  completenessRate: number;
  missingPeriods: string[];
  lastUpdateTime: string;
  dataFreshness: string;
  isCoreTable: boolean;
}

interface FilterParams {
  tableName: string;
  dataType: string;
  completenessStatus: string;
}

const loading = ref(false);
const tableData = ref<TableCompleteness[]>([]);
const filterParams = reactive<FilterParams>({
  tableName: "",
  dataType: "",
  completenessStatus: "",
});
// 客户端分页：表格展示切片后的当前页
const {
  page: currentPage,
  pageSize,
  itemCount: total,
  pagedData,
} = usePagedList(tableData, 20);
const dataTypeOptions = [
  { label: "行情数据", value: "market" },
  { label: "财务数据", value: "financial" },
  { label: "基础信息", value: "basic" },
  { label: "ETF数据", value: "etf" },
];
const completenessOptions = [
  { label: "完整", value: "complete" },
  { label: "部分缺失", value: "partial" },
  { label: "严重缺失", value: "incomplete" },
];

const columns: DataTableColumn<TableCompleteness>[] = [
  {
    key: "tableName",
    title: "指标名称",
    width: 160,
    render: (row: TableCompleteness) =>
      h("div", { style: { fontWeight: 500 } }, row.tableName),
  },
  {
    key: "completenessRate",
    title: "达标率",
    width: 180,
    sorter: true,
    render: (row: TableCompleteness) => {
      const metric = props.metrics.find((m) => m.metric_name === row.tableName);
      const value = metric?.metric_value ?? 0;
      const threshold = metric?.threshold ?? 95;
      const displayRate = Math.min(value, 100);
      return h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            percentage: displayRate,
            status:
              value >= threshold
                ? "success"
                : value >= threshold * 0.9
                  ? "warning"
                  : "error",
            showIndicator: false,
          }),
          h(
            "span",
            {
              class: getRateTextClass(displayRate),
              style: { fontSize: "12px", fontWeight: "500" },
            },
            displayRate.toFixed(1) + "%",
          ),
        ],
      );
    },
  },
  {
    key: "tableDescription",
    title: "阈值",
    width: 100,
    render: (row: TableCompleteness) => {
      const metric = props.metrics.find((m) => m.metric_name === row.tableName);
      const threshold = metric?.threshold;
      return h("span", {}, threshold != null ? String(threshold) : "-");
    },
  },
  {
    key: "dataFreshness",
    title: "状态",
    width: 80,
    render: (row: TableCompleteness) => {
      const metric = props.metrics.find((m) => m.metric_name === row.tableName);
      const status = metric?.status ?? "unknown";
      const map: Record<
        string,
        { type: "success" | "warning" | "error"; text: string }
      > = {
        pass: { type: "success", text: "通过" },
        warning: { type: "warning", text: "警告" },
        fail: { type: "error", text: "未通过" },
      };
      const t = map[status] || { type: "default" as const, text: status };
      return h(
        NTag,
        { type: t.type, size: "small" },
        { default: () => t.text },
      );
    },
  },
];

const getRateTextClass = (rate: number) => {
  if (rate >= 98) return "rate-high";
  if (rate >= 90) return "rate-medium";
  return "rate-low";
};

const loadTableData = async () => {
  loading.value = true;
  try {
    const data = props.metrics.map((m, i) => ({
      id: String(i + 1),
      tableName: m.metric_name,
      tableDescription: m.metric_name,
      dataType: "quality",
      totalRecords: 0,
      expectedRecords: 0,
      completenessRate:
        m.status === "pass" ? 100 : m.status === "warning" ? 90 : 70,
      missingPeriods: [] as string[],
      lastUpdateTime: new Date().toISOString(),
      dataFreshness: "fresh",
      isCoreTable: m.metric_name.includes("完整"),
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
  Object.assign(filterParams, {
    tableName: "",
    dataType: "",
    completenessStatus: "",
  });
  handleFilter();
};

watch(
  () => props.metrics,
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
.data-completeness-table {
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
.no-missing {
  color: #67c23a;
  font-size: 12px;
}
.period-item {
  padding: 2px 0;
  font-size: 12px;
  color: var(--n-text-color-3);
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
.pagination-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding: 16px 0;
}
</style>
