<!-- components/portfolio/AttributionAnalysis.vue -->
<!--绩效归因-->
<!--收益归因柱状图-->
<!--收益分解瀑布图-->
<!--归因因子明细表格-->
<template>
  <div class="attribution-analysis">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-bar" width="20" />
              <span>收益归因</span>
            </div>
          </template>
          <div ref="attributionChart" style="height: 350px;"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-waterfall" width="20" />
              <span>收益分解</span>
            </div>
          </template>
          <div ref="waterfallChart" style="height: 350px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:table" width="20" />
              <span>归因明细</span>
            </div>
          </template>
          <el-table :data="attributionDetails" stripe style="width: 100%">
            <el-table-column prop="factor" label="归因因子" width="180" />
            <el-table-column prop="contribution" label="贡献度 (%)" width="120">
              <template #default="scope">
                <span :class="scope.row.contribution >= 0 ? 'positive' : 'negative'">
                  {{ scope.row.contribution >= 0 ? '+' : '' }}{{ scope.row.contribution }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="allocation" label="配置效应 (%)" width="120">
              <template #default="scope">
                <span :class="scope.row.allocation >= 0 ? 'positive' : 'negative'">
                  {{ scope.row.allocation >= 0 ? '+' : '' }}{{ scope.row.allocation }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="selection" label="选择效应 (%)" width="120">
              <template #default="scope">
                <span :class="scope.row.selection >= 0 ? 'positive' : 'negative'">
                  {{ scope.row.selection >= 0 ? '+' : '' }}{{ scope.row.selection }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="interaction" label="交互效应 (%)" width="120">
              <template #default="scope">
                <span :class="scope.row.interaction >= 0 ? 'positive' : 'negative'">
                  {{ scope.row.interaction >= 0 ? '+' : '' }}{{ scope.row.interaction }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const attributionChart = ref<HTMLElement>()
const waterfallChart = ref<HTMLElement>()

const attributionDetails = ref([
  {
    factor: '股票选择',
    contribution: 8.2,
    allocation: 2.1,
    selection: 5.8,
    interaction: 0.3,
    description: '优秀的个股选择能力'
  },
  {
    factor: '行业配置',
    contribution: 4.5,
    allocation: 3.2,
    selection: 1.1,
    interaction: 0.2,
    description: '超配科技和消费行业'
  },
  {
    factor: '市场时机',
    contribution: 2.8,
    allocation: 1.5,
    selection: 0.9,
    interaction: 0.4,
    description: '适时的仓位调整'
  },
  {
    factor: '债券配置',
    contribution: 1.2,
    allocation: 0.8,
    selection: 0.3,
    interaction: 0.1,
    description: '稳定的债券收益'
  },
  {
    factor: '现金管理',
    contribution: 0.5,
    allocation: 0.3,
    selection: 0.1,
    interaction: 0.1,
    description: '流动性管理收益'
  },
  {
    factor: '其他',
    contribution: -1.2,
    allocation: -0.5,
    selection: -0.6,
    interaction: -0.1,
    description: '交易成本及其他'
  }
])

onMounted(() => {
  // 收益归因柱状图
  if (attributionChart.value) {
    const chart = echarts.init(attributionChart.value)
    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      legend: {
        data: ['配置效应', '选择效应', '交互效应']
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['股票选择', '行业配置', '市场时机', '债券配置', '现金管理', '其他']
      },
      yAxis: {
        type: 'value',
        name: '贡献度 (%)'
      },
      series: [
        {
          name: '配置效应',
          type: 'bar',
          stack: 'total',
          data: [2.1, 3.2, 1.5, 0.8, 0.3, -0.5],
          itemStyle: {
            color: '#5470c6'
          }
        },
        {
          name: '选择效应',
          type: 'bar',
          stack: 'total',
          data: [5.8, 1.1, 0.9, 0.3, 0.1, -0.6],
          itemStyle: {
            color: '#91cc75'
          }
        },
        {
          name: '交互效应',
          type: 'bar',
          stack: 'total',
          data: [0.3, 0.2, 0.4, 0.1, 0.1, -0.1],
          itemStyle: {
            color: '#fac858'
          }
        }
      ]
    }
    chart.setOption(option)
  }

  // 瀑布图
  if (waterfallChart.value) {
    const chart = echarts.init(waterfallChart.value)
    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        },
        formatter: function (params: any) {
          const tar = params[1]
          return tar.name + '<br/>' + tar.seriesName + ' : ' + tar.value
        }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: ['期初净值', '股票选择', '行业配置', '市场时机', '债券配置', '其他', '期末净值']
      },
      yAxis: {
        type: 'value'
      },
      series: [
        {
          name: '辅助',
          type: 'bar',
          stack: 'Total',
          itemStyle: {
            borderColor: 'transparent',
            color: 'transparent'
          },
          emphasis: {
            itemStyle: {
              borderColor: 'transparent',
              color: 'transparent'
            }
          },
          data: [1.0, 1.082, 1.127, 1.155, 1.167, 1.162, 0]
        },
        {
          name: '净值变化',
          type: 'bar',
          stack: 'Total',
          label: {
            show: true,
            position: 'inside'
          },
          data: [
            { value: 1.0, itemStyle: { color: '#73c0de' } },
            { value: 0.082, itemStyle: { color: '#5470c6' } },
            { value: 0.045, itemStyle: { color: '#5470c6' } },
            { value: 0.028, itemStyle: { color: '#5470c6' } },
            { value: 0.012, itemStyle: { color: '#5470c6' } },
            { value: -0.005, itemStyle: { color: '#ee6666' } },
            { value: 1.162, itemStyle: { color: '#73c0de' } }
          ]
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

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>