// 用户API
import request from '../utils/request'
import { handleResponse } from '../utils/responseHandler'

export default {
  // 用户登录
  login(credentials) {
    return request.post('/auth/login', credentials)
      .then(handleResponse)
      .then(data => ({
        token: data.token,
        user: data.user,
        expiresIn: data.expiresIn
      }))
  },

  // 用户登出
  logout() {
    return request.post('/auth/logout')
      .then(handleResponse)
  },

  // 获取用户信息
  getUserInfo() {
    return request.get('/user/info')
      .then(handleResponse)
      .then(data => data.user)
  },

  // 更新用户信息
  updateUserInfo(userInfo) {
    return request.put('/user/info', userInfo)
      .then(handleResponse)
      .then(data => data.updatedUser)
  },

  // 修改密码
  changePassword(oldPassword, newPassword) {
    return request.post('/user/password', { oldPassword, newPassword })
      .then(handleResponse)
      .then(data => ({
        success: data.success,
        message: data.message
      }))
  },

  // 获取用户偏好设置
  getUserPreferences() {
    return request.get('/user/preferences')
      .then(handleResponse)
      .then(data => data.preferences)
  },

  // 更新用户偏好设置
  updateUserPreferences(preferences) {
    return request.put('/user/preferences', preferences)
      .then(handleResponse)
      .then(data => data.updatedPreferences)
  },

  // 获取通知设置
  getNotificationSettings() {
    return request.get('/user/notifications')
      .then(handleResponse)
      .then(data => data.notifications)
  },

  // 更新通知设置
  updateNotificationSettings(settings) {
    return request.put('/user/notifications', settings)
      .then(handleResponse)
      .then(data => data.updatedSettings)
  },

  // 获取API密钥
  getApiKeys() {
    return request.get('/user/api-keys')
      .then(handleResponse)
      .then(data => data.keys)
  },

  // 创建API密钥
  createApiKey(name) {
    return request.post('/user/api-keys', { name })
      .then(handleResponse)
      .then(data => data.newKey)
  },

  // 删除API密钥
  deleteApiKey(keyId) {
    return request.delete(`/user/api-keys/${keyId}`)
      .then(handleResponse)
  },

  // 获取操作日志
  getUserActivityLogs(page = 1, pageSize = 20) {
    return request.get('/user/activity', {
      params: { page, pageSize }
    })
      .then(handleResponse)
      .then(data => ({
        logs: data.logs,
        total: data.total,
        page: data.page
      }))
  },

  // 启用双因素认证
  enableTwoFactorAuth() {
    return request.post('/user/two-factor/enable')
      .then(handleResponse)
      .then(data => ({
        secret: data.secret,
        qrCode: data.qrCode
      }))
  },

  // 验证双因素认证
  verifyTwoFactorAuth(token) {
    return request.post('/user/two-factor/verify', { token })
      .then(handleResponse)
      .then(data => ({
        success: data.success,
        recoveryCodes: data.recoveryCodes
      }))
  },

  // 禁用双因素认证
  disableTwoFactorAuth() {
    return request.post('/user/two-factor/disable')
      .then(handleResponse)
  }
}