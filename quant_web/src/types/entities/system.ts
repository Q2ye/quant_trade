// quant_web/src/types/entities/system.ts
// 系统相关实体
import { BaseEntity } from './base';

/**
 * 数据同步任务
 */
export interface DataSyncTask extends BaseEntity {
  task_type: string;             // 任务类型（daily/minute/financial等）
  status: 'pending' | 'running' | 'completed' | 'failed'; // 任务状态
  start_time?: string;           // 开始时间
  end_time?: string;             // 结束时间
  total_records: number;         // 同步记录数
  error_message?: string;        // 错误信息
  progress: number;              // 进度百分比
  details?: Record<string, any>; // 详细数据
}

/**
 * 系统日志记录
 */
export interface SystemLog extends BaseEntity {
  id: string;                   // 日志ID
  level: 'info' | 'warning' | 'error' | 'debug'; // 日志级别
  module: string;               // 模块名称
  message: string;              // 日志消息
  timestamp: string;            // 时间戳
  user_id?: string;             // 关联用户ID
  username?: string;            // 用户名
  ip_address?: string;          // IP地址
  details?: Record<string, any>; // 详细数据
  user_agent?: string;          // 用户代理
}

/**
 * 系统设置项
 */
export interface SystemSetting extends BaseEntity {
  key: string;                   // 设置键
  value: any;                    // 设置值
  type: 'string' | 'number' | 'boolean' | 'object' | 'array'; // 值类型
  description: string;           // 设置描述
  category: string;              // 分类
  is_public: boolean;            // 是否公开
  editable: boolean;             // 是否可编辑
}

/**
 * 系统健康状态
 */
export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy'; // 整体状态
  components: {                  // 组件状态
    database: ComponentHealth;   // 数据库
    redis: ComponentHealth;      // Redis缓存
    api: ComponentHealth;        // API服务
    strategy_engine: ComponentHealth; // 策略引擎
    data_service: ComponentHealth; // 数据服务
  };
  last_check: string;            // 最后检查时间
}

/**
 * 组件健康状态
 */
export interface ComponentHealth {
  status: 'up' | 'down' | 'degraded'; // 组件状态
  response_time?: number;        // 响应时间（毫秒）
  details?: Record<string, any>; // 详细状态信息
}

/**
 * 审计日志
 */
export interface AuditLog extends BaseEntity {
  user_id: string;               // 用户ID
  action: string;                // 操作动作
  resource_type: string;         // 资源类型
  resource_id?: string;          // 资源ID
  details: Record<string, any>;  // 操作详情
  ip_address: string;            // 操作IP
  user_agent?: string;           // 用户代理
}

/**
 * 系统监控指标
 */
export interface SystemMetrics {
  cpu: {                            // CPU使用情况
    usage: number;                  // 使用率
    cores: number;                  // 核心数
  };
  memory: {                         // 内存使用情况
    total: number;                  // 总内存
    used: number;                   // 已使用
    free: number;                   // 空闲内存
    usage: number;                  // 使用率
  };
  disk: {                           // 磁盘使用情况
    total: number;                  // 总空间
    used: number;                   // 已使用
    free: number;                   // 空闲空间
    usage: number;                  // 使用率
  };
  database: {                       // 数据库状态
    connections: number;            // 连接数
    queries: number;                // 查询数
  };
  redis: {                          // Redis状态
    connections: number;            // 连接数
    memory: number;                // 内存使用
  };
}

/**
 * 任务调度信息
 */
export interface ScheduledTask {
  id: string;                        // 任务ID
  name: string;                      // 任务名称
  type: string;                      // 任务类型
  status: 'running' | 'paused' | 'error'; // 任务状态
  last_run?: string;                 // 最后运行时间
  next_run?: string;                 // 下次运行时间
  interval: string;                  // 执行间隔
  description?: string;              // 任务描述
}

/**
 * 数据源状态
 */
export interface DataSourceStatus {
  name: string;                      // 数据源名称
  type: string;                      // 数据类型
  status: 'connected' | 'disconnected' | 'error'; // 连接状态
  last_update?: string;              // 最后更新时间
  error_message?: string;            // 错误信息
}

/**
 * 系统备份参数
 */
export interface SystemBackupRequest {
  backup_type: 'full' | 'incremental'; // 备份类型
  include_data: boolean;              // 是否包含数据
  description?: string;               // 备份描述
}

/**
 * 系统备份信息
 */
export interface SystemBackup {
  id: string;                        // 备份ID
  name: string;                      // 备份名称
  backup_type: string;               // 备份类型
  size: number;                      // 备份大小
  created_at: string;                // 创建时间
  description?: string;              // 备份描述
}