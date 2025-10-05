<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useTrade } from '@/composables/useTrade'
import { useStore } from '@/store'

interface Props {
  symbol?: string
  defaultVolume?: number
  showMarketOrder?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  defaultVolume: 100,
  showMarketOrder: true
})

const emit = defineEmits<{
  orderPlaced: [orderId: string]
  orderCancelled: [orderId: string]
}>()

const store = useStore()
const { quickOrder, marketOrder, limitOrder, estimateFees, isTrading } = useTrade()

const orderType = ref<'market' | 'limit'>('limit')
const direction = ref<'buy' | 'sell'>('buy')
const price = ref<number>(0)
const volume = ref<number>(props.defaultVolume)
const isSubmitting = ref(false)

// 当前价格
const currentPrice = computed(() => {
  if (props.symbol) {
    return store.getters['market/getCurrentPrice'](props.symbol)
  }
  return 0
})

// 可用资金
const availableCash = computed(() => {
  return store.getters['trade/getAvailableCash']
})

// 可用持仓
const availablePosition = computed(() => {
  if (props.symbol && direction.value === 'sell') {
    const position = store.getters['trade/getPosition'](props.symbol)
    return position ? position.available_volume : 0
  }
  return 0
})

// 估算费用
const estimatedFees = computed(() => {
  if (!price.value || !volume.value) return null

  return estimateFees(
    price.value || currentPrice.value,
    volume.value,
    direction.value
  )
})

// 总金额
const totalAmount = computed(() => {
  const p = orderType.value === 'market' ? currentPrice.value : price.value
  return p * volume.value
})

// 价格步长（根据股价）
const priceStep = computed(() => {
  const p = currentPrice.value
  if (p < 2) return 0.01
  if (p < 5) return 0.02
  if (p < 10) return 0.05
  if (p < 20) return 0.1
  if (p < 50) return 0.2
  if (p < 100) return 0.5
  return 1
})

// 数量步长
const volumeStep = computed(() => {
  return 100 // A股最小交易单位
})

// 价格变化
const changePrice = (delta: number) => {
  const step = priceStep.value
  price.value = Math.max(0, price.value + delta * step)
}

// 数量变化
const changeVolume = (delta: number) => {
  const step = volumeStep.value
  volume.value = Math.max(step, volume.value + delta * step)
}

// 设置百分比数量
const setVolumePercent = (percent: number) => {
  if (direction.value === 'buy') {
    const maxVolume = Math.floor(availableCash.value / (price.value || currentPrice.value))
    volume.value = Math.floor(maxVolume * percent / 100)
  } else {
    volume.value = Math.floor(availablePosition.value * percent / 100)
  }
  volume.value = Math.max(volumeStep.value, volume.value)
}

// 提交订单
const submitOrder = async () => {
  if (!props.symbol) {
    alert('请选择交易标的')
    return
  }

  if (isSubmitting.value) return

  isSubmitting.value = true

  try {
    let orderId: string

    if (orderType.value === 'market') {
      orderId = await marketOrder(props.symbol, direction.value, volume.value)
    } else {
      if (!price.value || price.value <= 0) {
        alert('请输入有效的价格')
        return
      }
      orderId = await limitOrder(props.symbol, direction.value, price.value, volume.value)
    }

    emit('orderPlaced', orderId)

    // 重置表单
    volume.value = props.defaultVolume
    if (orderType.value === 'limit') {
      price.value = currentPrice.value
    }

    // 显示成功消息
    store.dispatch('ui/showMessage', {
      type: 'success',
      message: `订单提交成功 (${orderId})`
    })

  } catch (error: any) {
    store.dispatch('ui/showMessage', {
      type: 'error',
      message: `下单失败: ${error.message}`
    })
  } finally {
    isSubmitting.value = false
  }
}

// 监听symbol变化，更新价格
watch(() => props.symbol, (newSymbol) => {
  if (newSymbol) {
    price.value = currentPrice.value
  }
}, { immediate: true })

// 监听方向变化，重置数量
watch(direction, () => {
  volume.value = props.defaultVolume
})
</script>

<template>
  <div class="quick-order-panel">
    <div class="panel-header">
      <h3>快速交易</h3>
      <span class="symbol" v-if="symbol">{{ symbol }}</span>
    </div>

    <div class="order-form">
      <!-- 订单类型选择 -->
      <div class="form-group">
        <label>订单类型</label>
        <div class="button-group">
          <button
            :class="{ active: orderType === 'limit' }"
            @click="orderType = 'limit'"
          >
            限价单
          </button>
          <button
            v-if="showMarketOrder"
            :class="{ active: orderType === 'market' }"
            @click="orderType = 'market'"
          >
            市价单
          </button>
        </div>
      </div>

      <!-- 买卖方向 -->
      <div class="form-group">
        <label>方向</label>
        <div class="button-group">
          <button
            :class="{ active: direction === 'buy', buy: true }"
            @click="direction = 'buy'"
          >
            买入
          </button>
          <button
            :class="{ active: direction === 'sell', sell: true }"
            @click="direction = 'sell'"
          >
            卖出
          </button>
        </div>
      </div>

      <!-- 价格输入 -->
      <div class="form-group" v-if="orderType === 'limit'">
        <label>价格</label>
        <div class="input-with-buttons">
          <input
            type="number"
            v-model.number="price"
            :step="priceStep"
            min="0"
          />
          <div class="adjust-buttons">
            <button @click="changePrice(1)">+</button>
            <button @click="changePrice(-1)">-</button>
          </div>
        </div>
      </div>

      <!-- 数量输入 -->
      <div class="form-group">
        <label>数量 (股)</label>
        <div class="input-with-buttons">
          <input
            type="number"
            v-model.number="volume"
            :step="volumeStep"
            min="0"
          />
          <div class="adjust-buttons">
            <button @click="changeVolume(1)">+</button>
            <button @click="changeVolume(-1)">-</button>
          </div>
        </div>
        <div class="quick-percent">
          <button @click="setVolumePercent(25)">25%</button>
          <button @click="setVolumePercent(50)">50%</button>
          <button @click="setVolumePercent(75)">75%</button>
          <button @click="setVolumePercent(100)">100%</button>
        </div>
      </div>

      <!-- 费用估算 -->
      <div class="fee-estimation" v-if="estimatedFees">
        <div class="fee-item">
          <span>佣金:</span>
          <span>¥{{ estimatedFees.commission.toFixed(2) }}</span>
        </div>
        <div class="fee-item" v-if="direction === 'sell'">
          <span>印花税:</span>
          <span>¥{{ estimatedFees.tax.toFixed(2) }}</span>
        </div>
        <div class="fee-item">
          <span>总费用:</span>
          <span>¥{{ estimatedFees.total.toFixed(2) }}</span>
        </div>
        <div class="fee-item total">
          <span>净金额:</span>
          <span>¥{{ estimatedFees.netAmount.toFixed(2) }}</span>
        </div>
      </div>

      <!-- 提交按钮 -->
      <button
        class="submit-button"
        :class="[direction, { loading: isSubmitting }]"
        @click="submitOrder"
        :disabled="isSubmitting || !symbol"
      >
        <span v-if="isSubmitting">提交中...</span>
        <span v-else>{{ direction === 'buy' ? '买入' : '卖出' }} {{ symbol || '' }}</span>
      </button>

      <!-- 资金信息 -->
      <div class="balance-info">
        <div v-if="direction === 'buy'">
          可用资金: ¥{{ availableCash.toFixed(2) }}
        </div>
        <div v-else>
          可用持仓: {{ availablePosition }} 股
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quick-order-panel {
  background: var(--bg-color-secondary);
  border-radius: 8px;
  padding: 16px;
  min-width: 300px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-color-primary);
}

.symbol {
  font-size: 14px;
  color: var(--text-color-secondary);
  font-weight: bold;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-color-secondary);
}

.button-group {
  display: flex;
  gap: 8px;
}

.button-group button {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color-secondary);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.button-group button.active {
  border-color: var(--primary-color);
  background: var(--primary-color);
  color: white;
}

.button-group button.buy.active {
  border-color: var(--success-color);
  background: var(--success-color);
}

.button-group button.sell.active {
  border-color: var(--danger-color);
  background: var(--danger-color);
}

.input-with-buttons {
  display: flex;
  gap: 8px;
}

.input-with-buttons input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color-primary);
  border-radius: 4px;
}

.adjust-buttons {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.adjust-buttons button {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color-secondary);
  border-radius: 2px;
  cursor: pointer;
  font-size: 12px;
}

.quick-percent {
  display: flex;
  gap: 4px;
  margin-top: 8px;
}

.quick-percent button {
  flex: 1;
  padding: 4px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color-secondary);
  border-radius: 2px;
  cursor: pointer;
  font-size: 12px;
}

.fee-estimation {
  margin: 16px 0;
  padding: 12px;
  background: var(--bg-color);
  border-radius: 4px;
  font-size: 12px;
}

.fee-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.fee-item.total {
  border-top: 1px solid var(--border-color);
  padding-top: 4px;
  font-weight: bold;
  color: var(--text-color-primary);
}

.submit-button {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
}

.submit-button.buy {
  background: var(--success-color);
  color: white;
}

.submit-button.buy:hover:not(:disabled) {
  background: var(--success-color-dark);
}

.submit-button.sell {
  background: var(--danger-color);
  color: white;
}

.submit-button.sell:hover:not(:disabled) {
  background: var(--danger-color-dark);
}

.submit-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.submit-button.loading {
  opacity: 0.8;
}

.balance-info {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
  font-size: 12px;
  color: var(--text-color-secondary);
  text-align: center;
}
</style>