// quant_web/src/types/state/module-states/system-state.ts
// 系统管理状态
// 负责管理系统配置、用户管理、日志监控等状态

export interface SystemState {
  // 系统配置
  systemConfig: {
    // 交易配置
    trading: {
      defaultCommission: number;    // 默认手续费率
      defaultSlippage: number;      // 默认滑点
      tradeConfirm: boolean;        // 交易确认
      autoCancelTimeout: number;    // 自动撤单超时
    };

    // 风险配置
    risk: {
      maxPositionRatio: number;     // 最大持仓比例
      maxDailyLoss: number;         // 单日最大亏损
      enableBlacklist: boolean;     // 启用黑名单
    };

    // 数据配置
    data: {
      autoSync: boolean;            // 自动同步
      syncInterval: number;         // 同步间隔
      keepHistoryDays: number;      // 历史数据保留天数
    };

    // 通知配置
    notification: {
      enableEmail: boolean;         // 邮件通知
      enableWechat: boolean;        // 微信通知
      criticalAlerts: boolean;      // 关键警报
    };
  };

  // 用户管理
  userManagement: {
    // 用户列表
    users: Array<{
      id: string;                   // 用户ID
      username: string;             // 用户名
      email: string;                // 邮箱
      role: 'admin' | 'user' | 'guest'; // 角色
      status: 'active' | 'inactive'; // 状态
      lastLogin: string | null;     // 最后登录时间
    }>;

    // 当前编辑的用户
    editingUser: any | null;
  };

  // 系统监控
  systemMonitor: {
    // 系统资源使用情况
    resources: {
      cpuUsage: number;             // CPU使用率
      memoryUsage: number;          // 内存使用率
      diskUsage: number;            // 磁盘使用率
      networkUsage: number;         // 网络使用率
    };

    // 服务状态
    services: Array<{
      name: string;                 // 服务名称
      status: 'running' | 'stopped' | 'error'; // 状态
      uptime: number;               // 运行时间
      lastCheck: string;            // 最后检查时间
    }>;

    // 数据库状态
    database: {
      connections: number;          // 连接数
      queryPerformance: number;     // 查询性能
      size: number;                 // 数据库大小
    };
  };

  // 系统日志
  systemLogs: {
    // 日志列表
    logs: Array<{
      id: string;                   // 日志ID
      level: 'info' | 'warning' | 'error' | 'debug'; // 日志级别
      module: string;               // 模块名称
      message: string;              // 日志消息
      timestamp: string;            // 时间戳
      user: string;                 // 操作用户
    }>;

    // 日志筛选条件
    filters: {
      level: string[];              // 级别筛选
      module: string[];             // 模块筛选
      dateRange: {                  // 时间范围
        start: string;
        end: string;
      };
      keyword: string;              // 关键词搜索
    };

    // 分页信息
    pagination: {
      page: number;
      pageSize: number;
      total: number;
    };
  };

  // 加载状态
  loading: {
    config: boolean;                // 配置加载
    users: boolean;                 // 用户加载
    monitor: boolean;               // 监控数据加载
    logs: boolean;                  // 日志加载
  };
}