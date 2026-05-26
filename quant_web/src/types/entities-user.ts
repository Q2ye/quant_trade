// 用户相关实体
import { BaseEntity } from "./common";

/**
 * 用户信息
 */
export interface User extends BaseEntity {
  id: string; // 用户ID
  username: string; // 用户名
  email?: string; // 邮箱
  phone?: string; // 手机号
  real_name?: string; // 真实姓名
  role: "admin" | "user" | "guest"; // 用户角色
  is_active: boolean; // 是否激活
  last_login?: string; // 最后登录时间
  preferences?: UserPreferences; // 用户偏好设置
}

/**
 * 用户偏好设置
 */
export interface UserPreferences {
  theme: "light" | "dark" | "auto"; // 主题模式
  language: "zh-CN" | "en-US"; // 语言设置
  notifications: {
    // 通知设置
    email: boolean; // 邮件通知
    push: boolean; // 推送通知
    sms: boolean; // 短信通知
  };
  trading: {
    // 交易设置
    default_order_type: "limit" | "market"; // 默认订单类型
    default_volume: number; // 默认交易数量
    confirm_before_trade: boolean; // 交易前确认
  };
  dashboard: {
    // 仪表盘设置
    default_view: "overview" | "trading" | "research"; // 默认视图
    refresh_interval: number; // 刷新间隔（秒）
  };
}

/**
 * 用户权限
 */
export interface UserPermission {
  id: string; // 权限ID
  user_id: string; // 用户ID
  module: string; // 模块名称
  can_read: boolean; // 读取权限
  can_write: boolean; // 写入权限
  can_execute: boolean; // 执行权限
  created_at: string; // 创建时间
  updated_at: string; // 更新时间
}

/**
 * 登录请求参数
 */
export interface LoginRequest {
  username: string; // 用户名
  password: string; // 密码
  remember_me?: boolean; // 记住我
}

/**
 * 登录响应数据
 */
export interface LoginResponse {
  user: User; // 用户信息
  token: string; // 认证令牌
  expires_in: number; // 过期时间（秒）
}

/**
 * 注册请求参数
 */
export interface RegisterRequest {
  username: string; // 用户名
  password: string; // 密码
  email?: string; // 邮箱
  phone?: string; // 手机号
  real_name?: string; // 真实姓名
}

/**
 * 修改密码请求参数
 */
export interface ChangePasswordRequest {
  current_password: string; // 当前密码
  new_password: string; // 新密码
  confirm_password: string; // 确认密码
}

/**
 * 重置密码请求参数
 */
export interface ResetPasswordRequest {
  email: string; // 邮箱
  token: string; // 重置令牌
  new_password: string; // 新密码
}
