// 工具类型统一导出文件

// 导出图表相关类型
export * from './charts';

// 导出通用工具类型
export * from './common';

// 导出表单相关类型
export * from './form';

// 导出表格相关类型
export * from './table';

// 导出Vuex相关类型
export * from './vuex';

/**
 * 深度只读类型工具
 */
export type DeepReadonly<T> = {
  readonly [P in keyof T]: T[P] extends object ? DeepReadonly<T[P]> : T[P];
};

/**
 * 深度可选类型工具
 */
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

/**
 * 深度必需类型工具
 */
export type DeepRequired<T> = {
  [P in keyof T]-?: T[P] extends object ? DeepRequired<T[P]> : T[P];
};

/**
 * 函数类型工具
 */
export type FunctionType = (...args: any[]) => any;

/**
 * 构造函数类型工具
 */
export type ConstructorType<T = any> = new (...args: any[]) => T;

/**
 * 提取Promise值的类型工具
 */
export type Awaited<T> = T extends PromiseLike<infer U> ? Awaited<U> : T;

/**
 * 异步函数返回类型工具
 */
export type AsyncFunctionReturnType<T extends FunctionType> = Awaited<ReturnType<T>>;

/**
 * 事件处理器类型
 */
export type EventHandler<T = any> = (event: T) => void;

/**
 * 防抖函数配置
 */
export interface DebounceOptions {
  wait?: number;          // 等待时间
  leading?: boolean;      // 是否在延迟开始前调用
  trailing?: boolean;     // 是否在延迟结束后调用
  maxWait?: number;       // 最大等待时间
}

/**
 * 节流函数配置
 */
export interface ThrottleOptions {
  wait?: number;          // 等待时间
  leading?: boolean;      // 是否在节流开始前调用
  trailing?: boolean;     // 是否在节流结束后调用
}