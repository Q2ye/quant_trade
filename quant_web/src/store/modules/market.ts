// quant_web/src/store/modules/market.ts
import { Module } from 'vuex'
import { ETFBasic, StockBasic, RealTimeQuote, IndexData } from "@/types/entities/data";
import { RootState } from "@/types";

export interface MarketState {
  // 股票基础信息
  stockBasic: StockBasic[]
  stockBasicMap: Map<string, StockBasic>

  // 实时行情数据
  realTimeData: Map<string, RealTimeQuote>
  realTimeSubscriptions: Set<string>

  // 指数数据
  indexData: {
    sh: IndexData | null
    sz: IndexData | null
    cyb: IndexData | null
    kcb: IndexData | null
  }

  // ETF数据
  etfBasic: ETFBasic[]
  etfRealTime: Map<string, RealTimeQuote>

  // 市场状态
  marketStatus: {
    isOpen: boolean
    currentTime: string
    nextOpenTime: string
  }

  // 板块数据
  sectorPerformance: Array<{
    name: string
    change: number
    stocks: string[]
  }>

  // 缓存控制
  lastUpdate: number
  isLoading: boolean
}

const state: MarketState = {
  stockBasic: [],
  stockBasicMap: new Map(),
  realTimeData: new Map(),
  realTimeSubscriptions: new Set(),
  indexData: {
    sh: null,
    sz: null,
    cyb: null,
    kcb: null
  },
  etfBasic: [],
  etfRealTime: new Map(),
  marketStatus: {
    isOpen: false,
    currentTime: '',
    nextOpenTime: ''
  },
  sectorPerformance: [],
  lastUpdate: 0,
  isLoading: false
}

const mutations = {
  // 设置股票基础信息
  SET_STOCK_BASIC(state: MarketState, stocks: StockBasic[]) {
    state.stockBasic = stocks
    state.stockBasicMap = new Map(stocks.map(stock => [stock.ts_code, stock]))
  },

  // 更新实时行情数据
  UPDATE_REAL_TIME_DATA(state: MarketState, data: RealTimeQuote) {
    state.realTimeData.set(data.ts_code, {
      ...state.realTimeData.get(data.ts_code),
      ...data,
      lastUpdate: Date.now()
    })
  },

  // 批量更新实时数据
  BATCH_UPDATE_REAL_TIME_DATA(state: MarketState, dataList: RealTimeQuote[]) {
    dataList.forEach(data => {
      state.realTimeData.set(data.ts_code, {
        ...state.realTimeData.get(data.ts_code),
        ...data,
        lastUpdate: Date.now()
      })
    })
  },

  // 添加实时数据订阅
  ADD_REAL_TIME_SUBSCRIPTION(state: MarketState, symbol: string) {
    state.realTimeSubscriptions.add(symbol)
  },

  // 移除实时数据订阅
  REMOVE_REAL_TIME_SUBSCRIPTION(state: MarketState, symbol: string) {
    state.realTimeSubscriptions.delete(symbol)
  },

  // 设置指数数据
  SET_INDEX_DATA(state: MarketState, payload: { index: string, data: IndexData }) {
    state.indexData[payload.index as keyof typeof state.indexData] = payload.data
  },

  // 设置ETF基础信息
  SET_ETF_BASIC(state: MarketState, etfs: ETFBasic[]) {
    state.etfBasic = etfs
  },

  // 更新ETF实时数据
  UPDATE_ETF_REAL_TIME(state: MarketState, data: RealTimeQuote) {
    state.etfRealTime.set(data.ts_code, data)
  },

  // 更新市场状态
  UPDATE_MARKET_STATUS(state: MarketState, status: MarketState['marketStatus']) {
    state.marketStatus = status
  },

  // 设置板块表现
  SET_SECTOR_PERFORMANCE(state: MarketState, sectors: MarketState['sectorPerformance']) {
    state.sectorPerformance = sectors
  },

  // 设置加载状态
  SET_LOADING(state: MarketState, loading: boolean) {
    state.isLoading = loading
  },

  // 清除过期的实时数据（超过5秒未更新）
  CLEAR_STALE_DATA(state: MarketState) {
    const now = Date.now()
    const staleThreshold = 5000 // 5秒

    // 清理股票实时数据
    for (const [symbol, data] of state.realTimeData.entries()) {
      if (now - (data.lastUpdate || 0) > staleThreshold) {
        state.realTimeData.delete(symbol)
      }
    }

    // 清理ETF实时数据
    for (const [symbol, data] of state.etfRealTime.entries()) {
      if (now - (data.lastUpdate || 0) > staleThreshold) {
        state.etfRealTime.delete(symbol)
      }
    }
  }
}

const actions = {
  // 加载股票基础信息
  async loadStockBasic({ commit, state }: any) {
    if (state.stockBasic.length > 0 && Date.now() - state.lastUpdate < 3600000) {
      return // 1小时内不重复加载
    }

    commit('SET_LOADING', true)
    try {
      const response = await fetch('/api/market/stock-basic')
      const data = await response.json()
      commit('SET_STOCK_BASIC', data)
      commit('SET_LOADING', false)
      state.lastUpdate = Date.now()
    } catch (error) {
      console.error('加载股票基础信息失败:', error)
      commit('SET_LOADING', false)
      throw error
    }
  },

  // 订阅实时数据
  async subscribeRealTime({ commit, rootState }: any, symbols: string[]) {
    if (!rootState.user.isAuthenticated) {
      throw new Error('请先登录')
    }

    try {
      // 通过WebSocket订阅
      if (rootState.websocket.isConnected) {
        rootState.websocket.send('subscribe', { channels: symbols.map(s => `quote_${s}`) })
      }

      symbols.forEach(symbol => {
        commit('ADD_REAL_TIME_SUBSCRIPTION', symbol)
      })
    } catch (error) {
      console.error('订阅实时数据失败:', error)
      throw error
    }
  },

  // 取消订阅实时数据
  async unsubscribeRealTime({ commit, rootState }: any, symbols: string[]) {
    try {
      // 通过WebSocket取消订阅
      if (rootState.websocket.isConnected) {
        rootState.websocket.send('unsubscribe', { channels: symbols.map(s => `quote_${s}`) })
      }

      symbols.forEach(symbol => {
        commit('REMOVE_REAL_TIME_SUBSCRIPTION', symbol)
      })
    } catch (error) {
      console.error('取消订阅实时数据失败:', error)
      throw error
    }
  },

  // 加载指数数据
  async loadIndexData({ commit }: any) {
    try {
      const indices = ['sh', 'sz', 'cyb', 'kcb']
      const promises = indices.map(async index => {
        const response = await fetch(`/api/market/index/${index}`)
        const data = await response.json()
        commit('SET_INDEX_DATA', { index, data })
      })

      await Promise.all(promises)
    } catch (error) {
      console.error('加载指数数据失败:', error)
      throw error
    }
  },

  // 搜索股票
  async searchStocks({ state, dispatch }: any, keyword: string) {
    if (!keyword.trim()) {
      return []
    }

    // 如果基础数据未加载，先加载
    if (state.stockBasic.length === 0) {
      await dispatch('loadStockBasic')
    }

    const lowerKeyword = keyword.toLowerCase()
    return state.stockBasic.filter((stock: StockBasic) => {
      return (
        stock.ts_code.toLowerCase().includes(lowerKeyword) ||
        stock.name.toLowerCase().includes(lowerKeyword) ||
        stock.symbol.toLowerCase().includes(lowerKeyword)
      )
    }).slice(0, 50) // 限制返回数量
  },

  // 获取股票详情
  async getStockDetail({ state, dispatch }: any, symbol: string) {
    // 确保基础数据已加载
    if (state.stockBasic.length === 0) {
      await dispatch('loadStockBasic')
    }

    const stock = state.stockBasicMap.get(symbol)
    if (!stock) {
      throw new Error(`未找到股票: ${symbol}`)
    }

    try {
      // 加载详细信息
      const [dailyData, basicData, companyInfo] = await Promise.all([
        fetch(`/api/market/daily/${symbol}`).then(r => r.json()),
        fetch(`/api/market/daily-basic/${symbol}`).then(r => r.json()),
        fetch(`/api/market/company/${symbol}`).then(r => r.json())
      ])

      return {
        ...stock,
        dailyData,
        basicData,
        companyInfo
      }
    } catch (error) {
      console.error('获取股票详情失败:', error)
      throw error
    }
  },

  // 定期清理过期数据
  startDataCleanup({ commit }: any) {
    setInterval(() => {
      commit('CLEAR_STALE_DATA')
    }, 10000) // 每10秒清理一次
  }
}

const getters = {
  // 获取股票基础信息
  getStockBasic: (state: MarketState) => state.stockBasic,

  // 获取单个股票信息
  getStockBySymbol: (state: MarketState) => (symbol: string) => {
    return state.stockBasicMap.get(symbol)
  },

  // 获取实时行情
  getRealTimeQuote: (state: MarketState) => (symbol: string) => {
    return state.realTimeData.get(symbol)
  },

  // 获取当前价格
  getCurrentPrice: (state: MarketState) => (symbol: string) => {
    const quote = state.realTimeData.get(symbol)
    return quote ? quote.current : null
  },

  // 获取涨跌幅
  getChangePercent: (state: MarketState) => (symbol: string) => {
    const quote = state.realTimeData.get(symbol)
    return quote ? quote.changePercent : null
  },

  // 获取指数数据
  getIndexData: (state: MarketState) => (index: string) => {
    return state.indexData[index as keyof typeof state.indexData]
  },

  // 获取市场状态
  isMarketOpen: (state: MarketState) => state.marketStatus.isOpen,

  // 获取热门股票（按成交量）
  getHotStocks: (state: MarketState) => (limit: number = 10) => {
    const quotes = Array.from(state.realTimeData.values())
    return quotes
      .filter(quote => quote.volume > 0)
      .sort((a, b) => b.volume - a.volume)
      .slice(0, limit)
      .map(quote => ({
        ...quote,
        stock: state.stockBasicMap.get(quote.ts_code)
      }))
  },

  // 获取涨跌幅排行榜
  getTopGainers: (state: MarketState) => (limit: number = 10) => {
    const quotes = Array.from(state.realTimeData.values())
    return quotes
      .filter(quote => quote.changePercent > 0)
      .sort((a, b) => b.changePercent - a.changePercent)
      .slice(0, limit)
      .map(quote => ({
        ...quote,
        stock: state.stockBasicMap.get(quote.ts_code)
      }))
  },

  getTopLosers: (state: MarketState) => (limit: number = 10) => {
    const quotes = Array.from(state.realTimeData.values())
    return quotes
      .filter(quote => quote.changePercent < 0)
      .sort((a, b) => a.changePercent - b.changePercent)
      .slice(0, limit)
      .map(quote => ({
        ...quote,
        stock: state.stockBasicMap.get(quote.ts_code)
      }))
  },

  // 获取板块表现
  getSectorPerformance: (state: MarketState) => state.sectorPerformance,

  // 检查数据是否过期
  isDataStale: (state: MarketState) => (symbol: string) => {
    const quote = state.realTimeData.get(symbol)
    if (!quote || !quote.lastUpdate) return true
    return Date.now() - quote.lastUpdate > 10000 // 10秒视为过期
  }
}

const marketModule: Module<MarketState, RootState> = {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
}

export default marketModule