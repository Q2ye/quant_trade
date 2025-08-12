// 数据相关API
// 数据相关API
import request from '../utils/request'
import { handleResponse } from '../utils/responseHandler'

export default {
  // 获取市场概览数据
  getMarketData() {
    return request.get('/data/market-overview')
      .then(handleResponse)
      .then(data => data.marketData)
  },

  // 获取历史数据
  getHistoricalData(symbol, period = '1y', frequency = '1d') {
    return request.get(`/data/historical/${symbol}`, {
      params: { period, frequency }
    })
      .then(handleResponse)
      .then(data => data.historical)
  },

  // 获取财务数据
  getFinancialData(symbol) {
    return request.get(`/data/financials/${symbol}`)
      .then(handleResponse)
      .then(data => data.financials)
  },

  // 获取ETF数据
  getETFData() {
    return request.get('/data/etfs')
      .then(handleResponse)
      .then(data => data.etfs)
  },

  // 获取股票基本信息
  getStockBasic(symbol) {
    return request.get(`/data/stocks/${symbol}/basic`)
      .then(handleResponse)
      .then(data => data.basic)
  },

  // 获取股票资金流向
  getMoneyFlow(symbol, period = '1m') {
    return request.get(`/data/stocks/${symbol}/moneyflow`, {
      params: { period }
    })
      .then(handleResponse)
      .then(data => data.moneyflow)
  },

  // 获取板块数据
  getSectorData() {
    return request.get('/data/sectors')
      .then(handleResponse)
      .then(data => data.sectors)
  },

  // 获取指数成分股
  getIndexComponents(indexCode) {
    return request.get(`/data/indexes/${indexCode}/components`)
      .then(handleResponse)
      .then(data => data.components)
  },

  // 获取股票列表
  getStockList(exchange = '', industry = '', page = 1, pageSize = 50) {
    return request.get('/data/stocks', {
      params: { exchange, industry, page, pageSize }
    })
      .then(handleResponse)
      .then(data => ({
        stocks: data.stocks,
        total: data.total,
        page: data.page
      }))
  },

  // 搜索股票
  searchStocks(keyword) {
    return request.get('/data/stocks/search', {
      params: { keyword }
    })
      .then(handleResponse)
      .then(data => data.results)
  },

  // 获取因子数据
  getFactorData(factorName, period = '1y') {
    return request.get(`/data/factors/${factorName}`, {
      params: { period }
    })
      .then(handleResponse)
      .then(data => data.factorData)
  },

  // 订阅实时数据（模拟）
  subscribeRealtime(symbols, callback) {
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
        callback(symbol, quote)
      }, 2000)
    })
  },

  // 获取数据同步状态
  getDataSyncStatus() {
    return request.get('/data/sync-status')
      .then(handleResponse)
      .then(data => data.status)
  },

  // 手动触发数据同步
  triggerDataSync(source) {
    return request.post('/data/sync', { source })
      .then(handleResponse)
  }
}