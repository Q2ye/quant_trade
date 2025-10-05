// 枚举类型统一导出
import {
  StrategyStatus,
  StrategyType,
  StrategyCategory,
  BacktestStatus,
  SignalType
} from './strategy.enum';

import {
  OrderStatus,
  OrderType,
  OrderDirection,
  PositionSide,
  TradeType
} from './trading.enum';

import { UserRole } from './user.enum';
import { RiskLevel } from './common.enum';
import {
  DataSource,
  DataType,
  SyncTaskStatus,
  LogLevel,
  HealthStatus
} from './system.enum';

// 枚举工具函数
export const getEnumKeys = <T extends Record<string, any>>(enumObj: T): Array<keyof T> => {
  return Object.keys(enumObj).filter(key => isNaN(Number(key))) as Array<keyof T>;
};

export const getEnumValues = <T extends Record<string, any>>(enumObj: T): Array<T[keyof T]> => {
  const keys = getEnumKeys(enumObj);
  return keys.map(key => enumObj[key]);
};

export const getEnumKeyByValue = <T extends Record<string, any>>(
  enumObj: T,
  value: T[keyof T]
): keyof T | undefined => {
  const keys = getEnumKeys(enumObj);
  return keys.find(key => enumObj[key] === value);
};

export const enumToOptions = <T extends Record<string, any>>(
  enumObj: T,
  labelMap?: Record<keyof T, string>
): Array<{ label: string; value: T[keyof T] }> => {
  const keys = getEnumKeys(enumObj);
  return keys.map(key => ({
    label: labelMap?.[key] || key.toString(),
    value: enumObj[key]
  }));
};

// 常用枚举映射
export const StrategyStatusLabel = {
  [StrategyStatus.DRAFT]: '草稿',
  [StrategyStatus.RUNNING]: '运行中',
  [StrategyStatus.STOPPED]: '已停止',
  [StrategyStatus.PAUSED]: '暂停',
  [StrategyStatus.ERROR]: '错误',
  [StrategyStatus.DISABLED]: '禁用'
};

export const OrderStatusLabel = {
  [OrderStatus.SUBMITTED]: '已提交',
  [OrderStatus.PENDING]: '待处理',
  [OrderStatus.ACCEPTED]: '已接受',
  [OrderStatus.PARTIAL_FILLED]: '部分成交',
  [OrderStatus.FILLED]: '全部成交',
  [OrderStatus.CANCELLED]: '已撤销',
  [OrderStatus.REJECTED]: '已拒绝',
  [OrderStatus.EXPIRED]: '已过期'
};

export const UserRoleLabel = {
  [UserRole.SUPER_ADMIN]: '超级管理员',
  [UserRole.ADMIN]: '管理员',
  [UserRole.USER]: '普通用户',
  [UserRole.GUEST]: '访客',
  [UserRole.READ_ONLY]: '只读用户'
};

export const RiskLevelLabel = {
  [RiskLevel.LOW]: '低风险',
  [RiskLevel.MEDIUM]: '中风险',
  [RiskLevel.HIGH]: '高风险',
  [RiskLevel.CRITICAL]: '严重风险'
};

// 枚举分组
export const TradingEnums = {
  OrderType,
  OrderStatus,
  OrderDirection,
  PositionSide,
  TradeType
};

export const StrategyEnums = {
  StrategyStatus,
  StrategyType,
  StrategyCategory,
  BacktestStatus,
  SignalType
};

export const SystemEnums = {
  DataSource,
  DataType,
  SyncTaskStatus,
  LogLevel,
  HealthStatus
};