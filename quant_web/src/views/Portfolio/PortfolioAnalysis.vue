<!-- views/Portfolio/PortfolioAnalysis.vue -->
<template>
  <div class="portfolio-analysis">
    <div class="page-header">
      <h1>组合分析</h1>
      <p>多维度分析投资组合表现和风险特征</p>
    </div>

    <el-row :gutter="16" class="portfolio-overview">
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>组合概况</span>
          </template>
          <div class="overview-stats">
            <div class="stat-item">
              <label>总资产</label>
              <span class="value">¥{{ formatNumber(portfolioStats.totalValue) }}</span>
            </div>
            <div class="stat-item">
              <label>今日收益</label>
              <span :class="['value', portfolioStats.dailyPnL >= 0 ? 'positive' : 'negative']">
                {{ portfolioStats.dailyPnL >= 0 ? '+' : '' }}{{ portfolioStats.dailyPnL.toFixed(2) }}%
              </span>
            </div>
            <div class="stat-item">
              <label>累计收益</label>
              <span :class="['value', portfolioStats.totalReturn >= 0 ? 'positive' : 'negative']">
                {{ portfolioStats.totalReturn >= 0 ? '+' : '' }}{{ portfolioStats.totalReturn.toFixed(2) }}%
              </span>
            </div>
            <div class="stat-item">
              <label>年化收益</label>
              <span class="value">{{ portfolioStats.annualReturn.toFixed(2) }}%</span>
            </div>
            <div class="stat-item">
              <label>最大回撤</label>
              <span class="value negative">{{ portfolioStats.maxDrawdown.toFixed(2) }}%</span>
            </div>
            <div class="stat-item">
              <label>夏普比率</label>
              <span class="value">{{ portfolioStats.sharpeRatio.toFixed(2) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card>
          <template #header>
            <span>净值曲线</span>
          </template>
          <div ref="equityChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="analysis-tabs">
      <el-col :span="24">
        <el-card>
          <template #header>
            <el-tabs v-model="activeTab">
              <el-tab-pane label="持仓分析" name="holdings" />
              <el-tab-pane label="风险分析" name="risk" />
              <el-tab-pane label="绩效归因" name="attribution" />
              <el-tab-pane label="组合优化" name="optimization" />
            </el-tabs>
          </template>

          <HoldingsAnalysis v-if="activeTab === 'holdings'" />
          <RiskAnalysis v-if="activeTab === 'risk'" />
          <AttributionAnalysis v-if="activeTab === 'attribution'" />
          <PortfolioOptimization v-if="activeTab === 'optimization'" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import HoldingsAnalysis from "@/components/portfolio/HoldingsAnalysis.vue";
import RiskAnalysis from "@/components/portfolio/RiskAnalysis.vue";
import AttributionAnalysis from "@/components/portfolio/AttributionAnalysis.vue";
import PortfolioOptimization from "@/components/portfolio/PortfolioOptimization.vue";

const activeTab = ref('holdings')
const equityChart = ref<HTMLElement>()

const portfolioStats = ref({
  totalValue: 1250000,
  dailyPnL: 1.25,
  totalReturn: 25.8,
  annualReturn: 18.5,
  maxDrawdown: -15.2,
  sharpeRatio: 1.8
})

const formatNumber = (num: number) => {
  return num.toLocaleString('zh-CN')
}

onMounted(() => {
  if (equityChart.value) {
    const chart = echarts.init(equityChart.value)
    const option = {
      tooltip: {
        trigger: 'axis'
      },
      legend: {
        data: ['组合净值', '基准指数']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          name: '组合净值',
          type: 'line',
          data: [1.0, 1.05, 1.12, 1.08, 1.15, 1.22, 1.18, 1.25, 1.30, 1.28, 1.32, 1.35],
          smooth: true,
          lineStyle: {
            width: 3
          }
        },
        {
          name: '基准指数',
          type: 'line',
          data: [1.0, 1.02, 1.08, 1.05, 1.10, 1.15, 1.12, 1.18, 1.22, 1.20, 1.25, 1.28],
          smooth: true,
          lineStyle: {
            width: 2,
            type: 'dashed'
          }
        }
      ]
    }
    chart.setOption(option)

    // 响应式调整
    window.addEventListener('resize', () => {
      chart.resize()
    })
  }
})
</script>

<style scoped>
.portfolio-analysis {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.portfolio-overview {
  margin-bottom: 24px;
}

.overview-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-item label {
  color: #606266;
  font-size: 14px;
}

.stat-item .value {
  font-weight: 600;
  font-size: 16px;
}

.stat-item .positive {
  color: #f56c6c;
}

.stat-item .negative {
  color: #67c23a;
}

.analysis-tabs {
  margin-top: 24px;
}
</style>