type WebSocketCallback = (data: any) => void;

class WebSocketService {
    private socket: WebSocket | null = null;
    private subscribers: Record<string, WebSocketCallback[]> = {};
    private reconnectAttempts: number = 0;
    private readonly maxReconnectAttempts: number = 5;
    private readonly reconnectInterval: number = 5000;
    private readonly messageQueue: any[] = [];

    connect(url: string): void {
        if (this.socket) {
            this.disconnect();
        }

        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;

            // 重新订阅所有频道
            Object.keys(this.subscribers).forEach(channel => {
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
                const message = JSON.parse(event.data);
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

    disconnect(): void {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }

    subscribe(channel: string, callback: WebSocketCallback): void {
        if (!this.subscribers[channel]) {
            this.subscribers[channel] = [];
        }

        if (!this.subscribers[channel].includes(callback)) {
            this.subscribers[channel].push(callback);
        }

        // 如果已连接，立即发送订阅请求
        if (this.isConnected()) {
            this.sendSubscribe(channel);
        }
    }

    unsubscribe(channel: string, callback: WebSocketCallback): void {
        if (this.subscribers[channel]) {
            this.subscribers[channel] = this.subscribers[channel].filter(cb => cb !== callback);

            if (this.subscribers[channel].length === 0) {
                // 如果没有订阅者，发送取消订阅请求
                this.sendUnsubscribe(channel);
                delete this.subscribers[channel];
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

    private notifySubscribers(message: { channel: string; data: any }): void {
        const {channel, data} = message;
        if (this.subscribers[channel]) {
            this.subscribers[channel].forEach(callback => callback(data));
        }
    }

    // 发送通用消息
    sendMessage(message: any): void {
        if (this.isConnected()) {
            this.socket?.send(JSON.stringify(message));
        } else {
            // 如果未连接，将消息加入队列
            this.messageQueue.push(message);
        }
    }

    isConnected(): boolean {
        return this.socket?.readyState === WebSocket.OPEN;
    }

    // 订阅实时行情
    subscribeRealtime(symbols: string[], callback: WebSocketCallback): string {
        const channel = `realtime:${symbols.join(',')}`;
        this.subscribe(channel, callback);
        return channel;
    }

    // 订阅篮子实时数据
    subscribeBasketRealtime(basketId: string, callback: WebSocketCallback): string {
        const channel = `basket:${basketId}`;
        this.subscribe(channel, callback);
        return channel;
    }

    // 订阅交易信号
    subscribeTradeSignals(callback: WebSocketCallback): string {
        const channel = 'trade:signals';
        this.subscribe(channel, callback);
        return channel;
    }

    // 订阅系统通知
    subscribeSystemNotifications(callback: WebSocketCallback): string {
        const channel = 'system:notifications';
        this.subscribe(channel, callback);
        return channel;
    }
}

// 创建单例实例
const webSocketService = new WebSocketService();

export default webSocketService;