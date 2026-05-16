// quant_web/src/types/state/module-states/risk-state.ts
// 风险管理状态
// 负责管理风险监控、风控规则、风险事件等状态

export interface RiskState {
  // 风控规则配置
  riskRules: {
    // 规则列表
    rules: Array<{
      id: string; // 规则ID
      name: string; // 规则名称
      type: "position" | "loss" | "liquidity" | "blacklist"; // 规则类型
      condition: any; // 规则条件
      action: "alert" | "stop" | "cancel"; // 触发动作
      enabled: boolean; // 是否启用
      priority: number; // 优先级
    }>;

    // 当前编辑的规则
    editingRule: any | null;
  };

  // 实时风险监控
  realTimeMonitoring: {
    // 账户风险指标
    accountRisk: {
      totalRisk: number; // 总风险度
      positionRisk: number; // 持仓风险
      concentrationRisk: number; // 集中度风险
      liquidityRisk: number; // 流动性风险
    };

    // 策略风险指标
    strategyRisks: Map<
      string,
      {
        strategyId: string; // 策略ID
        riskLevel: "low" | "medium" | "high"; // 风险等级
        metrics: any; // 风险指标
      }
    >;

    // 市场风险指标
    marketRisk: {
      volatility: number; // 市场波动率
      correlation: number; // 相关性风险
      sentiment: number; // 市场情绪
    };
  };

  // 风险事件记录
  riskEvents: {
    // 事件列表
    events: Array<{
      id: string; // 事件ID
      ruleId: string; // 规则ID
      strategyId: string; // 策略ID
      type: string; // 事件类型
      level: "info" | "warning" | "error" | "critical"; // 事件级别
      message: string; // 事件描述
      triggerValue: any; // 触发值
      actionTaken: string; // 采取的动作
      timestamp: string; // 发生时间
    }>;

    // 事件统计
    statistics: {
      today: number; // 今日事件数
      critical: number; // 严重事件数
      unresolved: number; // 未处理事件数
    };
  };

  // 黑名单管理
  blacklist: {
    // 黑名单股票
    stocks: Array<{
      symbol: string; // 股票代码
      name: string; // 股票名称
      reason: string; // 加入原因
      addedDate: string; // 加入日期
      enabled: boolean; // 是否启用
    }>;
  };

  // 风险报告
  riskReports: {
    // 日报、周报、月报
    daily: any | null;
    weekly: any | null;
    monthly: any | null;
  };

  // 加载状态
  loading: {
    rules: boolean; // 规则加载
    monitoring: boolean; // 监控数据加载
    events: boolean; // 事件加载
    blacklist: boolean; // 黑名单加载
  };
}
