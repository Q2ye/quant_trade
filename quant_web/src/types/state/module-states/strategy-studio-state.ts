// quant_web/src/types/state/module-states/strategy-studio-state.ts
// 策略工作室状态管理
// 负责策略开发、回测、参数优化等高级功能的状态

export interface StrategyStudioState {
  // 回测配置
  backtestConfig: {
    // 基本配置
    basic: {
      strategyId: string;           // 策略ID
      name: string;                 // 回测名称
      description: string;          // 回测描述
    };

    // 时间范围
    timeRange: {
      startDate: string;            // 开始日期
      endDate: string;              // 结束日期
      frequency: 'daily' | 'minute'; // 数据频率
    };

    // 资金配置
    capital: {
      initial: number;              // 初始资金
      commission: number;           // 手续费率
      slippage: number;             // 滑点
    };

    // 标的配置
    universe: {
      type: 'single' | 'basket' | 'all'; // 标的类型
      symbols: string[];            // 标的代码列表
      basketId: string | null;      // 篮子ID
    };
  };

  // 回测任务状态
  backtestTasks: {
    // 任务列表
    tasks: Array<{
      id: string;                   // 任务ID
      name: string;                 // 任务名称
      status: 'pending' | 'running' | 'completed' | 'failed'; // 状态
      progress: number;             // 进度
      startTime: string | null;     // 开始时间
      endTime: string | null;       // 结束时间
      result: any | null;           // 回测结果
    }>;

    // 当前选中的任务
    currentTaskId: string | null;
  };

  // 回测结果分析
  backtestResults: {
    // 绩效指标
    performance: any | null;

    // 净值曲线
    equityCurve: any[];

    // 交易记录
    trades: any[];

    // 持仓记录
    positions: any[];

    // 分析视图配置
    viewConfig: {
      selectedCharts: string[];     // 选中的图表类型
      timeRange: any;               // 时间范围筛选
      comparisonBenchmark: string | null; // 对比基准
    };
  };

  // 参数优化
  parameterOptimization: {
    // 优化配置
    config: {
      parameters: Map<string, {     // 参数名 -> 范围配置
        min: number;
        max: number;
        step: number;
      }>;
      objective: string;            // 优化目标（夏普比率、最大回撤等）
      method: 'grid' | 'genetic' | 'bayesian'; // 优化方法
    };

    // 优化结果
    results: {
      bestParameters: any;          // 最佳参数组合
      parameterSpace: any[];        // 参数空间探索结果
      convergence: any[];           // 收敛曲线
    };
  };

  // 因子研究
  factorResearch: {
    // 因子配置
    factors: Array<{
      id: string;                   // 因子ID
      name: string;                 // 因子名称
      formula: string;              // 因子公式
      category: string;             // 因子类别
    }>;

    // 研究结果
    researchResults: {
      icAnalysis: any;              // IC分析结果
      factorReturns: any;           // 因子收益率
      correlation: any;             // 因子相关性
    };
  };

  // 加载状态
  loading: {
    backtest: boolean;              // 回测加载
    optimization: boolean;          // 参数优化加载
    research: boolean;              // 因子研究加载
  };
}