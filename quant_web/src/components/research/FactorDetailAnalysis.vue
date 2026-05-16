<template>
  <NSpin :show="loading">
    <div class="factor-detail-analysis">
      <!-- 因子基本信息 -->
      <NCard class="factor-info">
        <template #header>
          <div class="card-header"><span>因子基本信息</span></div>
        </template>

        <div class="desc-grid">
          <div class="desc-item">
            <span class="desc-label">因子名称</span>
            <NTag type="info">{{ factor.name }}</NTag>
          </div>
          <div class="desc-item">
            <span class="desc-label">因子代码</span>
            <NTag>{{ factor.code }}</NTag>
          </div>
          <div class="desc-item">
            <span class="desc-label">因子类别</span>
            <NTag :type="getCategoryTagType(factor.category)">{{
              getCategoryText(factor.category)
            }}</NTag>
          </div>
          <div class="desc-item">
            <span class="desc-label">状态</span>
            <NTag :type="factor.status === 'active' ? 'success' : 'error'">
              {{ factor.status === "active" ? "启用" : "停用" }}
            </NTag>
          </div>
          <div class="desc-item desc-full">
            <span class="desc-label">数据字段</span>
            <div class="data-fields">
              <NTag
                v-for="field in factor.dataFields"
                :key="field"
                size="small"
                type="info"
              >
                {{ field }}
              </NTag>
            </div>
          </div>
          <div class="desc-item desc-full">
            <span class="desc-label">因子描述</span>
            <span>{{ factor.description }}</span>
          </div>
          <div class="desc-item desc-full">
            <span class="desc-label">计算公式</span>
            <code class="formula-code">{{ factor.formula }}</code>
          </div>
        </div>
      </NCard>

      <!-- 测试结果概览 -->
      <NGrid :cols="24" :x-gap="20" class="results-overview">
        <NGridItem :span="6">
          <NCard>
            <div class="metric-card">
              <div class="metric-icon annual-return">
                <Icon icon="mdi:chart-line" />
              </div>
              <div class="metric-content">
                <div class="metric-value positive">
                  {{ formatPercent(testResults.annualReturn) }}
                </div>
                <div class="metric-label">年化收益</div>
              </div>
            </div>
          </NCard>
        </NGridItem>
        <NGridItem :span="6">
          <NCard>
            <div class="metric-card">
              <div class="metric-icon sharpe">
                <Icon icon="mdi:finance" />
              </div>
              <div class="metric-content">
                <div class="metric-value">
                  {{ testResults.sharpeRatio.toFixed(2) }}
                </div>
                <div class="metric-label">夏普比率</div>
              </div>
            </div>
          </NCard>
        </NGridItem>
        <NGridItem :span="6">
          <NCard>
            <div class="metric-card">
              <div class="metric-icon drawdown">
                <Icon icon="mdi:arrow-down" />
              </div>
              <div class="metric-content">
                <div class="metric-value negative">
                  {{ formatPercent(testResults.maxDrawdown) }}
                </div>
                <div class="metric-label">最大回撤</div>
              </div>
            </div>
          </NCard>
        </NGridItem>
        <NGridItem :span="6">
          <NCard>
            <div class="metric-card">
              <div class="metric-icon win-rate">
                <Icon icon="mdi:trophy" />
              </div>
              <div class="metric-content">
                <div class="metric-value">
                  {{ formatPercent(testResults.winRate) }}
                </div>
                <div class="metric-label">胜率</div>
              </div>
            </div>
          </NCard>
        </NGridItem>
      </NGrid>

      <!-- 详细分析图表 -->
      <NGrid :cols="24" :x-gap="20" class="analysis-charts">
        <NGridItem :span="12">
          <NCard>
            <template #header><span>分组收益分析</span></template>
            <div ref="groupReturnsChart" class="chart-container"></div>
          </NCard>
        </NGridItem>
        <NGridItem :span="12">
          <NCard>
            <template #header><span>IC序列分析</span></template>
            <div ref="icSeriesChart" class="chart-container"></div>
          </NCard>
        </NGridItem>
      </NGrid>

      <!-- 详细统计表格 -->
      <NCard class="detailed-stats">
        <template #header><span>详细统计指标</span></template>
        <NDataTable
          :data="statisticsData"
          :columns="statColumns"
          :bordered="false"
        />
      </NCard>
    </div>
  </NSpin>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from "vue";
import { NSpin, NCard, NTag, NGrid, NGridItem, NDataTable } from "naive-ui";
import type { DataTableColumn } from "naive-ui";
import { Icon } from "@iconify/vue";
import * as echarts from "echarts";

interface FactorData {
  name: string;
  code: string;
  category: string;
  status: string;
  dataFields: string[];
  description: string;
  formula: string;
}

interface TestResults {
  annualReturn: number;
  sharpeRatio: number;
  maxDrawdown: number;
  winRate: number;
  groupReturns: number[];
  icSeries: number[];
}

const props = defineProps<{
  factor: FactorData;
  testConfig?: Record<string, any>;
  testResults: TestResults;
}>();

const loading = ref(false);
const groupReturnsChart = ref<HTMLElement | null>(null);
const icSeriesChart = ref<HTMLElement | null>(null);

let groupReturnsChartInstance: echarts.ECharts | null = null;
let icSeriesChartInstance: echarts.ECharts | null = null;

const statisticsData = computed(() => [
  {
    metric: "年化收益",
    value: formatPercent(props.testResults.annualReturn),
    description: "策略年化收益率",
  },
  {
    metric: "年化波动率",
    value: formatPercent(0.182),
    description: "策略年化波动率",
  },
  {
    metric: "夏普比率",
    value: props.testResults.sharpeRatio.toFixed(3),
    description: "每单位风险获得的超额收益",
  },
  {
    metric: "最大回撤",
    value: formatPercent(props.testResults.maxDrawdown),
    description: "策略最大回撤幅度",
  },
  {
    metric: "卡尔玛比率",
    value: (
      props.testResults.annualReturn / Math.abs(props.testResults.maxDrawdown)
    ).toFixed(3),
    description: "年化收益与最大回撤的比率",
  },
  {
    metric: "胜率",
    value: formatPercent(props.testResults.winRate),
    description: "盈利周期占总周期比例",
  },
  { metric: "盈亏比", value: "1.85", description: "平均盈利与平均亏损的比率" },
  {
    metric: "IC均值",
    value: "0.045",
    description: "因子与下期收益的相关性均值",
  },
  { metric: "ICIR", value: "0.32", description: "IC均值与标准差的比率" },
  { metric: "换手率", value: "2.45", description: "策略月均换手率" },
]);

const statColumns: DataTableColumn<any>[] = [
  { key: "metric", title: "统计指标", width: 150 },
  { key: "value", title: "数值", width: 120 },
  { key: "description", title: "说明" },
];

const getCategoryTagType = (category: string) => {
  const map: Record<string, "success" | "warning" | "info" | "error"> = {
    value: "success",
    growth: "warning",
    quality: "info",
    momentum: "error",
    technical: "info",
  };
  return map[category] || "info";
};

const getCategoryText = (category: string) => {
  const map: Record<string, string> = {
    value: "价值因子",
    growth: "成长因子",
    quality: "质量因子",
    momentum: "动量因子",
    technical: "技术因子",
  };
  return map[category] || "其他";
};

const formatPercent = (value: number) => `${(value * 100).toFixed(2)}%`;

const initCharts = () => {
  if (!groupReturnsChart.value || !icSeriesChart.value) return;

  groupReturnsChartInstance = echarts.init(groupReturnsChart.value);
  groupReturnsChartInstance.setOption({
    tooltip: { trigger: "axis", formatter: "{b}: {c}%" },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: {
      type: "category",
      data: ["第1组", "第2组", "第3组", "第4组", "第5组"],
      axisLabel: { color: "#606266" },
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: "{value}%", color: "#606266" },
    },
    series: [
      {
        name: "分组收益",
        type: "bar",
        data: props.testResults.groupReturns.map((v) => (v * 100).toFixed(2)),
        itemStyle: {
          color: (params: any) => {
            const colors = [
              "#5470c6",
              "#91cc75",
              "#fac858",
              "#ee6666",
              "#73c0de",
            ];
            return colors[params.dataIndex] || "#5470c6";
          },
        },
        label: { show: true, position: "top", formatter: "{c}%" },
      },
    ],
  });

  icSeriesChartInstance = echarts.init(icSeriesChart.value);
  icSeriesChartInstance.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: "3%", right: "4%", bottom: "3%", containLabel: true },
    xAxis: {
      type: "category",
      data: Array.from(
        { length: props.testResults.icSeries.length },
        (_, i) => `周期${i + 1}`,
      ),
      axisLabel: { color: "#606266" },
    },
    yAxis: { type: "value", axisLabel: { color: "#606266" } },
    series: [
      {
        name: "IC序列",
        type: "line",
        data: props.testResults.icSeries,
        smooth: true,
        lineStyle: { color: "#67c23a", width: 2 },
        itemStyle: { color: "#67c23a" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(103, 194, 58, 0.3)" },
            { offset: 1, color: "rgba(103, 194, 58, 0.1)" },
          ]),
        },
      },
    ],
  });
};

onMounted(() => {
  setTimeout(() => initCharts(), 100);
});

onUnmounted(() => {
  groupReturnsChartInstance?.dispose();
  icSeriesChartInstance?.dispose();
});
</script>

<style lang="scss" scoped>
.factor-detail-analysis {
  .factor-info {
    margin-bottom: 20px;

    .data-fields {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .formula-code {
      background: #f5f7fa;
      padding: 8px 12px;
      border-radius: 4px;
      font-family: "Monaco", "Consolas", monospace;
      font-size: 12px;
      color: #e6a23c;
    }
  }

  .results-overview {
    margin-bottom: 20px;

    .metric-card {
      display: flex;
      align-items: center;
      gap: 16px;

      .metric-icon {
        width: 48px;
        height: 48px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;

        &.annual-return {
          background: #f0f9ff;
          color: #409eff;
        }
        &.sharpe {
          background: #f0f9e8;
          color: #67c23a;
        }
        &.drawdown {
          background: #fef0f0;
          color: #f56c6c;
        }
        &.win-rate {
          background: #fdf6ec;
          color: #e6a23c;
        }
      }

      .metric-content {
        .metric-value {
          font-size: 20px;
          font-weight: bold;
          margin-bottom: 4px;
          &.positive {
            color: #67c23a;
          }
          &.negative {
            color: #f56c6c;
          }
        }
        .metric-label {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }

  .analysis-charts {
    margin-bottom: 20px;
    .chart-container {
      height: 300px;
      width: 100%;
    }
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

/* descriptions grid replacement */
.desc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--n-border-color);
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
}

.desc-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--n-body-color);
  padding: 8px 12px;
  flex-wrap: wrap;
}

.desc-item .desc-label {
  font-size: 13px;
  color: var(--n-text-color-3);
  white-space: nowrap;
  min-width: 70px;
}

.desc-full {
  grid-column: 1 / -1;
}
</style>
