// 交易API
import request from '../utils/request'
import { handleResponse } from '../utils/responseHandler'

export default {
  // 获取账户信息
  getAccountInfo() {
    return request.get('/trade/account')
      .then(handleResponse)
      .then(data => data.account)
  },

  // 获取当前持仓
  getPositions() {
    return request.get('/trade/positions')
      .then(handleResponse)
      .then(data => data.positions)
  },

  // 获取订单历史
  getOrderHistory(params = {}) {
    return request.get('/trade/orders', { params })
      .then(handleResponse)
      .then(data => data.orders)
  },

  // 获取成交记录
  getTradeRecords(params = {}) {
    return request.get('/trade/trades', { params })
      .then(handleResponse)
      .then(data => data.trades)
  },

  // 创建订单
  createOrder(orderData) {
    return request.post('/trade/order', orderData)
      .then(handleResponse)
      .then(data => data.order)
  },

  // 修改订单
  modifyOrder(orderId, updateData) {
    return request.put(`/trade/order/${orderId}`, updateData)
      .then(handleResponse)
      .then(data => data.updatedOrder)
  },

  // 取消订单
  cancelOrder(orderId) {
    return request.delete(`/trade/order/${orderId}`)
      .then(handleResponse)
  },

  // 篮子交易（批量下单）
  basketTrade(basketId, tradeData) {
    return request.post(`/trade/basket/${basketId}`, tradeData)
      .then(handleResponse)
      .then(data => data.results)
  },

  // 获取实时交易信号
  getTradeSignals() {
    return request.get('/trade/signals')
      .then(handleResponse)
      .then(data => data.signals)
  },

  // 确认并执行信号
  executeSignal(signalId) {
    return request.post(`/trade/signal/${signalId}/execute`)
      .then(handleResponse)
      .then(data => data.order)
  },

  // 忽略信号
  ignoreSignal(signalId) {
    return request.post(`/trade/signal/${signalId}/ignore`)
      .then(handleResponse)
  },

  // 获取交易绩效
  getTradePerformance() {
    return request.get('/trade/performance')
      .then(handleResponse)
      .then(data => data.performance)
  }
}