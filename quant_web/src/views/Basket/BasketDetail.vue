<template>
  <div class="basket-detail bg-gradient-mesh bg-noise">
    <n-result
      v-if="error"
      status="500"
      title="加载失败"
      description="获取篮子详情失败，请稍后重试"
    >
      <template #footer
        ><n-button @click="getBasketDetail(basketId)">重试</n-button></template
      >
    </n-result>

    <n-spin v-else :show="loading">
      <div class="back-header">
        <n-button text @click="$router.go(-1)">
          <Icon icon="ant-design:arrow-left-outlined" /> 返回
        </n-button>
        <span class="back-title">{{ basket.name }}</span>
      </div>

      <div class="header">
        <h2>{{ basket.name }}</h2>
        <p class="description">{{ basket.description }}</p>
      </div>

      <div class="chart-section">
        <h3>篮子净值走势</h3>
        <NetValueChart :chart-data="chartData" height="400px" />
      </div>

      <div class="stocks-section">
        <h3>成分股列表</h3>
        <n-data-table
          :data="basket.items"
          :columns="stockColumns"
          :bordered="false"
          striped
          :row-key="(row: any) => row.ts_code"
        />
      </div>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { NButton, NResult } from "naive-ui";
import { useMessage } from "naive-ui";
import { Icon } from "@iconify/vue";
import { getBasket } from "@/api/basket";
import { fetchStockRealTime } from "@/api/data";
import NetValueChart from "@/components/charts/NetValueChart.vue";

const route = useRoute();
const message = useMessage();
const loading = ref(false);
const error = ref(false);

const basket = ref<any>({ id: "", name: "", description: "", items: [] });
const realTimeData = ref<any>({});
const chartData = ref({
  dates: [] as string[],
  values: [] as number[],
  benchmark: [] as number[],
});

const stockColumns = [
  { title: "代码", key: "ts_code", width: 100 },
  {
    title: "名称",
    minWidth: 150,
    render(row: any) {
      return row.stock_info?.name || row.ts_code;
    },
  },
  {
    title: "当前价",
    width: 120,
    render(row: any) {
      return realTimeData.value[row.ts_code]?.price ?? "--";
    },
  },
  {
    title: "涨跌幅",
    width: 120,
    render(row: any) {
      const cp = realTimeData.value[row.ts_code]?.change_percent ?? 0;
      const cls = cp > 0 ? "color-up" : cp < 0 ? "color-down" : "";
      return h("span", { class: cls }, `${cp}%`);
    },
  },
  {
    title: "权重",
    width: 120,
    render(row: any) {
      return `${(row.weight * 100).toFixed(2)}%`;
    },
  },
  {
    title: "操作",
    width: 100,
    render(row: any) {
      return h(
        NButton,
        {
          text: true,
          onClick: () => window.open(`/market/detail/${row.ts_code}`, "_self"),
        },
        { default: () => "行情" },
      );
    },
  },
];

const getBasketDetail = async (basketId: string) => {
  loading.value = true;
  try {
    basket.value = await getBasket(basketId);
    getRealTimeData();
    loadChartData();
    error.value = false;
  } catch (err) {
    console.error("获取篮子详情失败:", err);
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const getRealTimeData = async () => {
  const codes = basket.value.items.map((item: any) => item.ts_code);
  try {
    realTimeData.value = await fetchStockRealTime(codes);
  } catch (error) {
    console.error("获取实时行情失败:", error);
  }
};

const loadChartData = () => {
  chartData.value = {
    dates: ["2023-01", "2023-02", "2023-03", "2023-04"],
    values: [1.0, 1.05, 1.12, 1.08],
    benchmark: [1.0, 1.03, 1.1, 1.05],
  };
};

const basketId = route.params.id as string;
if (basketId) getBasketDetail(basketId);
</script>

<style scoped>
.basket-detail {
  display: block;
  padding: 20px;
  background: var(--n-card-color);
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.back-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--n-border-color);
}
.back-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
}
.header {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--n-border-color);
}
.description {
  color: var(--n-text-color-3);
  margin-top: 5px;
}
.chart-section {
  margin-bottom: 30px;
}
.stocks-section {
  margin-top: 30px;
}
.color-up {
  color: #f56c6c;
}
.color-down {
  color: #67c23a;
}
</style>
