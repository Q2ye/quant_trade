// WebSocket封装
class WebSocketService {
  constructor() {
    this.socket = null
    this.subscribers = {}
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectInterval = 5000
    this.messageQueue = []
  }

  connect(url) {
    if (this.socket) {
      this.disconnect()
    }

    this.socket = new WebSocket(url)

    this.socket.onopen = () => {
      console.log('WebSocket connected')
      this.reconnectAttempts = 0

      // 重新订阅所有频道
      Object.keys(this.subscribers).forEach(channel => {
        this.sendSubscribe(channel)
      })

      // 发送积压的消息
      while (this.messageQueue.length > 0) {
        const message = this.messageQueue.shift()
        this.sendMessage(message)
      }
    }

    this.socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        this.notifySubscribers(message)
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
      }
    }

    this.socket.onclose = (event) => {
      console.log(`WebSocket closed: ${event.reason}`)
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++
          console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`)
          this.connect(url)
        }, this.reconnectInterval)
      }
    }

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.close()
      this.socket = null
    }
  }

  subscribe(channel, callback) {
    if (!this.subscribers[channel]) {
      this.subscribers[channel] = []
    }

    if (!this.subscribers[channel].includes(callback)) {
      this.subscribers[channel].push(callback)
    }

    // 如果已连接，立即发送订阅请求
    if (this.isConnected()) {
      this.sendSubscribe(channel)
    }
  }

  unsubscribe(channel, callback) {
    if (this.subscribers[channel]) {
      this.subscribers[channel] = this.subscribers[channel].filter(cb => cb !== callback)

      if (this.subscribers[channel].length === 0) {
        // 如果没有订阅者，发送取消订阅请求
        this.sendUnsubscribe(channel)
        delete this.subscribers[channel]
      }
    }
  }

  sendSubscribe(channel) {
    this.sendMessage({
      action: 'subscribe',
      channel
    })
  }

  sendUnsubscribe(channel) {
    this.sendMessage({
      action: 'unsubscribe',
      channel
    })
  }

  notifySubscribers(message) {
    const { channel, data } = message
    if (this.subscribers[channel]) {
      this.subscribers[channel].forEach(callback => callback(data))
    }
  }

  // 发送通用消息
  sendMessage(message) {
    if (this.isConnected()) {
      this.socket.send(JSON.stringify(message))
    } else {
      // 如果未连接，将消息加入队列
      this.messageQueue.push(message)
    }
  }

  isConnected() {
    return this.socket && this.socket.readyState === WebSocket.OPEN
  }

  // 订阅实时行情
  subscribeRealtime(symbols, callback) {
    const channel = `realtime:${symbols.join(',')}`
    this.subscribe(channel, callback)
    return channel
  }

  // 订阅篮子实时数据
  subscribeBasketRealtime(basketId, callback) {
    const channel = `basket:${basketId}`
    this.subscribe(channel, callback)
    return channel
  }

  // 订阅交易信号
  subscribeTradeSignals(callback) {
    const channel = 'trade:signals'
    this.subscribe(channel, callback)
    return channel
  }

  // 订阅系统通知
  subscribeSystemNotifications(callback) {
    const channel = 'system:notifications'
    this.subscribe(channel, callback)
    return channel
  }
}

// 创建单例实例
const webSocketService = new WebSocketService()

export default webSocketService