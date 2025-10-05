// 用户相关枚举类型定义
export enum UserRole {
  SUPER_ADMIN = 'super_admin',  // 超级管理员
  ADMIN = 'admin',              // 管理员
  USER = 'user',                // 普通用户
  GUEST = 'guest',              // 访客
  READ_ONLY = 'read_only'       // 只读用户
}

export enum PermissionLevel {
  NONE = 'none',              // 无权限
  READ = 'read',              // 读取权限
  WRITE = 'write',            // 写入权限
  EXECUTE = 'execute',        // 执行权限
  ADMIN = 'admin'             // 管理权限
}

export enum UserStatus {
  ACTIVE = 'active',          // 活跃
  INACTIVE = 'inactive',      // 非活跃
  SUSPENDED = 'suspended',    // 暂停
  LOCKED = 'locked',          // 锁定
  DELETED = 'deleted'         // 已删除
}

export enum LoginMethod {
  PASSWORD = 'password',      // 密码登录
  SMS = 'sms',                // 短信登录
  EMAIL = 'email',            // 邮箱登录
  SSO = 'sso',                // 单点登录
  API_KEY = 'api_key'         // API密钥登录
}

export enum VerificationType {
  EMAIL = 'email',            // 邮箱验证
  PHONE = 'phone',            // 手机验证
  TWO_FACTOR = 'two_factor',  // 双因子验证
  KYC = 'kyc'                 // 实名认证
}

export enum PreferenceCategory {
  GENERAL = 'general',        // 通用设置
  TRADING = 'trading',        // 交易设置
  NOTIFICATION = 'notification', // 通知设置
  DISPLAY = 'display',        // 显示设置
  RISK = 'risk'               // 风险设置
}

export enum DashboardView {
  OVERVIEW = 'overview',      // 概览视图
  TRADING = 'trading',        // 交易视图
  RESEARCH = 'research',      // 研究视图
  PERFORMANCE = 'performance', // 绩效视图
  RISK = 'risk'               // 风险视图
}

export enum NotificationChannel {
  EMAIL = 'email',            // 邮件通知
  SMS = 'sms',                // 短信通知
  PUSH = 'push',              // 推送通知
  WEBHOOK = 'webhook',        // Webhook通知
  IN_APP = 'in_app'           // 应用内通知
}