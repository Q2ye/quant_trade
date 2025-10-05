<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useChart } from '@/composables/useChart'
import { useMarketStore } from '@/store/modules/market'
import { ElMessage } from 'element-plus'

const marketStore = useMarketStore()

// 交易配置
const tradeConfig = reactive({
  symbol: '000001.SZ',
  quantity: 100,
  priceType: 'limit', // limit, market
  limitPrice: 0,
  orderType: 'buy' // buy, sell
})

// 图表数据
const klineData = ref<any[]>([])
const currentPrice = ref(0)
const chartRef = ref<HTMLDivElement>()

// 初始化K线图表
const initKLineChart = () => {
  if (!chartRef.value) return

  // 模拟K线数据
  const data = generateKLineData()
  klineData.value = data
  currentPrice.value = data[data.length - 1].close

  const chart = useChart(chartRef.value, {
    title: { text: `${tradeConfig.symbol} K线图` },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'time' },
    yAxis: { type: 'value', scale: true },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0 }
    ],
    series: [{
      type: 'candlestick',
      data: data.map(item => [item.open, item.close, item.low, item.high]),
      itemStyle: {
        color: '#ec0000',
        color0: '#00da3c',
        borderColor: '#ec0000',
        borderColor0: '#00da3c'
      }
    }]
  })

  // 添加图表点击事件
  chart.on('click', (params: any) => {
    if (params.componentType === 'series' && params.seriesType === 'candlestick') {
      const data = params.data
      tradeConfig.limitPrice = data[3] // 使用最高价作为参考
    }
  })
}

// 生成模拟K线数据
const generateKLineData = () => {
  const data = []
  const basePrice = 100
  const baseTime = new Date('2023-01-01').getTime()

  for (let i = 0; i < 100; i++) {
    const open = basePrice + Math.random() * 10
    const close = open + (Math.random() - 0.5) * 5
    const high = Math.max(open, close) + Math.random() * 3
    const low = Math.min(open, close) - Math.random() * 3
    const time = baseTime + i * 24 * 60 * 60 * 1000

    data.push({ time, open, close, high, low })
  }

  return data
}

// 快速下单
const quickOrder = (direction: 'buy' | 'sell') => {
  tradeConfig.orderType = direction

  if (tradeConfig.priceType === 'market') {
    // 市价单，使用当前价格
    tradeConfig.limitPrice = currentPrice.value
  }

  submitOrder()
}

// 提交订单
const submitOrder = async () => {
  try {
    const order = {
      symbol: tradeConfig.symbol,
      quantity: tradeConfig.quantity,
      price: tradeConfig.priceType === 'market' ? undefined : tradeConfig.limitPrice,
      direction: tradeConfig.orderType,
      priceType: tradeConfig.priceType
    }

    // 调用交易API
    await marketStore.submitOrder(order)
    ElMessage.success('订单提交成功')
  } catch (error) {
    ElMessage.error('订单提交失败')
  }
}

// 价格变化监听
const priceChange = computed(() => {
  if (klineData.value.length < 2) return 0
  const current = klineData.value[klineData.value.length - 1].close
  const previous = klineData.value[klineData.value.length - 2].close
  return ((current - previous) / previous) * 100
})

// 图表标记交易点
const markTradePoints = () => {
  // 在图表上标记买卖点
}

onMounted(() => {
  initKLineChart()
})
</script>

<template>
  <div class="chart-trading">
    <div class="trading-header">
      <h3>图表联动交易</h3>
      <div class="symbol-info">
        <span class="symbol">{{ tradeConfig.symbol }}</span>
        <span class="price" :class="{ up: priceChange > 0, down: priceChange < 0 }">
          {{ currentPrice.toFixed(2) }}
          <span class="change">({{ priceChange.toFixed(2) }}%)</span>
        </span>
      </div>
    </div>

    <div class="trading-layout">
      <!-- K线图表 -->
      <div class="chart-section">
        <div ref="chartRef" class="kline-chart"></div>
      </div>

      <!-- 交易面板 -->
      <div class="trade-panel">
        <el-card class="trade-card">
          <template #header>
            <span>快速交易</span>
          </template>

          <!-- 交易方向选择 -->
          <div class="trade-direction">
            <el-radio-group v-model="tradeConfig.orderType">
              <el-radio-button label="buy">买入</el-radio-button>
              <el-radio-button label="sell">卖出</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 价格类型 -->
          <div class="price-type">
            <el-radio-group v-model="tradeConfig.priceType">
              <el-radio-button label="limit">限价</el-radio-button>
              <el-radio-button label="market">市价</el-radio-button>
            </el-radio-group>
          </div>

          <!-- 价格输入 -->
          <div class="price-input" v-if="tradeConfig.priceType === 'limit'">
            <el-input-number
              v-model="tradeConfig.limitPrice"
              :min="0"
              :step="0.01"
              controls-position="right"
              placeholder="委托价格"
            />
          </div>

          <!-- 数量输入 -->
          <div class="quantity-input">
            <el-input-number
              v-model="tradeConfig.quantity"
              :min="100"
              :step="100"
              controls-position="right"
              placeholder="委托数量"
            />
            <span class="unit">股</span>
          </div>

          <!-- 快速交易按钮 -->
          <div class="quick-buttons">
            <el-button
              type="success"
              size="large"
              @click="quickOrder('buy')"
              class="buy-button"
            >
              快速买入
            </el-button>
            <el-button
              type="danger"
              size="large"
              @click="quickOrder('sell')"
              class="sell-button"
            >
              快速卖出
            </el-button>
          </div>

          <!-- 订单信息 -->
          <div class="order-info">
            <div class="info-item">
              <span>预估金额:</span>
              <span class="amount">
                {{ (tradeConfig.quantity * (tradeConfig.limitPrice || currentPrice)).toFixed(2) }} 元
              </span>
            </div>
            <div class="info-item">
              <span>手续费:</span>
              <span class="fee">~5.00 元</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 技术指标面板 -->
    <div class="indicators-panel">
      <h4>技术指标</h4>
      <div class="indicators-grid">
        <div class="indicator-item">
          <span class="label">MA5</span>
          <span class="value">12.34</span>
        </div>
        <div class="indicator-item">
          <span class="label">MA10</span>
          <span class="value">12.56</span>
        </div>
        <div class="indicator-item">
          <span class="label">RSI</span>
          <span class="value">45.67</span>
        </div>
        <div class="indicator-item">
          <span class="label">MACD</span>
          <span class="value">0.12</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chart-trading {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
}

.trading-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color);
}

.symbol-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.symbol {
  font-weight: bold;
  font-size: 16px;
}

.price {
  font-size: 18px;
  font-weight: bold;
}

.price.up {
  color: #f56c6c;
}

.price.down {
  color: #67c23a;
}

.change {
  font-size: 14px;
  font-weight: normal;
}

.trading-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
  padding: 16px;
  min-height: 0;
}

.chart-section {
  background: var(--el-fill-color-light);
  border-radius: 6px;
  overflow: hidden;
}

.kline-chart {
  height: 100%;
  min-height: 500px;
}

.trade-panel {
  display: flex;
  flex-direction: column;
}

.trade-card {
  height: 100%;
}

.trade-direction, .price-type {
  margin-bottom: 16px;
  text-align: center;
}

.price-input, .quantity-input {
  margin-bottom: 16px;
}

.quantity-input {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unit {
  color: var(--el-text-color-secondary);
}

.quick-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 20px 0;
}

.buy-button, .sell-button {
  width: 100%;
  height: 40px;
}

.order-info {
  border-top: 1px solid var(--el-border-color);
  padding-top: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
}

.amount, .fee {
  font-weight: bold;
}

.indicators-panel {
  padding: 16px;
  border-top: 1px solid var(--el-border-color);
}

.indicators-panel h4 {
  margin: 0 0 12px 0;
}

.indicators-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.indicator-item {
  background: var(--el-fill-color-light);
  padding: 8px 12px;
  border-radius: 4px;
  text-align: center;
}

.indicator-item .label {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.indicator-item .value {
  display: block;
  font-size: 14px;
  font-weight: bold;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .trading-layout {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }

  .indicators-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>