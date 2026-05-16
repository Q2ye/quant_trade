<template>
  <div class="order-history bg-gradient-mesh bg-noise">
    <n-card>
      <template #header>
        <div class="card-header">
          <span>历史订单</span>
          <n-space :size="8">
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="width: 280px"
            />
            <n-button type="primary" size="small" @click="searchOrders"
              >查询</n-button
            >
          </n-space>
        </div>
      </template>

      <n-spin :show="loading">
        <n-result
          v-if="error"
          status="500"
          title="数据加载失败"
          description="请检查网络连接后重试"
        >
          <template #footer>
            <n-button type="primary" @click="fetchOrders">重试</n-button>
          </template>
        </n-result>

        <template v-else>
          <n-data-table
            :columns="columns"
            :data="filteredOrders"
            :bordered="false"
            size="small"
            :max-height="550"
          />
          <div class="pagination">
            <n-pagination
              v-model:page="currentPage"
              v-model:page-size="pageSize"
              :item-count="totalOrders"
              @update:page="handlePageChange"
              @update:page-size="handleSizeChange"
            />
          </div>
        </template>
      </n-spin>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import { useMessage, NTag, NResult, NSpin } from "naive-ui";

const message = useMessage();

const loading = ref(false);
const error = ref(false);

const dateRange = ref<[number, number]>([
  Date.now() - 30 * 24 * 3600 * 1000,
  Date.now(),
]);
const orders = ref<any[]>([]);
const filteredOrders = ref<any[]>([]);
const currentPage = ref(1);
const pageSize = ref(20);
const totalOrders = ref(0);

const getStatusType = (status: string) =>
  ({
    已报: "info" as const,
    已成: "success" as const,
    部分成交: "warning" as const,
    已撤: "default" as const,
    废单: "error" as const,
  })[status] || ("default" as const);

const columns = [
  { title: "委托号", key: "orderId", width: 180 },
  { title: "代码", key: "symbol", width: 100 },
  { title: "名称", key: "name", width: 120 },
  {
    title: "方向",
    key: "direction",
    width: 80,
    render: (row: any) =>
      h(
        "span",
        { style: { color: row.direction === "买入" ? "#f56c6c" : "#67c23a" } },
        row.direction,
      ),
  },
  {
    title: "委托价",
    key: "price",
    width: 120,
    align: "right",
    render: (row: any) => row.price.toFixed(2),
  },
  { title: "数量", key: "quantity", width: 100, align: "right" },
  {
    title: "金额",
    key: "amount",
    width: 120,
    align: "right",
    render: (row: any) => (row.price * row.quantity).toFixed(2),
  },
  {
    title: "状态",
    key: "status",
    width: 100,
    render: (row: any) =>
      h(
        NTag,
        { type: getStatusType(row.status), size: "small" },
        { default: () => row.status },
      ),
  },
  { title: "委托时间", key: "orderTime", width: 180 },
  { title: "成交时间", key: "tradeTime", width: 180 },
  {
    title: "成交价",
    key: "tradePrice",
    width: 120,
    align: "right",
    render: (row: any) =>
      row.status === "已成" ? row.tradePrice.toFixed(2) : "",
  },
];

const fetchOrders = async () => {
  loading.value = true;
  error.value = false;
  try {
    orders.value = [
      {
        orderId: "202308090001",
        symbol: "600519.SH",
        name: "贵州茅台",
        direction: "买入",
        price: 1850.0,
        quantity: 100,
        status: "已成",
        orderTime: "2023-08-09 10:05:32",
        tradeTime: "2023-08-09 10:05:35",
        tradePrice: 1850.5,
      },
      {
        orderId: "202308080002",
        symbol: "000001.SH",
        name: "上证指数",
        direction: "卖出",
        price: 3240.0,
        quantity: 200,
        status: "已成",
        orderTime: "2023-08-08 09:45:18",
        tradeTime: "2023-08-08 09:45:20",
        tradePrice: 3245.67,
      },
      {
        orderId: "202308070003",
        symbol: "300750.SZ",
        name: "宁德时代",
        direction: "买入",
        price: 230.0,
        quantity: 300,
        status: "部分成交",
        orderTime: "2023-08-07 13:25:45",
        tradeTime: "2023-08-07 13:26:10",
        tradePrice: 230.5,
      },
    ];
    filteredOrders.value = orders.value;
    totalOrders.value = orders.value.length;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const filterOrders = () => {
  const start = (currentPage.value - 1) * pageSize.value;
  filteredOrders.value = orders.value.slice(start, start + pageSize.value);
};

const searchOrders = () => message.success("查询成功");
const handleSizeChange = () => {
  currentPage.value = 1;
  filterOrders();
};
const handlePageChange = () => filterOrders();

onMounted(() => fetchOrders());
</script>

<style scoped>
.order-history {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pagination {
  margin-top: 20px;
  text-align: right;
}
</style>
