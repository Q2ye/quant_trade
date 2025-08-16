import request from '../utils/request'
import {handleResponse} from '@/utils/responseHandler'

interface Basket {
    id: string;
    name: string;
    description?: string;
    stocks: Array<{
        symbol: string;
        weight: number;
    }>;
}

interface StockData {
    symbol: string;
    weight: number;
}

interface PerformanceData {
    returns: number;
    volatility: number;
    sharpeRatio: number;
    // ...其他性能指标
}

interface RealtimeBasketData {
    value: number;
    change: number;
    changePercent: number;
    // ...其他实时数据
}

export default {
    async createBasket(basketData: Omit<Basket, 'id'>): Promise<Basket> {
        return request.post('/baskets', basketData)
            .then(handleResponse)
            .then((data: { basket: Basket }) => data.basket) // 添加类型注解
    },

    async getBaskets(): Promise<Basket[]> {
        return request.get('/baskets')
            .then(handleResponse)
            .then((data: { baskets: Basket[] }) => data.baskets) // 添加类型注解
    },

    async getBasket(id: string): Promise<Basket> {
        return request.get(`/baskets/${id}`)
            .then(handleResponse)
            .then((data: { basket: Basket }) => data.basket) // 添加类型注解
    },

    async updateBasket(id: string, updateData: Partial<Basket>): Promise<Basket> {
        return request.put(`/baskets/${id}`, updateData)
            .then(handleResponse)
            .then((data: { updatedBasket: Basket }) => data.updatedBasket) // 添加类型注解
    },

    async deleteBasket(id: string): Promise<void> {
        return request.delete(`/baskets/${id}`)
            .then(handleResponse)
    },

    async addStockToBasket(basketId: string, stockData: StockData): Promise<Basket> {
        return request.post(`/baskets/${basketId}/stocks`, stockData)
            .then(handleResponse)
            .then((data: { basket: Basket }) => data.basket) // 添加类型注解
    },

    async removeStockFromBasket(basketId: string, stockCode: string): Promise<Basket> {
        return request.delete(`/baskets/${basketId}/stocks/${stockCode}`)
            .then(handleResponse)
            .then((data: { basket: Basket }) => data.basket) // 添加类型注解
    },

    async adjustStockWeight(basketId: string, stockCode: string, newWeight: number): Promise<Basket> {
        return request.patch(`/baskets/${basketId}/stocks/${stockCode}`, {weight: newWeight})
            .then(handleResponse)
            .then((data: { basket: Basket }) => data.basket) // 添加类型注解
    },

    async getBasketPerformance(basketId: string, period: string = '1y'): Promise<PerformanceData> {
        return request.get(`/baskets/${basketId}/performance`, {params: {period}})
            .then(handleResponse)
            .then((data: { performance: PerformanceData }) => data.performance) // 添加类型注解
    },

    async importFromBacktest(backtestId: string, basketName: string): Promise<Basket> {
        return request.post(`/baskets/import/backtest/${backtestId}`, {name: basketName})
            .then(handleResponse)
            .then((data: { basket: Basket }) => data.basket) // 添加类型注解
    },

    async cloneBasket(basketId: string, newName: string): Promise<Basket> {
        return request.post(`/baskets/${basketId}/clone`, {newName})
            .then(handleResponse)
            .then((data: { newBasket: Basket }) => data.newBasket) // 添加类型注解
    },

    async getBasketRealtime(basketId: string): Promise<RealtimeBasketData> {
        return request.get(`/baskets/${basketId}/realtime`)
            .then(handleResponse)
            .then((data: { realtime: RealtimeBasketData }) => data.realtime) // 添加类型注解
    }
}