// 状态类型统一导出
// 集中管理所有状态类型的导出，提供统一的类型访问入口

/**
 * 根状态及相关类型导出
 * 包含应用完整的状态树定义和工具类型
 */
export * from "./root-state";

/**
 * 模块状态类型导出
 * 按功能模块划分的状态类型定义
 */
export * from "./module-states";

/**
 * 状态工具类型
 * 提供状态管理的辅助类型定义
 */

/**
 * 加载状态枚举
 * 定义统一的加载状态标识
 */
export enum LoadingStatus {
  IDLE = "idle", // 空闲状态
  PENDING = "pending", // 加载中
  SUCCESS = "success", // 加载成功
  FAILED = "failed", // 加载失败
}

/**
 * 筛选参数接口
 * 统一的列表筛选参数定义
 */
export interface FilterParams {
  keyword?: string; // 关键词搜索
  sortField?: string; // 排序字段
  sortOrder?: "asc" | "desc"; // 排序方向
  [key: string]: any; // 扩展字段
}

/**
 * API响应状态接口
 * 统一的后端API响应数据结构
 */
export interface ApiResponse<T = any> {
  code: number; // 状态码
  message: string; // 消息
  data: T; // 响应数据
  timestamp: number; // 时间戳
}

/**
 * 错误状态接口
 * 统一的错误信息处理结构
 */
export interface ErrorState {
  code: string; // 错误代码
  message: string; // 错误消息
  details?: any; // 错误详情
  timestamp: number; // 发生时间
}

/**
 * 状态快照接口
 * 用于状态持久化和恢复的数据结构
 */
export interface StateSnapshot {
  version: string; // 状态版本
  timestamp: number; // 快照时间
  data: any; // 状态数据
  modules: string[]; // 包含的模块
}

// 状态版本常量
export const STATE_VERSION = "1.0.0";

/**
 * 创建状态快照工具函数
 * @param state 当前状态
 * @param modules 需要快照的模块列表
 * @returns 状态快照对象
 */
export function createStateSnapshot(
  state: any,
  modules: string[] = [],
): StateSnapshot {
  const snapshotData: any = {};

  if (modules.length === 0) {
    // 快照所有模块
    Object.keys(state).forEach((module) => {
      snapshotData[module] = state[module];
    });
  } else {
    // 快照指定模块
    modules.forEach((module) => {
      if (state[module]) {
        snapshotData[module] = state[module];
      }
    });
  }

  return {
    version: STATE_VERSION,
    timestamp: Date.now(),
    data: snapshotData,
    modules: modules.length === 0 ? Object.keys(state) : modules,
  };
}

/**
 * 验证状态快照有效性
 * @param snapshot 状态快照
 * @returns 验证结果
 */
export function validateStateSnapshot(snapshot: StateSnapshot): boolean {
  return (
    snapshot &&
    snapshot.version === STATE_VERSION &&
    snapshot.timestamp > 0 &&
    snapshot.data &&
    Array.isArray(snapshot.modules)
  );
}

// 仪表盘API响应类型
export interface DashboardOverview {
  total_assets: number;
  daily_pnl: number;
  position_value: number;
  available_cash: number;
  return_rate: number;
}

export interface MarketStatus {
  [market: string]: "open" | "closed" | "halted" | "pre_market" | "after_hours";
}

export interface DashboardOverviewResponse {
  data: DashboardOverview;
}

export interface MarketStatusResponse {
  data: MarketStatus;
}
