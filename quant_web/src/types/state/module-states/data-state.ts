// 数据管理状态
// 负责管理数据同步、行情数据、财务数据等的状态

export interface DataState {
  // 数据同步任务状态
  syncTasks: {
    // 任务列表
    tasks: Array<{
      id: string; // 任务ID
      type: "daily" | "minute" | "financial" | "basic"; // 任务类型
      status: "pending" | "running" | "completed" | "failed"; // 任务状态
      progress: number; // 进度百分比
      startTime: string | null; // 开始时间
      endTime: string | null; // 结束时间
      totalRecords: number; // 总记录数
      errorMessage?: string; // 错误信息
    }>;

    // 同步统计
    statistics: {
      lastSyncTime: string | null; // 最后同步时间
      totalSynced: number; // 总同步记录数
      successRate: number; // 成功率
    };
  };

  // 行情数据状态
  marketData: {
    // 实时行情订阅列表
    subscriptions: Array<{
      symbol: string; // 标的代码
      dataType: "tick" | "minute" | "daily"; // 数据类型
      lastUpdate: string; // 最后更新时间
    }>;

    // 缓存的数据
    cache: Map<string, any>; // 标的代码 -> 行情数据映射
  };

  // 财务数据状态
  financialData: {
    // 已加载的财务数据
    loadedData: Map<string, any>; // 标的代码 -> 财务数据映射

    // 数据更新时间
    updateTime: string | null;
  };

  // 数据质量监控
  dataQuality: {
    // 数据完整性检查
    completeness: {
      daily: number; // 日线数据完整度
      minute: number; // 分钟数据完整度
      financial: number; // 财务数据完整度
    };

    // 数据延迟情况
    latency: {
      marketData: number; // 行情数据延迟（秒）
      financialData: number; // 财务数据延迟（天）
    };
  };

  // 加载状态
  loading: {
    syncTasks: boolean; // 同步任务加载
    marketData: boolean; // 行情数据加载
    financialData: boolean; // 财务数据加载
  };
}
