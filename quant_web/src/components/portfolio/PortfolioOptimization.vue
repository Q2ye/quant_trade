<template>
  <div class="portfolio-optimization">
    <NGrid :cols="24" :x-gap="16">
      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-bubble" width="20" />
              <span>有效前沿</span>
            </div>
          </template>
          <div ref="efficientFrontierChart" style="height: 400px"></div>
        </NCard>
      </NGridItem>

      <NGridItem :span="12">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:weight" width="20" />
              <span>权重优化</span>
            </div>
          </template>
          <div class="optimization-controls">
            <NForm
              :model="optimizationForm"
              label-placement="left"
              label-width="120px"
            >
              <NFormItem label="优化目标">
                <NSelect
                  v-model:value="optimizationForm.objective"
                  :options="objectiveOptions"
                  placeholder="请选择优化目标"
                />
              </NFormItem>
              <NFormItem label="预期收益率">
                <NInputNumber
                  v-model:value="optimizationForm.targetReturn"
                  :min="0"
                  :max="50"
                  :step="0.1"
                />
                <span class="unit-text">%</span>
              </NFormItem>
              <NFormItem label="最大回撤约束">
                <NInputNumber
                  v-model:value="optimizationForm.maxDrawdown"
                  :min="0"
                  :max="30"
                  :step="0.1"
                />
                <span class="unit-text">%</span>
              </NFormItem>
              <NFormItem label="单个资产上限">
                <NInputNumber
                  v-model:value="optimizationForm.maxWeight"
                  :min="0"
                  :max="100"
                  :step="1"
                />
                <span class="unit-text">%</span>
              </NFormItem>
              <NFormItem>
                <NButton
                  type="primary"
                  :loading="optimizing"
                  @click="runOptimization"
                >
                  <Icon icon="mdi:rocket-launch" width="16" />
                  <span style="margin-left: 4px">执行优化</span>
                </NButton>
                <NButton style="margin-left: 8px" @click="resetWeights">
                  <Icon icon="mdi:refresh" width="16" />
                  <span style="margin-left: 4px">重置权重</span>
                </NButton>
              </NFormItem>
            </NForm>
          </div>

          <NDivider />

          <div class="weight-comparison">
            <h4>权重对比</h4>
            <NDataTable :data="weightComparison" :columns="weightColumns" />
          </div>
        </NCard>
      </NGridItem>
    </NGrid>

    <NGrid :cols="24" :x-gap="16" style="margin-top: 16px">
      <NGridItem :span="24">
        <NCard>
          <template #header>
            <div class="card-header">
              <Icon icon="mdi:chart-line" width="20" />
              <span>优化效果对比</span>
            </div>
          </template>
          <div class="optimization-results">
            <NGrid :cols="24" :x-gap="16">
              <NGridItem
                :span="6"
                v-for="metric in optimizationMetrics"
                :key="metric.name"
              >
                <div class="metric-card">
                  <div class="metric-name">{{ metric.name }}</div>
                  <div class="metric-values">
                    <div class="current-value">
                      <span class="label">当前:</span>
                      <span :class="metric.currentClass">{{
                        metric.current
                      }}</span>
                    </div>
                    <div class="optimized-value">
                      <span class="label">优化:</span>
                      <span :class="metric.optimizedClass">{{
                        metric.optimized
                      }}</span>
                    </div>
                  </div>
                  <div
                    class="improvement"
                    :class="metric.improvement >= 0 ? 'positive' : 'negative'"
                  >
                    {{ metric.improvement >= 0 ? "+" : ""
                    }}{{ metric.improvement }}%
                  </div>
                </div>
              </NGridItem>
            </NGrid>
          </div>
        </NCard>
      </NGridItem>
    </NGrid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from "vue";
import {
  NGrid,
  NGridItem,
  NCard,
  NForm,
  NFormItem,
  NSelect,
  NInputNumber,
  NButton,
  NDivider,
  NDataTable,
} from "naive-ui";
import type { DataTableColumn } from "naive-ui";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";
import { useMessage } from "naive-ui";

const message = useMessage();
const efficientFrontierChart = ref<HTMLElement>();
const optimizing = ref(false);

interface WeightItem {
  asset: string;
  current: number;
  optimized: number;
  change: number;
}

const optimizationForm = ref({
  objective: "sharpe",
  targetReturn: 15.0,
  maxDrawdown: 20,
  maxWeight: 30,
});

const objectiveOptions = [
  { label: "最大化夏普比率", value: "sharpe" },
  { label: "最小化波动率", value: "volatility" },
  { label: "最大化收益", value: "return" },
  { label: "风险平价", value: "risk_parity" },
];

const weightComparison = ref<WeightItem[]>([
  { asset: "贵州茅台", current: 15.5, optimized: 12.8, change: -2.7 },
  { asset: "宁德时代", current: 12.2, optimized: 10.5, change: -1.7 },
  { asset: "腾讯控股", current: 10.8, optimized: 14.2, change: 3.4 },
  { asset: "招商银行", current: 8.7, optimized: 9.5, change: 0.8 },
  { asset: "中国平安", current: 7.3, optimized: 8.2, change: 0.9 },
  { asset: "其他股票", current: 25.5, optimized: 24.8, change: -0.7 },
  { asset: "债券", current: 15.0, optimized: 15.0, change: 0 },
  { asset: "现金", current: 5.0, optimized: 5.0, change: 0 },
]);

const optimizationMetrics = ref([
  {
    name: "夏普比率",
    current: "1.80",
    optimized: "2.15",
    improvement: 19.4,
    currentClass: "",
    optimizedClass: "positive",
  },
  {
    name: "年化收益",
    current: "18.5%",
    optimized: "19.8%",
    improvement: 7.0,
    currentClass: "",
    optimizedClass: "positive",
  },
  {
    name: "波动率",
    current: "18.5%",
    optimized: "16.2%",
    improvement: -12.4,
    currentClass: "",
    optimizedClass: "positive",
  },
  {
    name: "最大回撤",
    current: "15.2%",
    optimized: "13.8%",
    improvement: -9.2,
    currentClass: "",
    optimizedClass: "positive",
  },
]);

const weightColumns: DataTableColumn<any>[] = [
  { key: "asset", title: "资产", width: 120 },
  {
    key: "current",
    title: "当前权重",
    width: 100,
    render: (row: WeightItem) => row.current + "%",
  },
  {
    key: "optimized",
    title: "优化权重",
    width: 100,
    render: (row: WeightItem) => row.optimized + "%",
  },
  {
    key: "change",
    title: "变化",
    width: 120,
    render: (row: WeightItem) =>
      h(
        "span",
        { class: row.change >= 0 ? "positive" : "negative" },
        (row.change >= 0 ? "+" : "") + row.change + "%",
      ),
  },
  {
    key: "actions",
    title: "操作",
    width: 80,
    render: (row: WeightItem) =>
      row.optimized !== row.current
        ? h(
            NButton,
            {
              type: "primary",
              text: true,
              onClick: () => applyWeight(row.asset),
            },
            { default: () => "应用" },
          )
        : null,
  },
];

const runOptimization = () => {
  optimizing.value = true;
  setTimeout(() => {
    optimizing.value = false;
    message.success("组合优化完成");
    weightComparison.value = weightComparison.value.map((item) => ({
      ...item,
      optimized: Math.max(0, item.optimized + (Math.random() - 0.5) * 2),
      change: 0,
    }));
    const total = weightComparison.value.reduce(
      (sum, item) => sum + item.optimized,
      0,
    );
    weightComparison.value.forEach((item) => {
      item.optimized = Number(((item.optimized * 100) / total).toFixed(1));
      item.change = Number((item.optimized - item.current).toFixed(1));
    });
  }, 2000);
};

const resetWeights = () => {
  weightComparison.value.forEach((item) => {
    item.optimized = item.current;
    item.change = 0;
  });
  message.info("已重置为当前权重");
};

const applyWeight = (asset: string) => {
  const item = weightComparison.value.find((w) => w.asset === asset);
  if (item) {
    item.current = item.optimized;
    item.change = 0;
    message.success(`已应用 ${asset} 的优化权重`);
  }
};

onMounted(() => {
  if (efficientFrontierChart.value) {
    const chart = echarts.init(efficientFrontierChart.value);
    chart.setOption({
      tooltip: {
        trigger: "item",
        formatter: (params: any) =>
          `${params.data[4]}<br/>风险: ${params.data[0].toFixed(1)}%<br/>收益: ${params.data[1].toFixed(1)}%`,
      },
      grid: { left: "3%", right: "7%", bottom: "3%", containLabel: true },
      xAxis: {
        type: "value",
        name: "风险 (%)",
        nameLocation: "middle",
        nameGap: 30,
        min: 10,
        max: 25,
      },
      yAxis: {
        type: "value",
        name: "收益 (%)",
        nameLocation: "middle",
        nameGap: 30,
        min: 8,
        max: 22,
      },
      series: [
        {
          name: "有效前沿",
          type: "line",
          data: [
            [12.5, 9.8, 1, 0, "最小风险"],
            [13.2, 12.5, 1, 1, ""],
            [14.8, 15.2, 1, 2, ""],
            [16.5, 17.8, 1, 3, ""],
            [18.2, 19.5, 1, 4, ""],
            [20.8, 20.2, 1, 5, "最大收益"],
          ],
          lineStyle: { color: "#5470c6", width: 3 },
          symbol: "circle",
          symbolSize: 8,
          itemStyle: { color: "#5470c6" },
        },
        {
          name: "当前组合",
          type: "scatter",
          data: [[18.5, 18.5, 2, 0, "当前组合"]],
          symbolSize: 20,
          itemStyle: { color: "#ee6666" },
        },
        {
          name: "优化组合",
          type: "scatter",
          data: [[16.2, 19.8, 3, 0, "优化组合"]],
          symbolSize: 20,
          itemStyle: { color: "#67c23a" },
        },
        {
          name: "可行组合",
          type: "scatter",
          data: [
            [15.2, 14.5],
            [17.8, 16.2],
            [14.5, 13.8],
            [19.2, 17.5],
            [16.8, 15.8],
          ],
          symbolSize: 6,
          itemStyle: { color: "#ccc" },
        },
      ],
    });
  }
});
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit-text {
  margin-left: 8px;
}

.optimization-controls {
  padding: 8px 0;
}

.weight-comparison {
  margin-top: 16px;
}

.weight-comparison h4 {
  margin: 0 0 16px 0;
  color: #606266;
}

.optimization-results {
  padding: 8px 0;
}

.metric-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}

.metric-name {
  font-size: 14px;
  color: #606266;
  margin-bottom: 12px;
}

.metric-values {
  display: flex;
  justify-content: space-around;
  margin-bottom: 8px;
}

.current-value,
.optimized-value {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.improvement {
  font-size: 14px;
  font-weight: 600;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>
