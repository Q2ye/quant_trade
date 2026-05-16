// 用户管理API类型定义
import { ApiResponse, PaginatedResponse } from "@/types";
import { PaginationParams } from "./base";

/**
 * 用户登录请求参数
 */
export interface LoginRequest {
  username: string; // 用户名
  password: string; // 密码
  captcha?: string; // 验证码
}

/**
 * 用户注册请求参数
 */
export interface RegisterRequest {
  username: string; // 用户名
  password: string; // 密码
  email: string; // 邮箱
  phone?: string; // 手机号
  realName?: string; // 真实姓名
}

/**
 * 用户信息更新参数
 */
export interface UpdateUserRequest {
  email?: string; // 邮箱
  phone?: string; // 手机号
  realName?: string; // 真实姓名
  avatar?: string; // 头像URL
}

/**
 * 修改密码参数
 */
export interface ChangePasswordRequest {
  oldPassword: string; // 旧密码
  newPassword: string; // 新密码
}

/**
 * 用户权限信息
 */
export interface UserPermission {
  module: string; // 模块名称
  canRead: boolean; // 读取权限
  canWrite: boolean; // 写入权限
  canExecute: boolean; // 执行权限
}

/**
 * 用户信息
 */
export interface UserInfo {
  id: string; // 用户ID
  username: string; // 用户名
  email: string; // 邮箱
  phone?: string; // 手机号
  realName?: string; // 真实姓名
  avatar?: string; // 头像URL
  role: string; // 用户角色
  isActive: boolean; // 是否激活
  lastLogin?: string; // 最后登录时间
  permissions: UserPermission[]; // 权限列表
  createdAt: string; // 创建时间
  updatedAt: string; // 更新时间
}

/**
 * 用户查询参数
 */
export interface UserQueryParams extends PaginationParams {
  username?: string; // 用户名模糊查询
  role?: string; // 角色筛选
  isActive?: boolean; // 激活状态筛选
}

/**
 * 用户创建参数（管理员）
 */
export interface CreateUserRequest {
  username: string; // 用户名
  password: string; // 密码
  email: string; // 邮箱
  phone?: string; // 手机号
  realName?: string; // 真实姓名
  role: string; // 用户角色
}

/**
 * 用户权限更新参数
 */
export interface UpdateUserPermissionRequest {
  userId: string; // 用户ID
  permissions: {
    // 权限列表
    module: string;
    canRead: boolean;
    canWrite: boolean;
    canExecute: boolean;
  }[];
}

// 响应类型定义
export interface LoginResponse extends ApiResponse<{
  token: string; // JWT令牌
  user: UserInfo; // 用户信息
  expiresIn: number; // 过期时间（秒）
}> {}

export interface UserInfoResponse extends ApiResponse<UserInfo> {}

export interface UserListResponse extends PaginatedResponse<UserInfo> {}

export interface PermissionResponse extends ApiResponse<UserPermission[]> {}
