// 基础实体类型
export interface BaseEntity {
  id: string; // 唯一标识符
  created_at: string; // 创建时间（ISO格式）
  updated_at: string; // 最后更新时间（ISO格式）
}

export interface PaginationParams {
  page: number; // 当前页码（从1开始）
  pageSize: number; // 每页数据条数
  total: number; // 总数据条数
}

export interface ListResponse<T> {
  data: T[]; // 数据列表
  pagination: PaginationParams; // 分页信息
}

// 通用枚举类型
export enum Status {
  ACTIVE = "active", // 活跃状态
  INACTIVE = "inactive", // 非活跃状态
  DELETED = "deleted", // 已删除状态
}

export enum OrderDirection {
  BUY = "buy", // 买入方向
  SELL = "sell", // 卖出方向
}

export enum OrderType {
  LIMIT = "limit", // 限价单：指定价格执行
  MARKET = "market", // 市价单：当前市场价执行
  STOP = "stop", // 止损单：达到触发价后转为市价单
}

export enum OrderStatus {
  SUBMITTED = "submitted", // 已提交：订单已发送到券商
  PARTIAL_FILLED = "partial_filled", // 部分成交：订单部分执行
  FILLED = "filled", // 全部成交：订单完全执行
  CANCELLED = "cancelled", // 已撤销：订单被取消
  REJECTED = "rejected", // 已拒绝：订单被券商拒绝
}

export enum StrategyStatus {
  RUNNING = "running", // 运行中：策略正在执行
  STOPPED = "stopped", // 已停止：策略暂停执行
  ERROR = "error", // 错误状态：策略执行异常
}

export enum SignalType {
  BUY = "buy", // 买入信号：建议买入标的
  SELL = "sell", // 卖出信号：建议卖出标的
  HOLD = "hold", // 持有信号：建议继续持有
}
