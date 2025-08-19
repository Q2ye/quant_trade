import request from '@/utils/request'
import {handleResponse} from '@/utils/responseHandler'

export interface AccountInfo {
    id: string;
    balance: number;
    equity: number;
    margin: number;
    // ...其他账户信息
}

export interface Position {
    symbol: string;
    quantity: number;
    avgPrice: number;
    // ...其他持仓信息
}

export interface Order {
    quantity: any;
    volume: any;
    price: number;
    orderType: string;
    accountId: any;
    id: string;
    symbol: string;
    type: 'market' | 'limit';
    // ...其他订单信息
}

export interface TradeRecord {
    accountId: any;
    id: string;
    symbol: string;
    price: number;
    quantity: number;
    // ...其他成交信息
    executedAt?: string;
}

export interface TradePerformance {
    totalProfit: number;
    winRate: number;
    // ...其他绩效指标
}

export default {
    async getAccountInfo(): Promise<AccountInfo[]> {
        return request.get('/trade/account')
            .then(handleResponse)
            .then((data: {
                account: any;
                accounts: AccountInfo[] }) => data.accounts) // 添加类型注解
    },

    async getPositions(): Promise<Position[]> {
        return request.get('/trade/positions')
            .then(handleResponse)
            .then((data: { positions: Position[] }) => data.positions) // 添加类型注解
    },

    async getOrderHistory(params: any = {}): Promise<Order[]> {
        return request.get('/trade/orders', {params})
            .then(handleResponse)
            .then((data: { orders: Order[] }) => data.orders) // 添加类型注解
    },

    async getTradeRecords(params: any = {}): Promise<TradeRecord[]> {
        return request.get('/trade/trades', {params})
            .then(handleResponse)
            .then((data: { trades: TradeRecord[] }) => data.trades) // 添加类型注解
    },

    async createOrder(orderData: any): Promise<Order> {
        return request.post('/trade/order', orderData)
            .then(handleResponse)
            .then((data: { order: Order }) => data.order) // 添加类型注解
    },

    async modifyOrder(orderId: string, updateData: any): Promise<Order> {
        return request.put(`/trade/order/${orderId}`, updateData)
            .then(handleResponse)
            .then((data: { updatedOrder: Order }) => data.updatedOrder) // 添加类型注解
    },

    async cancelOrder(orderId: string) {
        return request.delete(`/trade/order/${orderId}`)
            .then(handleResponse)
    },

    async basketTrade(basketId: string, tradeData: any): Promise<any> {
        return request.post(`/trade/basket/${basketId}`, tradeData)
            .then(handleResponse)
            .then((data: { results: any }) => data.results) // 添加类型注解
    },

    async getTradeSignals(): Promise<any[]> {
        return request.get('/trade/signals')
            .then(handleResponse)
            .then((data: { signals: any[] }) => data.signals) // 添加类型注解
    },

    async executeSignal(signalId: string): Promise<Order> {
        return request.post(`/trade/signal/${signalId}/execute`)
            .then(handleResponse)
            .then((data: { order: Order }) => data.order) // 添加类型注解
    },

    async ignoreSignal(signalId: string) {
        return request.post(`/trade/signal/${signalId}/ignore`)
            .then(handleResponse)
    },

    async getTradePerformance(): Promise<TradePerformance> {
        return request.get('/trade/performance')
            .then(handleResponse)
            .then((data: { performance: TradePerformance }) => data.performance) // 添加类型注解
    }
}