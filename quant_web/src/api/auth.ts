import request from '@/utils/request'
import { handleResponse } from '@/utils/responseHandler'
import { ApiResponse } from '@/types'

/**
 * 认证管理API服务
 * 专门处理用户认证、令牌管理和安全相关功能
 */

// 定义缺失的类型
export interface LoginRequest {
  username: string
  password: string
  rememberMe?: boolean
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  confirmPassword?: string
}

export interface UserInfo {
  id: string | number
  username: string
  email: string
  avatar?: string
  roles?: string[]
  permissions?: string[]
  createdAt?: string
  updatedAt?: string
}

export interface AuthResponse {
  token: string;
  user: UserInfo;
  expiresIn: number;
  refreshToken?: string;
}

export interface TokenInfo {
  token: string;
  expiresAt: string;
  issuedAt: string;
  type: 'access' | 'refresh';
}

export interface TokenCleanupResult {
  cleanedCount: number;
  remainingTokens: number;
}

export default {
  /**
   * 用户登录
   * @param credentials 登录凭证
   * @returns 认证响应信息
   */
  async login(credentials: LoginRequest): Promise<AuthResponse> {
    return request.post('/auth/login', credentials)
      .then(handleResponse)
      .then((data: ApiResponse<AuthResponse>) => data.data)
  },

  /**
   * 用户注册
   * @param userData 注册信息
   * @returns 认证响应信息
   */
  async register(userData: RegisterRequest): Promise<AuthResponse> {
    return request.post('/auth/register', userData)
      .then(handleResponse)
      .then((data: ApiResponse<AuthResponse>) => data.data)
  },

  /**
   * 用户登出
   * @returns 登出操作结果
   */
  async logout(): Promise<void> {
    return request.post('/auth/logout')
      .then(handleResponse)
  },

  /**
   * 刷新访问令牌
   * @param refreshToken 刷新令牌
   * @returns 新的认证响应
   */
  async refreshToken(refreshToken: string): Promise<AuthResponse> {
    return request.post('/auth/refresh', { refreshToken })
      .then(handleResponse)
      .then((data: ApiResponse<AuthResponse>) => data.data)
  },

  /**
   * 验证令牌有效性
   * @param token 访问令牌
   * @returns 验证结果
   */
  async validateToken(token: string): Promise<{ isValid: boolean; user?: UserInfo }> {
    return request.get('/auth/validate', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(handleResponse)
      .then((data: ApiResponse<{ isValid: boolean; user?: UserInfo }>) => data.data)
  },

  /**
   * 获取令牌信息
   * @param token 访问令牌
   * @returns 令牌详细信息
   */
  async getTokenInfo(token: string): Promise<TokenInfo> {
    return request.get('/auth/token-info', {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(handleResponse)
      .then((data: ApiResponse<TokenInfo>) => data.data)
  },

  /**
   * 清理过期令牌
   * @param token 管理员令牌
   * @returns 清理结果
   */
  async cleanupExpiredTokens(token: string): Promise<TokenCleanupResult> {
    return request.post('/auth/tokens/cleanup', null, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(handleResponse)
      .then((data: ApiResponse<TokenCleanupResult>) => data.data)
  },

  /**
   * 重置密码请求（发送重置邮件）
   * @param email 用户邮箱
   * @returns 操作结果
   */
  async requestPasswordReset(email: string): Promise<{ success: boolean; message: string }> {
    return request.post('/auth/password/reset-request', { email })
      .then(handleResponse)
      .then((data: ApiResponse<{ success: boolean; message: string }>) => data.data)
  },

  /**
   * 确认重置密码
   * @param token 重置令牌
   * @param newPassword 新密码
   * @returns 操作结果
   */
  async confirmPasswordReset(token: string, newPassword: string): Promise<{ success: boolean; message: string }> {
    return request.post('/auth/password/reset-confirm', { token, newPassword })
      .then(handleResponse)
      .then((data: ApiResponse<{ success: boolean; message: string }>) => data.data)
  },

  /**
   * 验证邮箱地址
   * @param token 验证令牌
   * @returns 验证结果
   */
  async verifyEmail(token: string): Promise<{ success: boolean; message: string }> {
    return request.post('/auth/email/verify', { token })
      .then(handleResponse)
      .then((data: ApiResponse<{ success: boolean; message: string }>) => data.data)
  },

  /**
   * 重新发送邮箱验证邮件
   * @param email 用户邮箱
   * @returns 操作结果
   */
  async resendVerificationEmail(email: string): Promise<{ success: boolean; message: string }> {
    return request.post('/auth/email/resend-verification', { email })
      .then(handleResponse)
      .then((data: ApiResponse<{ success: boolean; message: string }>) => data.data)
  }
}