// 篮子相关API
import request from '../utils/request'
import { handleResponse } from '../utils/responseHandler'

export default {
  // 创建新篮子
  createBasket(basketData) {
    return request.post('/baskets', basketData)
      .then(handleResponse)
      .then(data => data.basket)
  },

  // 获取用户所有篮子
  getBaskets() {
    return request.get('/baskets')
      .then(handleResponse)
      .then(data => data.baskets)
  },

  // 获取篮子详情
  getBasket(id) {
    return request.get(`/baskets/${id}`)
      .then(handleResponse)
      .then(data => data.basket)
  },

  // 更新篮子信息
  updateBasket(id, updateData) {
    return request.put(`/baskets/${id}`, updateData)
      .then(handleResponse)
      .then(data => data.updatedBasket)
  },

  // 删除篮子
  deleteBasket(id) {
    return request.delete(`/baskets/${id}`)
      .then(handleResponse)
  },

  // 向篮子添加股票
  addStockToBasket(basketId, stockData) {
    return request.post(`/baskets/${basketId}/stocks`, stockData)
      .then(handleResponse)
      .then(data => data.basket)
  },

  // 从篮子移除股票
  removeStockFromBasket(basketId, stockCode) {
    return request.delete(`/baskets/${basketId}/stocks/${stockCode}`)
      .then(handleResponse)
      .then(data => data.basket)
  },

  // 调整篮子中股票权重
  adjustStockWeight(basketId, stockCode, newWeight) {
    return request.patch(`/baskets/${basketId}/stocks/${stockCode}`, { weight: newWeight })
      .then(handleResponse)
      .then(data => data.basket)
  },

  // 获取篮子表现数据
  getBasketPerformance(basketId, period = '1y') {
    return request.get(`/baskets/${basketId}/performance`, { params: { period } })
      .then(handleResponse)
      .then(data => data.performance)
  },

  // 从回测结果导入篮子
  importFromBacktest(backtestId, basketName) {
    return request.post(`/baskets/import/backtest/${backtestId}`, { name: basketName })
      .then(handleResponse)
      .then(data => data.basket)
  },

  // 复制篮子
  cloneBasket(basketId, newName) {
    return request.post(`/baskets/${basketId}/clone`, { newName })
      .then(handleResponse)
      .then(data => data.newBasket)
  },

  // 获取篮子实时行情
  getBasketRealtime(basketId) {
    return request.get(`/baskets/${basketId}/realtime`)
      .then(handleResponse)
      .then(data => data.realtime)
  }
}