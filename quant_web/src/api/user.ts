import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  UserInfo,
  UpdateUserRequest,
  ApiChangePasswordRequest,
  ApiUserPermission,
  ApiResponse,
  PaginatedResponse,
} from "@/types";

/**
 * 用户管理API服务
 * 专门处理用户信息管理、偏好设置、安全配置和个人数据管理
 */

export interface ActivityLog {
  id: string;
  action: string;
  module: string;
  timestamp: string;
  ipAddress?: string;
  userAgent?: string;
  details?: any;
}

export interface TwoFactorSetup {
  secret: string;
  qrCode: string;
  recoveryCodes: string[];
}

export interface ApiKeyInfo {
  id: string;
  name: string;
  prefix: string;
  created: string;
  lastUsed?: string;
  expires?: string;
  permissions: string[];
}

export interface UserPreferences {
  language: string;
  timezone: string;
  dateFormat: string;
  numberFormat: string;
  theme: "light" | "dark" | "auto";
  notifications: {
    email: boolean;
    push: boolean;
    sms: boolean;
    tradingAlerts: boolean;
    systemAlerts: boolean;
  };
  trading: {
    defaultOrderType: "limit" | "market";
    confirmOrders: boolean;
    showAdvancedOptions: boolean;
  };
}

export interface NotificationSettings {
  channels: {
    email: boolean;
    push: boolean;
    sms: boolean;
    webhook: boolean;
  };
  events: {
    login: boolean;
    passwordChange: boolean;
    tradeExecution: boolean;
    riskAlert: boolean;
    systemMaintenance: boolean;
  };
  quietHours?: {
    enabled: boolean;
    start: string;
    end: string;
  };
}

export default {
  /**
   * 获取当前用户信息
   * @returns 用户详细信息
   */
  async getCurrentUser(): Promise<UserInfo> {
    return request
      .get("/quantTrade/system/me")
      .then(handleResponse)
      .then((data: ApiResponse<UserInfo>) => data.data);
  },

  /**
   * 更新用户信息
   * @param userInfo 用户信息更新参数
   * @returns 更新后的用户信息
   */
  async updateUser(userInfo: UpdateUserRequest): Promise<UserInfo> {
    return request
      .put("/quantTrade/system/me", userInfo)
      .then(handleResponse)
      .then((data: ApiResponse<UserInfo>) => data.data);
  },

  /**
   * 修改密码
   * @param passwordData 密码修改参数
   * @returns 修改结果
   */
  async changePassword(
    passwordData: ApiChangePasswordRequest,
  ): Promise<{ success: boolean; message: string }> {
    return request
      .post("/quantTrade/system/auth/change-password", passwordData)
      .then(handleResponse)
      .then(
        (data: ApiResponse<{ success: boolean; message: string }>) => data.data,
      );
  },

  /**
   * 获取用户偏好设置
   * @returns 用户偏好设置
   */
  async getPreferences(): Promise<UserPreferences> {
    return request
      .get("/quantTrade/system/preferences")
      .then(handleResponse)
      .then((data: ApiResponse<UserPreferences>) => data.data);
  },

  /**
   * 更新用户偏好设置
   * @param preferences 偏好设置
   * @returns 更新后的偏好设置
   */
  async updatePreferences(
    preferences: Partial<UserPreferences>,
  ): Promise<UserPreferences> {
    return request
      .put("/quantTrade/system/preferences", preferences)
      .then(handleResponse)
      .then((data: ApiResponse<UserPreferences>) => data.data);
  },

  /**
   * 获取通知设置
   * @returns 通知设置信息
   */
  async getNotificationSettings(): Promise<NotificationSettings> {
    return request
      .get("/quantTrade/system/notifications")
      .then(handleResponse)
      .then((data: ApiResponse<NotificationSettings>) => data.data);
  },

  /**
   * 更新通知设置
   * @param settings 通知设置
   * @returns 更新后的通知设置
   */
  async updateNotificationSettings(
    settings: Partial<NotificationSettings>,
  ): Promise<NotificationSettings> {
    return request
      .put("/quantTrade/system/notifications", settings)
      .then(handleResponse)
      .then((data: ApiResponse<NotificationSettings>) => data.data);
  },

  /**
   * 获取API密钥列表
   * @returns API密钥数组
   */
  async getApiKeys(): Promise<ApiKeyInfo[]> {
    return request
      .get("/quantTrade/system/api-keys")
      .then(handleResponse)
      .then((data: ApiResponse<ApiKeyInfo[]>) => data.data);
  },

  /**
   * 创建API密钥
   * @param name 密钥名称
   * @param permissions 权限列表
   * @param expiresIn 过期时间（天）
   * @returns 新创建的API密钥（包含完整密钥，仅此时可见）
   */
  async createApiKey(
    name: string,
    permissions: string[] = [],
    expiresIn?: number,
  ): Promise<ApiKeyInfo & { key: string }> {
    return request
      .post("/quantTrade/system/api-keys", { name, permissions, expiresIn })
      .then(handleResponse)
      .then((data: ApiResponse<ApiKeyInfo & { key: string }>) => data.data);
  },

  /**
   * 更新API密钥
   * @param keyId 密钥ID
   * @param updates 更新内容
   * @returns 更新后的API密钥信息
   */
  async updateApiKey(
    keyId: string,
    updates: { name?: string; permissions?: string[] },
  ): Promise<ApiKeyInfo> {
    return request
      .put(`/quantTrade/system/api-keys/${keyId}`, updates)
      .then(handleResponse)
      .then((data: ApiResponse<ApiKeyInfo>) => data.data);
  },

  /**
   * 删除API密钥
   * @param keyId 密钥ID
   * @returns 删除操作结果
   */
  async deleteApiKey(keyId: string): Promise<void> {
    return request.delete(`/quantTrade/system/api-keys/${keyId}`).then(handleResponse);
  },

  /**
   * 轮换API密钥（重新生成密钥值）
   * @param keyId 密钥ID
   * @returns 新的密钥值
   */
  async rotateApiKey(keyId: string): Promise<{ key: string }> {
    return request
      .post(`/quantTrade/system/api-keys/${keyId}/rotate`)
      .then(handleResponse)
      .then((data: ApiResponse<{ key: string }>) => data.data);
  },

  /**
   * 获取用户活动日志
   * @param params 查询参数
   * @returns 活动日志分页结果
   */
  async getActivityLogs(params?: {
    page?: number;
    limit?: number;
    action?: string;
    startDate?: string;
    endDate?: string;
  }): Promise<PaginatedResponse<ActivityLog>> {
    return request
      .get("/quantTrade/system/activity", { params })
      .then(handleResponse)
      .then((data: PaginatedResponse<ActivityLog>) => data);
  },

  /**
   * 启用双因素认证
   * @returns 双因素认证设置信息
   */
  async enableTwoFactorAuth(): Promise<TwoFactorSetup> {
    return request
      .post("/quantTrade/system/two-factor/enable")
      .then(handleResponse)
      .then((data: ApiResponse<TwoFactorSetup>) => data.data);
  },

  /**
   * 验证双因素认证
   * @param token 验证令牌
   * @returns 验证结果
   */
  async verifyTwoFactorAuth(
    token: string,
  ): Promise<{ success: boolean; recoveryCodes: string[] }> {
    return request
      .post("/quantTrade/system/two-factor/verify", { token })
      .then(handleResponse)
      .then(
        (data: ApiResponse<{ success: boolean; recoveryCodes: string[] }>) =>
          data.data,
      );
  },

  /**
   * 禁用双因素认证
   * @returns 禁用操作结果
   */
  async disableTwoFactorAuth(): Promise<void> {
    return request.post("/quantTrade/system/two-factor/disable").then(handleResponse);
  },

  /**
   * 获取双因素认证状态
   * @returns 双因素认证状态
   */
  async getTwoFactorStatus(): Promise<{ enabled: boolean; lastUsed?: string }> {
    return request
      .get("/quantTrade/system/two-factor/status")
      .then(handleResponse)
      .then(
        (data: ApiResponse<{ enabled: boolean; lastUsed?: string }>) =>
          data.data,
      );
  },

  /**
   * 生成新的恢复代码
   * @returns 新的恢复代码数组
   */
  async generateRecoveryCodes(): Promise<{ recoveryCodes: string[] }> {
    return request
      .post("/quantTrade/system/two-factor/recovery-codes")
      .then(handleResponse)
      .then((data: ApiResponse<{ recoveryCodes: string[] }>) => data.data);
  },

  /**
   * 获取用户权限列表
   * @returns 用户权限数组
   */
  async getPermissions(): Promise<ApiUserPermission[]> {
    return request
      .get("/quantTrade/system/permissions")
      .then(handleResponse)
      .then((data: ApiResponse<ApiUserPermission[]>) => data.data);
  },

  /**
   * 导出用户数据
   * @returns 用户数据导出结果
   */
  async exportData(): Promise<{ exportId: string; estimatedTime: number }> {
    return request
      .post("/quantTrade/system/data/export")
      .then(handleResponse)
      .then(
        (data: ApiResponse<{ exportId: string; estimatedTime: number }>) =>
          data.data,
      );
  },

  /**
   * 获取数据导出状态
   * @param exportId 导出ID
   * @returns 导出状态信息
   */
  async getExportStatus(exportId: string): Promise<{
    status: "processing" | "completed" | "failed";
    downloadUrl?: string;
    error?: string;
  }> {
    return request
      .get(`/quantTrade/system/data/export/${exportId}`)
      .then(handleResponse)
      .then((data: ApiResponse<any>) => data.data);
  },

  /**
   * 删除用户账户
   * @param confirmation 确认信息
   * @returns 删除操作结果
   */
  async deleteAccount(confirmation: {
    password: string;
    reason?: string;
  }): Promise<{ success: boolean; message: string }> {
    return request
      .delete("/quantTrade/system/account", { data: confirmation })
      .then(handleResponse)
      .then(
        (data: ApiResponse<{ success: boolean; message: string }>) => data.data,
      );
  },
};
