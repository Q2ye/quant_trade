// 系统监控API
// 系统监控API
import request from '../utils/request'
import { handleResponse } from '../utils/responseHandler'

export default {
  // 检查连接状态
  checkConnections() {
    return request.get('/system/connections')
      .then(handleResponse)
      .then(data => ({
        dataSource: data.dataSource,
        tradeGateway: data.tradeGateway,
        strategyEngine: data.strategyEngine
      }))
  },

  // 获取资源使用情况
  getResourceUsage() {
    return request.get('/system/resources')
      .then(handleResponse)
      .then(data => ({
        cpu: data.cpu,
        memory: data.memory,
        disk: data.disk,
        network: data.network
      }))
  },

  // 获取系统日志
  getSystemLogs(params) {
    return request.get('/system/logs', { params })
      .then(handleResponse)
      .then(data => ({
        logs: data.logs,
        total: data.total,
        page: data.page
      }))
  },

  // 同步数据源
  syncDataSource(source) {
    return request.post(`/system/sync/${source}`)
      .then(handleResponse)
      .then(data => ({
        success: data.success,
        message: data.message,
        syncId: data.syncId
      }))
  },

  // 获取任务队列状态
  getTaskQueueStatus() {
    return request.get('/system/tasks')
      .then(handleResponse)
      .then(data => data.tasks)
  },

  // 获取系统配置
  getSystemConfig() {
    return request.get('/system/config')
      .then(handleResponse)
      .then(data => data.config)
  },

  // 更新系统配置
  updateSystemConfig(config) {
    return request.put('/system/config', config)
      .then(handleResponse)
      .then(data => data.updatedConfig)
  },

  // 获取服务状态
  getServiceStatus(serviceName) {
    return request.get(`/system/services/${serviceName}/status`)
      .then(handleResponse)
      .then(data => data.status)
  },

  // 重启服务
  restartService(serviceName) {
    return request.post(`/system/services/${serviceName}/restart`)
      .then(handleResponse)
      .then(data => ({
        success: data.success,
        message: data.message
      }))
  },

  // 获取数据库状态
  getDatabaseStatus() {
    return request.get('/system/database')
      .then(handleResponse)
      .then(data => ({
        size: data.size,
        tables: data.tables,
        lastBackup: data.lastBackup
      }))
  },

  // 创建数据库备份
  createDatabaseBackup() {
    return request.post('/system/database/backup')
      .then(handleResponse)
      .then(data => ({
        success: data.success,
        backupId: data.backupId
      }))
  }
}