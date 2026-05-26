// 用户状态管理
// 负责管理用户认证、权限、个人信息等状态数据

import { User } from "./entities-user";

/**
 * 用户状态接口定义
 * 包含用户登录状态、权限信息、个人资料等核心数据
 */
export interface UserState {
  /**
   * 用户认证令牌
   * JWT token，用于API请求身份验证
   * null表示未登录状态
   */
  token: string | null;

  /**
   * 用户基本信息
   * 包含用户ID、用户名、邮箱、角色等个人信息
   * null表示用户信息未加载或未登录
   */
  userInfo: User | null;

  /**
   * 用户权限列表
   * 字符串数组，包含用户拥有的所有权限代码
   * 用于前端路由守卫和按钮级权限控制
   * 例如：['events:read', 'events:write', 'events:execute']
   */
  permissions: string[];

  /**
   * 最后登录时间
   * ISO格式的时间字符串，记录用户最后一次成功登录的时间
   * 用于显示登录历史和安全性检查
   */
  lastLogin: string | null;

  /**
   * 认证状态标识
   * 布尔值，表示用户是否已通过身份认证
   * 基于token和userInfo的综合判断结果
   */
  isAuthenticated: boolean;

  /**
   * 登录加载状态
   * 控制登录过程中的UI反馈，防止重复提交
   */
  loading: {
    login: boolean; // 登录中
    logout: boolean; // 登出中
    profile: boolean; // 个人信息加载中
  };

  /**
   * 错误信息记录
   * 记录认证过程中发生的错误，用于用户提示
   */
  error: {
    login: string | null; // 登录错误
    register: string | null; // 注册错误
    profile: string | null; // 个人信息错误
  };

  /**
   * 会话管理
   * 控制用户会话的持久化和安全性
   */
  session: {
    rememberMe: boolean; // 记住登录状态
    autoLogin: boolean; // 自动登录
    sessionTimeout: number; // 会话超时时间（分钟）
  };
}
