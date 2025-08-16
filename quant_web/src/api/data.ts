import request from '@/utils/request'
import {handleResponse} from '@/utils/responseHandler'

export interface HistoricalDataPoint {
    date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface FinancialData {
    revenue: number;
    netIncome: number;
    eps: number;
    // ...其他财务数据
}

export interface StockBasicInfo {
    name: string;
    industry: string;
    marketCap: number;
    // ...其他基本信息
}

export interface MoneyFlowData {
    netInflow: number;
    mainNetInflow: number;
    // ...其他资金流数据
}

export interface StockListResult {
    stocks: Array<{
        symbol: string;
        name: string;
        price: number;
    }>;
    total: number;
    page: number;
}

export default {
    async getMarketData(): Promise<any> {
        return request.get('/data/market-overview')
            .then(handleResponse)
            .then((data: { marketData: any }) => data.marketData) // 添加类型注解
    },

    async getHistoricalData(symbol: string, period: string = '1y', frequency: string = '1d'): Promise<HistoricalDataPoint[]> {
        return request.get(`/data/historical/${symbol}`, {
            params: {period, frequency}
        })
            .then(handleResponse)
            .then((data: { historical: HistoricalDataPoint[] }) => data.historical) // 添加类型注解
    },

    async getFinancialData(symbol: string): Promise<FinancialData> {
        return request.get(`/data/financials/${symbol}`)
            .then(handleResponse)
            .then((data: { financials: FinancialData }) => data.financials) // 添加类型注解
    },

    async getETFData(): Promise<any[]> {
        return request.get('/data/etfs')
            .then(handleResponse)
            .then((data: { etfs: any[] }) => data.etfs) // 添加类型注解
    },

    async getStockBasic(symbol: string): Promise<StockBasicInfo> {
        return request.get(`/data/stocks/${symbol}/basic`)
            .then(handleResponse)
            .then((data: { basic: StockBasicInfo }) => data.basic) // 添加类型注解
    },

    async getMoneyFlow(symbol: string, period: string = '1m'): Promise<MoneyFlowData> {
        return request.get(`/data/stocks/${symbol}/moneyflow`, {
            params: {period}
        })
            .then(handleResponse)
            .then((data: { moneyflow: MoneyFlowData }) => data.moneyflow) // 添加类型注解
    },

    async getSectorData(): Promise<any[]> {
        return request.get('/data/sectors')
            .then(handleResponse)
            .then((data: { sectors: any[] }) => data.sectors) // 添加类型注解
    },

    async getIndexComponents(indexCode: string): Promise<string[]> {
        return request.get(`/data/indexes/${indexCode}/components`)
            .then(handleResponse)
            .then((data: { components: string[] }) => data.components) // 添加类型注解
    },

    async getStockList(exchange: string = '', industry: string = '', page: number = 1, pageSize: number = 50): Promise<StockListResult> {
        return request.get('/data/stocks', {
            params: {exchange, industry, page, pageSize}
        })
            .then(handleResponse)
            .then((data: { stocks: any[], total: number, page: number }) => ({
                stocks: data.stocks,
                total: data.total,
                page: data.page
            }))
    },

    async searchStocks(keyword: string): Promise<any[]> {
        return request.get('/data/stocks/search', {
            params: {keyword}
        })
            .then(handleResponse)
            .then((data: { results: any[] }) => data.results) // 添加类型注解
    },

    async getFactorData(factorName: string, period: string = '1y'): Promise<any> {
        return request.get(`/data/factors/${factorName}`, {
            params: {period}
        })
            .then(handleResponse)
            .then((data: { factorData: any }) => data.factorData) // 添加类型注解
    },

    subscribeRealtime(
        symbols: string[], // 添加类型注解
        callback: (symbol: string, quote: any) => void // 修正类型为函数
    ) {
        symbols.forEach(symbol => {
            setInterval(() => {
                const change = (Math.random() - 0.5) * 2
                const price = 100 + Math.random() * 50
                const quote = {
                    symbol,
                    price: parseFloat(price.toFixed(2)),
                    change: parseFloat(change.toFixed(2)),
                    changePercent: parseFloat((change / price * 100).toFixed(2)),
                    volume: Math.floor(Math.random() * 1000000),
                    time: new Date().toISOString()
                }
                callback(symbol, quote) // 现在可以正确调用
            }, 2000)
        })
    },

    async getDataSyncStatus(): Promise<string> {
        return request.get('/data/sync-status')
            .then(handleResponse)
            .then((data: { status: string }) => data.status) // 添加类型注解
    },

    async triggerDataSync(source: string): Promise<void> {
        return request.post('/data/sync', {source})
            .then(handleResponse)
    }
}