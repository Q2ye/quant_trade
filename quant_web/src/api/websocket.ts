import {
    WebSocketMessage,
    RealTimeQuoteMessage,
    StrategySignal,
    OrderStatusMessage,
    SystemStatusMessage,
    RiskAlertMessage, TradeRecord
} from '@/types/api'

type WebSocketCallback<T = any> = (data: T) => void;

/**
 * WebSocket服务类
 * 提供实时数据订阅、消息推送和连接管理功能
 */
class WebSocketService {
  private socket: WebSocket | null = null;
  private subscribers: Map<string, WebSocketCallback[]> = new Map();
  private reconnectAttempts: number = 0;
  private readonly maxReconnectAttempts: number = 5;
  private readonly reconnectInterval: number = 5000;
  private readonly messageQueue: any[] = [];
  private url: string = '';

  /**
   * 连接到WebSocket服务器
   * @param url WebSocket服务器地址
   */
  connect(url: string): void {
    if (this.socket) {
      this.disconnect();
    }

    this.url = url;
    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;

      // 重新订阅所有频道
      this.subscribers.forEach((_, channel) => {
        this.sendSubscribe(channel);
      });

      // 发送积压的消息
      while (this.messageQueue.length > 0) {
        const message = this.messageQueue.shift();
        this.sendMessage(message);
      }
    };

    this.socket.onmessage = (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.notifySubscribers(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    this.socket.onclose = (event: CloseEvent) => {
      console.log(`WebSocket closed: ${event.reason}`);
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        setTimeout(() => {
          this.reconnectAttempts++;
          console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`);
          this.connect(url);
        }, this.reconnectInterval);
      }
    };

    this.socket.onerror = (error: Event) => {
      console.error('WebSocket error:', error);
    };
  }

  /**
   * 断开WebSocket连接
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.subscribers.clear();
  }

  /**
   * 订阅频道
   * @param channel 频道名称
   * @param callback 回调函数
   */
  subscribe<T = any>(channel: string, callback: WebSocketCallback<T>): void {
    if (!this.subscribers.has(channel)) {
      this.subscribers.set(channel, []);
    }

    const channelSubscribers = this.subscribers.get(channel)!;
    if (!channelSubscribers.includes(callback)) {
      channelSubscribers.push(callback);
    }

    // 如果已连接，立即发送订阅请求
    if (this.isConnected()) {
      this.sendSubscribe(channel);
    }
  }

  /**
   * 取消订阅频道
   * @param channel 频道名称
   * @param callback 回调函数
   */
  unsubscribe<T = any>(channel: string, callback: WebSocketCallback<T>): void {
    const channelSubscribers = this.subscribers.get(channel);
    if (channelSubscribers) {
      const newSubscribers = channelSubscribers.filter(cb => cb !== callback);
      this.subscribers.set(channel, newSubscribers);

      if (newSubscribers.length === 0) {
        // 如果没有订阅者，发送取消订阅请求
        this.sendUnsubscribe(channel);
        this.subscribers.delete(channel);
      }
    }
  }

  private sendSubscribe(channel: string): void {
    this.sendMessage({
      action: 'subscribe',
      channel
    });
  }

  private sendUnsubscribe(channel: string): void {
    this.sendMessage({
      action: 'unsubscribe',
      channel
    });
  }

  private notifySubscribers(message: WebSocketMessage): void {
    const { channel, data } = message;
    const channelSubscribers = this.subscribers.get(channel);
    if (channelSubscribers) {
      channelSubscribers.forEach(callback => callback(data));
    }
  }

  /**
   * 发送消息
   * @param message 消息内容
   */
  sendMessage(message: any): void {
    if (this.isConnected()) {
      this.socket?.send(JSON.stringify(message));
    } else {
      // 如果未连接，将消息加入队列
      this.messageQueue.push(message);
    }
  }

  /**
   * 检查连接状态
   * @returns 是否已连接
   */
  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /**
   * 订阅实时行情
   * @param symbols 股票代码数组
   * @param callback 行情回调函数
   * @returns 频道ID
   */
  subscribeRealtime(symbols: string[], callback: WebSocketCallback<RealTimeQuoteMessage>): string {
    const channel = `realtime:${symbols.join(',')}`;
    this.subscribe(channel, callback);
    return channel;
  }

  /**
   * 订阅交易信号
   * @param callback 信号回调函数
   * @returns 频道ID
   */
  subscribeTradeSignals(callback: WebSocketCallback<StrategySignal>): string {
    const channel = 'trade:signals';
    this.subscribe(channel, callback);
    return channel;
  }

  /**
   * 订阅订单状态
   * @param callback 订单状态回调函数
   * @returns 频道ID
   */
  subscribeOrderStatus(callback: WebSocketCallback<OrderStatusMessage>): string {
    const channel = 'order:status';
    this.subscribe(channel, callback);
    return channel;
  }

  /**
   * 订阅成交回报
   * @param callback 成交回调函数
   * @returns 频道ID
   */
  subscribeTrades(callback: WebSocketCallback<TradeRecord>): string {
    const channel = 'trade:execution';
    this.subscribe(channel, callback);
    return channel;
  }

  /**
   * 订阅系统状态
   * @param callback 系统状态回调函数
   * @returns 频道ID
   */
  subscribeSystemStatus(callback: WebSocketCallback<SystemStatusMessage>): string {
    const channel = 'system:status';
    this.subscribe(channel, callback);
    return channel;
  }

  /**
   * 订阅风险预警
   * @param callback 风险预警回调函数
   * @returns 频道ID
   */
  subscribeRiskAlerts(callback: WebSocketCallback<RiskAlertMessage>): string {
    const channel = 'risk:alerts';
    this.subscribe(channel, callback);
    return channel;
  }

  /**
   * 获取连接统计信息
   * @returns 连接统计
   */
  getConnectionStats(): {
    isConnected: boolean;
    subscriberCount: number;
    channelCount: number;
    reconnectAttempts: number;
  } {
    return {
      isConnected: this.isConnected(),
      subscriberCount: Array.from(this.subscribers.values()).flat().length,
      channelCount: this.subscribers.size,
      reconnectAttempts: this.reconnectAttempts
    };
  }
}

// 创建单例实例
const webSocketService = new WebSocketService();

export default webSocketService;