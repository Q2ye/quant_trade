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
        :data="tableData"
        :columns="columns"
        :bordered="false"
        :default-sort="{ prop: 'completenessRate', order: 'descending' }"
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
      :title="`数据表详情 - ${currentTable?.tableName || ''}`"
      style="width: 800px"
    >
      <DataTableDetail v-if="detailDialogVisible" :table-data="currentTable" />
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
import DataTableDetail from "@/components/data/DataTableDetail.vue";

const message = useMessage();
const dialog = useDialog();

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
const pagination = reactive({ currentPage: 1, pageSize: 20, total: 0 });
const detailDialogVisible = ref(false);
const currentTable = ref<TableCompleteness | null>(null);

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

const columns: DataTableColumn<any>[] = [
  {
    key: "tableName",
    title: "表名",
    width: 140,
    render: (row: TableCompleteness) =>
      h("div", { style: { fontWeight: 500 } }, row.tableName),
  },
  {
    key: "tableDescription",
    title: "描述",
    width: 160,
    ellipsis: { tooltip: true },
  },
  {
    key: "dataType",
    title: "数据类型",
    width: 100,
    render: (row: TableCompleteness) => {
      const typeMap: Record<
        string,
        { type: "info" | "success" | "warning"; text: string }
      > = {
        market: { type: "info", text: "行情数据" },
        financial: { type: "success", text: "财务数据" },
        basic: { type: "info", text: "基础信息" },
        etf: { type: "warning", text: "ETF数据" },
      };
      const t = typeMap[row.dataType] || {
        type: "default" as const,
        text: row.dataType,
      };
      return h(
        NTag,
        { type: t.type, size: "small" },
        { default: () => t.text },
      );
    },
  },
  {
    key: "totalRecords",
    title: "总记录数",
    width: 110,
    align: "right",
    render: (row: TableCompleteness) => formatNumber(row.totalRecords),
  },
  {
    key: "expectedRecords",
    title: "预期记录数",
    width: 110,
    align: "right",
    render: (row: TableCompleteness) => formatNumber(row.expectedRecords),
  },
  {
    key: "completenessRate",
    title: "完整率",
    width: 160,
    sorter: true,
    render: (row: TableCompleteness) =>
      h(
        "div",
        { style: { display: "flex", alignItems: "center", gap: "8px" } },
        [
          h(NProgress, {
            percentage: row.completenessRate,
            status:
              row.completenessRate >= 98
                ? "success"
                : row.completenessRate >= 95
                  ? "warning"
                  : "error",
            showIndicator: false,
          }),
          h(
            "span",
            {
              class: getRateTextClass(row.completenessRate),
              style: { fontSize: "12px", fontWeight: "500" },
            },
            row.completenessRate.toFixed(1) + "%",
          ),
        ],
      ),
  },
  {
    key: "missingPeriods",
    title: "缺失时段",
    width: 150,
    render: (row: TableCompleteness) => {
      if (!row.missingPeriods || row.missingPeriods.length === 0)
        return h("span", { class: "no-missing" }, "无缺失");
      return h(
        "div",
        { style: { maxHeight: "60px", overflowY: "auto" } },
        row.missingPeriods
          .slice(0, 3)
          .map((p) => h("div", { class: "period-item" }, p)),
      );
    },
  },
  {
    key: "lastUpdateTime",
    title: "最后更新时间",
    width: 140,
    render: (row: TableCompleteness) => formatTime(row.lastUpdateTime),
  },
  {
    key: "dataFreshness",
    title: "新鲜度",
    width: 80,
    render: (row: TableCompleteness) => {
      const map: Record<
        string,
        { type: "success" | "warning" | "error"; text: string }
      > = {
        fresh: { type: "success", text: "最新" },
        stale: { type: "warning", text: "较旧" },
        outdated: { type: "error", text: "过时" },
      };
      const t = map[row.dataFreshness] || {
        type: "default" as const,
        text: row.dataFreshness,
      };
      return h(
        NTag,
        { type: t.type, size: "small" },
        { default: () => t.text },
      );
    },
  },
  {
    key: "actions",
    title: "操作",
    width: 120,
    fixed: "right",
    render: (row: TableCompleteness) =>
      h("div", { style: { display: "flex", gap: "4px" } }, [
        h(
          NButton,
          { size: "tiny", text: true, onClick: () => handleViewDetail(row) },
          { default: () => "详情" },
        ),
        row.completenessRate < 95
          ? h(
              NButton,
              {
                size: "tiny",
                text: true,
                type: "warning",
                onClick: () => handleSyncData(row),
              },
              { default: () => "同步" },
            )
          : null,
      ]),
  },
];

const getRateTextClass = (rate: number) => {
  if (rate >= 98) return "rate-high";
  if (rate >= 95) return "rate-medium";
  return "rate-low";
};

const formatNumber = (num: number) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (num >= 1000) return (num / 1000).toFixed(1) + "K";
  return num.toString();
};

const formatTime = (time: string) => time.replace(" ", "\n");

const loadTableData = async () => {
  loading.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const mockData: TableCompleteness[] = [
      {
        id: "1",
        tableName: "stock_daily",
        tableDescription: "A股日线行情表",
        dataType: "market",
        totalRecords: 12500000,
        expectedRecords: 12800000,
        completenessRate: 97.7,
        missingPeriods: ["2023-01-03", "2023-05-08", "2023-10-02"],
        lastUpdateTime: "2024-01-15 16:30:00",
        dataFreshness: "fresh",
        isCoreTable: true,
      },
      {
        id: "2",
        tableName: "stock_basic",
        tableDescription: "股票基础信息表",
        dataType: "basic",
        totalRecords: 5200,
        expectedRecords: 5500,
        completenessRate: 94.5,
        missingPeriods: [],
        lastUpdateTime: "2024-01-15 09:00:00",
        dataFreshness: "fresh",
        isCoreTable: true,
      },
      {
        id: "3",
        tableName: "stock_minutes",
        tableDescription: "股票分钟行情表",
        dataType: "market",
        totalRecords: 185000000,
        expectedRecords: 200000000,
        completenessRate: 92.5,
        missingPeriods: [
          "2023-12-29 14:30",
          "2024-01-02 10:15",
          "2024-01-08 15:45",
        ],
        lastUpdateTime: "2024-01-15 17:00:00",
        dataFreshness: "fresh",
        isCoreTable: true,
      },
      {
        id: "4",
        tableName: "stock_income_core",
        tableDescription: "利润表核心信息表",
        dataType: "financial",
        totalRecords: 85000,
        expectedRecords: 95000,
        completenessRate: 89.5,
        missingPeriods: ["2023Q1", "2023Q2", "2023Q3"],
        lastUpdateTime: "2024-01-10 14:20:00",
        dataFreshness: "stale",
        isCoreTable: false,
      },
      {
        id: "5",
        tableName: "etf_daily",
        tableDescription: "ETF日线行情",
        dataType: "etf",
        totalRecords: 3200000,
        expectedRecords: 3300000,
        completenessRate: 97.0,
        missingPeriods: ["2023-11-15"],
        lastUpdateTime: "2024-01-15 16:45:00",
        dataFreshness: "fresh",
        isCoreTable: false,
      },
      {
        id: "6",
        tableName: "stock_moneyflow",
        tableDescription: "个股资金流向表",
        dataType: "market",
        totalRecords: 9800000,
        expectedRecords: 10500000,
        completenessRate: 93.3,
        missingPeriods: ["2023-08-14", "2023-09-28"],
        lastUpdateTime: "2024-01-15 17:30:00",
        dataFreshness: "fresh",
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
    dataType: "",
    completenessStatus: "",
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

const handleViewDetail = (row: TableCompleteness) => {
  currentTable.value = row;
  detailDialogVisible.value = true;
};

const handleSyncData = (row: TableCompleteness) => {
  dialog.warning({
    title: "数据同步确认",
    content: `确定要同步 ${row.tableName} 表的数据吗？`,
    positiveText: "确定",
    negativeText: "取消",
    onPositiveClick: async () => {
      loading.value = true;
      await new Promise((resolve) => setTimeout(resolve, 2000));
      message.success(`开始同步 ${row.tableName} 数据`);
      loading.value = false;
    },
  });
};

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
