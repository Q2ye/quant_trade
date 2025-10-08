<!-- /components/portfolio/HoldingsAnalysis.vue -->
<!--持仓分析-->
<!--资产配置饼图-->
<!--行业分布柱状图-->
<!--持仓明细表格-->
<!--收益和涨跌幅展示-->
<template>
  <div class="holdings-analysis">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:chart-pie" width="20" />
              <span>资产配置</span>
            </div>
          </template>
          <div ref="assetAllocationChart" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <iconify-icon icon="mdi:finance" width="20" />
              <span>行业分布</span>
            </div>
          </template>
          <div ref="sectorChart" style="height: 300px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px;">
      <template #header>
        <div class="card-header">
          <iconify-icon icon="mdi:table" width="20" />
          <span>持仓明细</span>
        </div>
      </template>
      <el-table :data="holdings" stripe style="width: 100%">
        <el-table-column prop="name" label="资产名称" width="180">
          <template #default="scope">
            <div class="asset-info">
              <iconify-icon :icon="scope.row.icon" width="16" />
              <span style="margin-left: 8px;">{{ scope.row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="100" />
        <el-table-column prop="weight" label="权重" width="120">
          <template #default="scope">
            <el-progress
              :percentage="scope.row.weight"
              :show-text="false"
              :color="scope.row.weight > 10 ? '#67c23a' : '#409eff'"
            />
            <span style="margin-left: 8px;">{{ scope.row.weight }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="currentPrice" label="当前价格" width="120">
          <template #default="scope">
            ¥{{ scope.row.currentPrice }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="持仓数量" width="120" />
        <el-table-column prop="marketValue" label="市值" width="140">
          <template #default="scope">
            ¥{{ formatNumber(scope.row.marketValue) }}
          </template>
        </el-table-column>
        <el-table-column prop="dailyChange" label="日涨跌幅" width="120">
          <template #default="scope">
            <span :class="scope.row.dailyChange >= 0 ? 'positive' : 'negative'">
              {{ scope.row.dailyChange >= 0 ? '+' : '' }}{{ scope.row.dailyChange }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="totalReturn" label="累计收益" width="120">
          <template #default="scope">
            <span :class="scope.row.totalReturn >= 0 ? 'positive' : 'negative'">
              {{ scope.row.totalReturn >= 0 ? '+' : '' }}{{ scope.row.totalReturn }}%
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const assetAllocationChart = ref<HTMLElement>()
const sectorChart = ref<HTMLElement>()

const holdings = ref([
  {
    name: '贵州茅台',
    symbol: '600519',
    icon: 'mdi:glass-wine',
    weight: 15.5,
    currentPrice: 1650.80,
    quantity: 1000,
    marketValue: 1650800,
    dailyChange: 2.35,
    totalReturn: 45.6
  },
  {
    name: '宁德时代',
    symbol: '300750',
    icon: 'mdi:battery',
    weight: 12.2,
    currentPrice: 210.50,
    quantity: 5000,
    marketValue: 1052500,
    dailyChange: -1.25,
    totalReturn: 32.8
  },
  {
    name: '腾讯控股',
    symbol: '00700',
    icon: 'mdi:chat',
    weight: 10.8,
    currentPrice: 320.40,
    quantity: 3000,
    marketValue: 961200,
    dailyChange: 0.85,
    totalReturn: 28.4
  },
  {
    name: '招商银行',
    symbol: '600036',
    icon: 'mdi:bank',
    weight: 8.7,
    currentPrice: 35.20,
    quantity: 20000,
    marketValue: 704000,
    dailyChange: 0.56,
    totalReturn: 15.2
  },
  {
    name: '中国平安',
    symbol: '601318',
    icon: 'mdi:shield-account',
    weight: 7.3,
    currentPrice: 48.90,
    quantity: 12000,
    marketValue: 586800,
    dailyChange: -0.42,
    totalReturn: 8.7
  }
])

const formatNumber = (num: number) => {
  return num.toLocaleString('zh-CN')
}

onMounted(() => {
  // 资产配置饼图
  if (assetAllocationChart.value) {
    const chart = echarts.init(assetAllocationChart.value)
    const option = {
      tooltip: {
        trigger: 'item',
        formatter: '{a} <br/>{b}: {c} ({d}%)'
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: 'center'
      },
      series: [
        {
          name: '资产配置',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2
          },
          label: {
            show: false,
            position: 'center'
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 18,
              fontWeight: 'bold'
            }
          },
          labelLine: {
            show: false
          },
          data: [
            { value: 45, name: '股票' },
            { value: 25, name: '债券' },
            { value: 15, name: '现金' },
            { value: 10, name: '商品' },
            { value: 5, name: '其他' }
          ]
        }
      ]
    }
    chart.setOption(option)
  }

  // 行业分布柱状图
  if (sectorChart.value) {
    const chart = echarts.init(sectorChart.value)
    const option = {
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
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
        data: ['科技', '消费', '金融', '医药', '能源', '工业', '材料']
      },
      yAxis: {
        type: 'value',
        name: '权重 (%)'
      },
      series: [
        {
          name: '行业权重',
          type: 'bar',
          data: [25, 20, 18, 15, 8, 7, 7],
          itemStyle: {
            color: function(params: any) {
              const colorList = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452']
              return colorList[params.dataIndex]
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

.asset-info {
  display: flex;
  align-items: center;
}

.positive {
  color: #f56c6c;
}

.negative {
  color: #67c23a;
}
</style>