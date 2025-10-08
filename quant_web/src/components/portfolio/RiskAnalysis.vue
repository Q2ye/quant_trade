<!-- components/portfolio/RiskAnalysis.vue -->
<!--风险分析-->
<!--风险指标概览-->
<!--回撤分析图表-->
<!--风险贡献分析-->
<!--风险收益散点图-->
<template>
  <div class="risk-analysis">
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-bell-curve" width="20" />
              <span>风险指标</span>
            </div>
          </template>
          <div class="risk-metrics">
            <div class="metric-item">
              <div class="metric-label">
                <iconify-icon icon="mdi:chart-line" width="16" />
                <span>年化波动率</span>
              </div>
              <div class="metric-value">{{ riskMetrics.volatility }}%</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                <iconify-icon icon="mdi:alert-octagon" width="16" />
                <span>VaR (95%)</span>
              </div>
              <div class="metric-value negative">-{{ riskMetrics.var }}%</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                <iconify-icon icon="mdi:trending-down" width="16" />
                <span>最大回撤</span>
              </div>
              <div class="metric-value negative">{{ riskMetrics.maxDrawdown }}%</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                <iconify-icon icon="mdi:chart-timeline" width="16" />
                <span>夏普比率</span>
              </div>
              <div class="metric-value positive">{{ riskMetrics.sharpeRatio }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                <iconify-icon icon="mdi:sigma" width="16" />
                <span>索提诺比率</span>
              </div>
              <div class="metric-value positive">{{ riskMetrics.sortinoRatio }}</div>
            </div>
            <div class="metric-item">
              <div class="metric-label">
                <iconify-icon icon="mdi:scale-balance" width="16" />
                <span>贝塔系数</span>
              </div>
              <div class="metric-value">{{ riskMetrics.beta }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-line" width="20" />
              <span>回撤分析</span>
            </div>
          </template>
          <div ref="drawdownChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-box" width="20" />
              <span>风险贡献</span>
            </div>
          </template>
          <div ref="riskContributionChart" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-scatter-plot" width="20" />
              <span>风险收益散点图</span>
            </div>
          </template>
          <div ref="riskReturnChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const drawdownChart = ref<HTMLElement>()
const riskContributionChart = ref<HTMLElement>()
const riskReturnChart = ref<HTMLElement>()

const riskMetrics = ref({
  volatility: 18.5,
  var: 2.8,
  maxDrawdown: 15.2,
  sharpeRatio: 1.8,
  sortinoRatio: 2.3,
  beta: 0.95
})

onMounted(() => {
  // 回撤分析图
  if (drawdownChart.value) {
    const chart = echarts.init(drawdownChart.value)
    const option = {
      tooltip: {
        trigger: 'axis'
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
        type: 'value',
        inverse: true,
        name: '回撤 (%)'
      },
      series: [
        {
          name: '组合回撤',
          type: 'line',
          data: [0, -2.5, -1.8, -8.2, -5.6, -3.1, -12.5, -9.8, -7.2, -15.2, -11.4, -8.7],
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(245,108,108,0.6)' },
              { offset: 1, color: 'rgba(245,108,108,0.1)' }
            ])
          },
          lineStyle: {
            color: '#f56c6c'
          }
        }
      ]
    }
    chart.setOption(option)
  }

  // 风险贡献饼图
  if (riskContributionChart.value) {
    const chart = echarts.init(riskContributionChart.value)
    const option = {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c}%'
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center'
      },
      series: [
        {
          name: '风险贡献',
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['40%', '50%'],
          data: [
            { value: 28, name: '贵州茅台' },
            { value: 22, name: '宁德时代' },
            { value: 18, name: '腾讯控股' },
            { value: 15, name: '招商银行' },
            { value: 12, name: '中国平安' },
            { value: 5, name: '其他' }
          ],
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          }
        }
      ]
    }
    chart.setOption(option)
  }

  // 风险收益散点图
  if (riskReturnChart.value) {
    const chart = echarts.init(riskReturnChart.value)
    const option = {
      tooltip: {
        trigger: 'item',
        formatter: function(params: any) {
          return `${params.data[4]}<br/>风险: ${params.data[0]}%<br/>收益: ${params.data[1]}%`
        }
      },
      grid: {
        left: '3%',
        right: '7%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'value',
        name: '风险 (%)',
        nameLocation: 'middle',
        nameGap: 30
      },
      yAxis: {
        type: 'value',
        name: '收益 (%)',
        nameLocation: 'middle',
        nameGap: 30
      },
      series: [
        {
          name: '资产',
          type: 'scatter',
          symbolSize: function(data: number[]) {
            return Math.sqrt(data[2]) * 5;
          },
          data: [
            [12, 8, 15, 0, '贵州茅台'],
            [25, 15, 12, 1, '宁德时代'],
            [18, 12, 10, 2, '腾讯控股'],
            [8, 6, 8, 3, '招商银行'],
            [10, 5, 7, 4, '中国平安'],
            [6, 4, 5, 5, '现金']
          ],
          itemStyle: {
            color: function(params: any) {
              const colorList = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272']
              return colorList[params.data[3]]
            }
          }
        }
      ]
    }
    chart.setOption(option)
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-metrics {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metric-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.metric-item:last-child {
  border-bottom: none;
}

.metric-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
  font-size: 14px;
}

.metric-value {
  font-weight: 600;
  font-size: 16px;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>