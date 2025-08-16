import request from '@/utils/request'
import {handleResponse} from '@/utils/responseHandler'

export interface Strategy {
    id: string;
    name: string;
    status: 'active' | 'paused' | 'stopped';
    // ...其他策略属性
}

export interface StrategyListResult {
    strategies: Strategy[];
    total: number;
    page: number;
}

export interface StrategyPerformance {
    totalReturn: number;
    maxDrawdown: number;
    // ...其他绩效指标
}

export interface BacktestResult {
    id: string;
    performance: StrategyPerformance;
    // ...其他回测结果
}


export default {
    async getStrategyTemplates(): Promise<any[]> {
        return request.get('/strategy/templates')
            .then(handleResponse)
            .then((data: { templates: any[] }) => data.templates) // 添加类型注解
    },

    async getStrategyList(status: string = 'all', page: number = 1, pageSize: number = 20): Promise<StrategyListResult> {
        return request.get('/strategies', {
            params: {status, page, pageSize}
        })
            .then(handleResponse)
            .then((data: { strategies: Strategy[], total: number, page: number }) => ({
                strategies: data.strategies,
                total: data.total,
                page: data.page
            }))
    },

    async createStrategy(strategyData: any): Promise<Strategy> {
        return request.post('/strategies', strategyData)
            .then(handleResponse)
            .then((data: { newStrategy: Strategy }) => data.newStrategy) // 添加类型注解
    },

    async updateStrategy(id: string, strategyData: Partial<Strategy>): Promise<Strategy> {
        return request.put(`/strategies/${id}`, strategyData)
            .then(handleResponse)
            .then((data: { updatedStrategy: Strategy }) => data.updatedStrategy) // 添加类型注解
    },

    async deleteStrategy(id: string): Promise<void> {
        return request.delete(`/strategies/${id}`)
            .then(handleResponse)
    },

    async getStrategyDetails(id: string): Promise<Strategy> {
        return request.get(`/strategies/${id}`)
            .then(handleResponse)
            .then((data: { strategy: Strategy }) => data.strategy) // 添加类型注解
    },

    // 启动策略
    async startStrategy(id: string): Promise<Strategy> {
        return request.post(`/strategies/${id}/start`)
            .then(handleResponse)
            .then((data: { strategy: Strategy }) => data.strategy) // 返回更新后的策略对象
    },

    stopStrategy(id: string) {
        return request.post(`/strategies/${id}/stop`)
            .then(handleResponse)
    },

    async getStrategyLogs(id: string, limit: number = 100, level: string = 'all'): Promise<any[]> {
        return request.get(`/strategies/${id}/logs`, {
            params: {limit, level}
        })
            .then(handleResponse)
            .then((data: { logs: any[] }) => data.logs) // 添加类型注解
    },

    async getStrategyPerformance(id: string): Promise<StrategyPerformance> {
        return request.get(`/strategies/${id}/performance`)
            .then(handleResponse)
            .then((data: { performance: StrategyPerformance }) => data.performance) // 添加类型注解
    },

    async cloneStrategy(id: string, newName: string): Promise<Strategy> {
        return request.post(`/strategies/${id}/clone`, {newName})
            .then(handleResponse)
            .then((data: { newStrategy: Strategy }) => data.newStrategy) // 添加类型注解
    },

    async optimizeStrategyParams(params: any): Promise<any> {
        return request.post('/strategy/optimize', params)
            .then(handleResponse)
            .then((data: { optimizedParams: any }) => data.optimizedParams) // 添加类型注解
    },

    async compareStrategies(strategyIds: string[]): Promise<any> {
        return request.post('/strategy/compare', {strategyIds})
            .then(handleResponse)
            .then((data: { comparison: any }) => data.comparison) // 添加类型注解
    },

    async getBacktestConfig(id: string): Promise<any> {
        return request.get(`/strategies/${id}/backtest-config`)
            .then(handleResponse)
            .then((data: { config: any }) => data.config) // 添加类型注解
    },

    async runStrategyBacktest(id: string, config: any): Promise<BacktestResult> {
        return request.post(`/strategies/${id}/backtest`, config)
            .then(handleResponse)
            .then((data: { backtestResult: BacktestResult }) => data.backtestResult) // 添加类型注解
    },

    async getBacktestResult(backtestId: string): Promise<BacktestResult> {
        return request.get(`/backtest/${backtestId}`)
            .then(handleResponse)
            .then((data: { result: BacktestResult }) => data.result) // 添加类型注解
    },

    async getStrategyPositions(id: string): Promise<any[]> {
        return request.get(`/strategies/${id}/positions`)
            .then(handleResponse)
            .then((data: { positions: any[] }) => data.positions) // 添加类型注解
    },

    async getStrategySignals(id: string, limit: number = 100): Promise<any[]> {
        return request.get(`/strategies/${id}/signals`, {
            params: {limit}
        })
            .then(handleResponse)
            .then((data: { signals: any[] }) => data.signals) // 添加类型注解
    }
}