<template>
  <div class="trading-dashboard">
    <div class="dashboard-header">
      <h2>交易驾驶舱</h2>
      <div class="account-info">
        <span>总资产: {{ formatCurrency(account.totalAsset) }}</span>
        <span>可用资金: {{ formatCurrency(account.availableCash) }}</span>
        <span>持仓市值: {{ formatCurrency(account.marketValue) }}</span>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- 左侧：订单入口 -->
      <el-col :span="8">
        <el-card class="order-panel">
          <div slot="header">
            <span>快速下单</span>
          </div>
          <OrderForm
              :symbol="selectedSymbol"
              @order-submit="handleOrderSubmit"
          />
        </el-card>

        <el-card class="order-list-panel">
          <div slot="header">
            <span>当前委托</span>
            <el-button size="mini" @click="refreshOrders">刷新</el-button>
          </div>
          <OrderList :orders="pendingOrders" @cancel-order="handleCancelOrder"/>
        </el-card>
      </el-col>

      <!-- 中部：图表联动 -->
      <el-col :span="10">
        <el-card class="chart-panel">
          <div slot="header">
            <span>K线图表 - {{ selectedSymbol || '请选择标的' }}</span>
            <el-select
                v-model="chartPeriod"
                size="mini"
                style="width: 100px; margin-left: 10px"
            >
              <el-option label="1分" value="1min"></el-option>
              <el-option label="5分" value="5min"></el-option>
              <el-option label="日线" value="daily"></el-option>
            </el-select>
          </div>
          <KLineChart
              :symbol="selectedSymbol"
              :period="chartPeriod"
              @chart-click="handleChartClick"
              @data-loaded="handleKLineDataLoaded"
          />
        </el-card>
      </el-col>

      <!-- 右侧：实时信息 -->
      <el-col :span="6">
        <el-card class="market-depth-panel">
          <div slot="header">
            <span>深度行情</span>
          </div>
          <MarketDepth :symbol="selectedSymbol"/>
        </el-card>

        <el-card class="position-panel">
          <div slot="header">
            <span>持仓列表</span>
          </div>
          <PositionList
              :positions="positions"
              @select-symbol="setSelectedSymbol"
          />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import OrderForm from '@/components/trade/OrderForm.vue'
import OrderList from '@/components/trade/OrderList.vue'
import KLineChart from '@/components/charts/KLineChart.vue'
import MarketDepth from '@/components/market/MarketDepth.vue'
import PositionList from '@/components/trade/PositionList.vue'

export default {
  name: "TradingDashboard",
  components: {
    OrderForm,
    OrderList,
    KLineChart,
    MarketDepth,
    PositionList
  },
  data() {
    return {
      selectedSymbol: '600519.SH',
      chartPeriod: '5min',
      account: {
        totalAsset: 1000000,
        availableCash: 350000,
        marketValue: 650000
      },
      pendingOrders: [
        {
          id: 'O1001',
          symbol: '600519.SH',
          direction: 'buy',
          type: 'limit',
          price: 1800,
          volume: 100,
          status: 'submitted'
        },
        {
          id: 'O1002',
          symbol: '000858.SZ',
          direction: 'sell',
          type: 'market',
          price: null,
          volume: 200,
          status: 'submitted'
        }
      ],
      positions: [
        {symbol: '600519.SH', name: '贵州茅台', volume: 100, costPrice: 1750, currentPrice: 1850},
        {symbol: '000858.SZ', name: '五粮液', volume: 200, costPrice: 150, currentPrice: 155}
      ]
    }
  },
  methods: {
    formatCurrency(value) {
      return `¥${value.toLocaleString('zh-CN')}`;
    },
    handleOrderSubmit(order) {
      console.log('提交订单:', order);
      // 调用API提交订单
      this.pendingOrders.push({
        id: `O${Date.now()}`,
        ...order,
        status: 'submitted'
      });
    },
    handleCancelOrder(orderId) {
      this.pendingOrders = this.pendingOrders.filter(o => o.id !== orderId);
      // 调用API撤单
    },
    refreshOrders() {
      // 调用API刷新订单列表
      console.log('刷新订单列表');
    },
    setSelectedSymbol(symbol) {
      this.selectedSymbol = symbol;
    },
    handleChartClick(data) {
      // 图表点击事件，可用于画线下单
      console.log('图表点击:', data);
    },
    handleKLineDataLoaded(data) {
      console.log('K线数据加载完成:', data);
      // 可以在这里处理加载的数据
    },
  }
}
</script>

<style scoped>
.trading-dashboard {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: 100vh;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 10px 20px;
  background: white;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.account-info {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #606266;
}

.order-panel,
.order-list-panel,
.chart-panel,
.market-depth-panel,
.position-panel {
  margin-bottom: 20px;
}

.chart-panel {
  height: 500px;
  min-height: 500px;
}

.market-depth-panel {
  height: 300px;
}

.position-panel {
  height: 300px;
}

.chart-panel >>> .kline-chart {
  height: 100% !important;
  min-height: 450px !important;
}
</style>