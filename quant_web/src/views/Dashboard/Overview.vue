<template>
  <div class="dashboard-overview">
    <!-- 顶部概览区 -->
    <el-row :gutter="20" class="overview-cards">
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-value">¥ {{ formatNumber(accountInfo.totalAsset) }}</div>
          <div class="metric-label">总资产</div>
          <div class="metric-change" :class="getChangeClass(accountInfo.dailyPnl)">
            {{ accountInfo.dailyPnl > 0 ? '+' : '' }}{{ formatNumber(accountInfo.dailyPnl) }} ({{ accountInfo.dailyReturn }}%)
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-value">¥ {{ formatNumber(accountInfo.cash) }}</div>
          <div class="metric-label">可用资金</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-value">{{ formatNumber(accountInfo.positionsCount) }}</div>
          <div class="metric-label">持仓品种</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="metric-card">
          <div class="metric-value">{{ formatNumber(accountInfo.activeStrategies) }}</div>
          <div class="metric-label">运行中策略</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 中部组件区 -->
    <el-row :gutter="20" class="dashboard-widgets">
      <el-col :span="16">
        <el-card class="widget-card">
          <template #header>
            <div class="widget-header">
              <span>组合绩效</span>
              <div class="widget-actions">
                <el-radio-group v-model="chartRange" size="small">
                  <el-radio-button label="1D">日</el-radio-button>
                  <el-radio-button label="1W">周</el-radio-button>
                  <el-radio-button label="1M">月</el-radio-button>
                  <el-radio-button label="1Y">年</el-radio-button>
                </el-radio-group>
              </div>
            </div>
          </template>
          <div id="equityChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="widget-card">
          <template #header>
            <span>实时信号</span>
          </template>
          <div class="signal-list">
            <div v-for="(signal, index) in recentSignals" :key="index" class="signal-item">
              <div class="signal-icon" :class="signal.direction">
                <i :class="signal.direction === 'buy' ? 'el-icon-top' : 'el-icon-bottom'"></i>
              </div>
              <div class="signal-content">
                <div class="signal-name">{{ signal.name }}</div>
                <div class="signal-symbol">{{ signal.symbol }}</div>
              </div>
              <div class="signal-price" :class="signal.direction">
                {{ signal.price }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 底部列表区 -->
    <el-row :gutter="20" class="dashboard-tables">
      <el-col :span="12">
        <el-card class="table-card">
          <template #header>
            <span>持仓列表</span>
          </template>
          <el-table :data="positions" style="width: 100%" height="250">
            <el-table-column prop="symbol" label="代码" width="80"></el-table-column>
            <el-table-column prop="name" label="名称" width="120"></el-table-column>
            <el-table-column prop="quantity" label="数量" width="80" align="right"></el-table-column>
            <el-table-column prop="price" label="当前价" width="100" align="right">
              <template #default="scope">
                {{ formatNumber(scope.row.price, 2) }}
              </template>
            </el-table-column>
            <el-table-column prop="pnl" label="盈亏" width="100" align="right">
              <template #default="scope">
                <span :class="scope.row.pnl >= 0 ? 'profit' : 'loss'">
                  {{ scope.row.pnl >= 0 ? '+' : '' }}{{ formatNumber(scope.row.pnl, 2) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="weight" label="权重" width="80" align="right">
              <template #default="scope">
                {{ formatNumber(scope.row.weight * 100, 1) }}%
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="table-card">
          <template #header>
            <span>今日成交</span>
          </template>
          <el-table :data="todayTrades" style="width: 100%" height="250">
            <el-table-column prop="time" label="时间" width="100"></el-table-column>
            <el-table-column prop="symbol" label="代码" width="80"></el-table-column>
            <el-table-column prop="direction" label="方向" width="60">
              <template #default="scope">
                <span :class="scope.row.direction">{{ scope.row.direction === 'buy' ? '买' : '卖' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="80" align="right">
              <template #default="scope">
                {{ formatNumber(scope.row.price, 2) }}
              </template>
            </el-table-column>
            <el-table-column prop="volume" label="数量" width="80" align="right">
              <template #default="scope">
                {{ formatNumber(scope.row.volume) }}
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="100" align="right">
              <template #default="scope">
                {{ formatNumber(scope.row.amount, 2) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { onMounted, ref, reactive } from 'vue'
import * as echarts from 'echarts'
import { getDashboardData, getPerformanceChart } from '@/api/dashboard'
import {formatNumber} from "@/utils/number";

export default {
  name: 'DashboardOverview',
  setup() {
    const chartRange = ref('1M')
    const accountInfo = reactive({
      totalAsset: 1256374.52,
      cash: 324560.12,
      dailyPnl: 12563.42,
      dailyReturn: 1.02,
      positionsCount: 8,
      activeStrategies: 3
    })

    const recentSignals = ref([
      { name: '双均线策略', symbol: '600036.SH', direction: 'buy', price: 42.56 },
      { name: '动量反转', symbol: '000858.SZ', direction: 'sell', price: 35.21 },
      { name: '布林带突破', symbol: '601318.SH', direction: 'buy', price: 48.93 }
    ])

    const positions = ref([
      { symbol: '600036.SH', name: '招商银行', quantity: 1000, price: 42.56, cost: 40.12, pnl: 2440, weight: 0.15 },
      { symbol: '000858.SZ', name: '五粮液', quantity: 500, price: 35.21, cost: 32.45, pnl: 1380, weight: 0.08 },
      { symbol: '601318.SH', name: '中国平安', quantity: 800, price: 48.93, cost: 47.21, pnl: 1376, weight: 0.18 }
    ])

    const todayTrades = ref([
      { time: '09:35:22', symbol: '600036.SH', direction: 'buy', price: 42.35, volume: 200, amount: 8470 },
      { time: '10:12:45', symbol: '000858.SZ', direction: 'sell', price: 35.40, volume: 100, amount: 3540 },
      { time: '13:28:17', symbol: '601318.SH', direction: 'buy', price: 48.75, volume: 300, amount: 14625 }
    ])

    let equityChart = null

    const initChart = async () => {
      const chartDom = document.getElementById('equityChart')
      if (!chartDom) return

      equityChart = echarts.init(chartDom)

      try {
        const response = await getPerformanceChart(chartRange.value)
        const option = {
          tooltip: {
            trigger: 'axis',
            axisPointer: {
              type: 'cross',
              label: {
                backgroundColor: '#6a7985'
              }
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
            boundaryGap: false,
            data: response.data.dates
          },
          yAxis: {
            type: 'value',
            axisLabel: {
              formatter: '{value}%'
            }
          },
          series: [
            {
              name: '策略收益',
              type: 'line',
              stack: '总量',
              areaStyle: {},
              emphasis: {
                focus: 'series'
              },
              data: response.data.strategyReturns
            },
            {
              name: '基准收益',
              type: 'line',
              stack: '总量',
              areaStyle: {},
              emphasis: {
                focus: 'series'
              },
              data: response.data.benchmarkReturns
            }
          ]
        }

        equityChart.setOption(option)
      } catch (error) {
        console.error('Failed to load chart events:', error)
      }
    }

    const loadDashboardData = async () => {
      try {
        const response = await getDashboardData()
        Object.assign(accountInfo, response.data.accountInfo)
        recentSignals.value = response.data.recentSignals
        positions.value = response.data.positions
        todayTrades.value = response.data.todayTrades
      } catch (error) {
        console.error('Failed to load dashboard events:', error)
      }
    }

    const getChangeClass = (value) => {
      return value >= 0 ? 'positive' : 'negative'
    }

    onMounted(() => {
      loadDashboardData()
      initChart()

      // 监听窗口变化，调整图表大小
      window.addEventListener('resize', () => {
        if (equityChart) {
          equityChart.resize()
        }
      })
    })

    return {
      chartRange,
      accountInfo,
      recentSignals,
      positions,
      todayTrades,
      formatNumber,
      getChangeClass
    }
  }
}
</script>

<style scoped lang="scss">
.dashboard-overview {
  padding: 0;

  .overview-cards {
    margin-bottom: 20px;

    .metric-card {
      text-align: center;

      .metric-value {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 8px;
      }

      .metric-label {
        color: #909399;
        margin-bottom: 8px;
      }

      .metric-change {
        font-size: 14px;

        &.positive {
          color: #f56c6c;
        }

        &.negative {
          color: #67c23a;
        }
      }
    }
  }

  .dashboard-widgets {
    margin-bottom: 20px;

    .widget-card {
      height: 300px;

      .widget-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .chart-container {
        height: 250px;
        width: 100%;
      }

      .signal-list {
        height: 250px;
        overflow-y: auto;

        .signal-item {
          display: flex;
          align-items: center;
          padding: 10px 0;
          border-bottom: 1px solid #ebeef5;

          &:last-child {
            border-bottom: none;
          }

          .signal-icon {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;

            &.buy {
              background-color: #fef0f0;
              color: #f56c6c;
            }

            &.sell {
              background-color: #f0f9eb;
              color: #67c23a;
            }
          }

          .signal-content {
            flex: 1;

            .signal-name {
              font-size: 14px;
              margin-bottom: 4px;
            }

            .signal-symbol {
              font-size: 12px;
              color: #909399;
            }
          }

          .signal-price {
            font-weight: bold;

            &.buy {
              color: #f56c6c;
            }

            &.sell {
              color: #67c23a;
            }
          }
        }
      }
    }
  }

  .dashboard-tables {
    .table-card {
      height: 320px;
    }
  }

  .profit {
    color: #f56c6c;
  }

  .loss {
    color: #67c23a;
  }

  .buy {
    color: #f56c6c;
  }

  .sell {
    color: #67c23a;
  }
}
</style>