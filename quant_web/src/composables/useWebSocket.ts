// WebSocket连接和消息管理
import { ref, onUnmounted, onMounted } from 'vue'
import { useStore } from '@/store'
import { TradeSignal, MarketData, OrderUpdate, RiskAlert } from '@/types/websocket'

interface WebSocketMessage {
  event: string
  data: any
  timestamp: number
}

export function useWebSocket() {
  const store = useStore()
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectInterval = ref(3000)

  // 消息处理器映射
  const messageHandlers = {
    'market_data': handleMarketData,
    'trade_signal': handleTradeSignal,
    'order_update': handleOrderUpdate,
    'risk_alert': handleRiskAlert,
    'system_status': handleSystemStatus
  }

  // 连接WebSocket
  const connect = () => {
    try {
      const token = store.state.user.token
      const wsUrl = `${import.meta.env.VITE_WS_URL}?token=${token}`

      ws.value = new WebSocket(wsUrl)

      ws.value.onopen = () => {
        console.log('WebSocket连接成功')
        isConnected.value = true
        reconnectAttempts.value = 0
        reconnectInterval.value = 3000
      }

      ws.value.onmessage = (event) => {
        const message: WebSocketMessage = JSON.parse(event.data)
        handleMessage(message)
      }

      ws.value.onclose = (event) => {
        console.log('WebSocket连接关闭', event)
        isConnected.value = false
        handleReconnect()
      }

      ws.value.onerror = (error) => {
        console.error('WebSocket错误', error)
        isConnected.value = false
      }

    } catch (error) {
      console.error('WebSocket连接失败', error)
      handleReconnect()
    }
  }

  // 处理消息
  const handleMessage = (message: WebSocketMessage) => {
    const handler = messageHandlers[message.event as keyof typeof messageHandlers]
    if (handler) {
      handler(message.data)
    } else {
      console.warn('未知的消息类型:', message.event)
    }
  }

  // 处理市场数据
  function handleMarketData(data: MarketData) {
    store.commit('market/UPDATE_REAL_TIME_DATA', data)

    // 更新相关图表
    if (store.state.trade.currentSymbol === data.ts_code) {
      store.commit('trade/UPDATE_CURRENT_PRICE', data)
    }
  }

  // 处理交易信号
  function handleTradeSignal(data: TradeSignal) {
    store.commit('strategy/ADD_SIGNAL', data)

    // 显示桌面通知
    if (Notification.permission === 'granted') {
      new Notification('交易信号提醒', {
        body: `${data.ts_code} ${data.signal_type}信号 - ${data.message}`,
        icon: '/favicon.ico'
      })
    }
  }

  // 处理订单更新
  function handleOrderUpdate(data: OrderUpdate) {
    store.commit('trade/UPDATE_ORDER_STATUS', data)
  }

  // 处理风险警报
  function handleRiskAlert(data: RiskAlert) {
    store.commit('risk/ADD_RISK_EVENT', data)

    // 显示风险警告
    store.dispatch('ui/showAlert', {
      type: 'warning',
      title: '风险警报',
      message: data.message,
      duration: 5000
    })
  }

  // 处理系统状态
  function handleSystemStatus(data: any) {
    store.commit('system/UPDATE_SYSTEM_STATUS', data)
  }

  // 重连逻辑
  const handleReconnect = () => {
    if (reconnectAttempts.value < maxReconnectAttempts) {
      reconnectAttempts.value++
      setTimeout(() => {
        console.log(`尝试重新连接... (${reconnectAttempts.value}/${maxReconnectAttempts})`)
        connect()
      }, reconnectInterval.value)

      // 指数退避
      reconnectInterval.value = Math.min(reconnectInterval.value * 1.5, 30000)
    }
  }

  // 发送消息
  const send = (event: string, data: any) => {
    if (ws.value && isConnected.value) {
      const message = {
        event,
        data,
        timestamp: Date.now()
      }
      ws.value.send(JSON.stringify(message))
    } else {
      console.error('WebSocket未连接，无法发送消息')
    }
  }

  // 订阅数据
  const subscribe = (channels: string[]) => {
    send('subscribe', { channels })
  }

  // 取消订阅
  const unsubscribe = (channels: string[]) => {
    send('unsubscribe', { channels })
  }

  // 关闭连接
  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    isConnected,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe
  }
}