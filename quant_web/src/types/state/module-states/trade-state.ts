// 交易执行状态管理
// 负责管理交易订单、持仓、账户等交易相关状态

export interface TradeState {
  // 账户信息
  account: {
    // 基本信息
    info: {
      accountId: string; // 账户ID
      broker: string; // 券商
      type: string; // 账户类型
      status: string; // 账户状态
    };

    // 资金信息
    capital: {
      totalAssets: number; // 总资产
      netAssets: number; // 净资产
      availableCash: number; // 可用资金
      frozenCash: number; // 冻结资金
      marketValue: number; // 持仓市值
    };

    // 今日统计
    today: {
      pnl: number; // 今日盈亏
      commission: number; // 今日手续费
      tradeCount: number; // 成交笔数
    };
  };

  // 持仓信息
  positions: {
    // 持仓列表
    list: Array<{
      symbol: string; // 标的代码
      name: string; // 标的名称
      volume: number; // 持仓数量
      availableVolume: number; // 可用数量
      costPrice: number; // 成本价
      currentPrice: number; // 当前价
      marketValue: number; // 市值
      pnl: number; // 浮动盈亏
      pnlRatio: number; // 盈亏比例
    }>;

    // 持仓统计
    statistics: {
      totalValue: number; // 总市值
      totalPnl: number; // 总盈亏
      positionCount: number; // 持仓品种数
      concentration: number; // 集中度
    };
  };

  // 订单管理
  orders: {
    // 当前订单列表
    current: Array<{
      orderId: string; // 订单ID
      strategyId: string | null; // 策略ID（手动交易为空）
      symbol: string; // 标的代码
      direction: "buy" | "sell"; // 买卖方向
      price: number; // 委托价格
      volume: number; // 委托数量
      filledVolume: number; // 已成交数量
      status: "submitted" | "partial" | "filled" | "cancelled" | "rejected"; // 状态
      orderTime: string; // 委托时间
      cancelTime: string | null; // 撤单时间
    }>;

    // 历史订单
    history: any[];

    // 订单统计
    statistics: {
      todayOrders: number; // 今日委托数
      todayTrades: number; // 今日成交数
      successRate: number; // 成交成功率
    };
  };

  // 成交记录
  trades: {
    // 成交列表
    list: Array<{
      tradeId: string; // 成交ID
      orderId: string; // 订单ID
      symbol: string; // 标的代码
      direction: "buy" | "sell"; // 买卖方向
      price: number; // 成交价格
      volume: number; // 成交数量
      amount: number; // 成交金额
      commission: number; // 手续费
      tax: number; // 印花税
      tradeTime: string; // 成交时间
    }>;
  };

  // 交易驾驶舱状态
  tradingCockpit: {
    // 快速交易面板
    quickTrade: {
      symbol: string; // 当前交易标的
      direction: "buy" | "sell"; // 交易方向
      priceType: "limit" | "market"; // 价格类型
      price: number; // 价格
      volume: number; // 数量
      amount: number; // 金额
    };

    // 图表交易状态
    chartTrading: {
      selectedSymbol: string; // 选中的标的
      chartType: string; // 图表类型
      indicators: string[]; // 技术指标
    };
  };

  // 加载状态
  loading: {
    account: boolean; // 账户信息加载
    positions: boolean; // 持仓加载
    orders: boolean; // 订单加载
    trades: boolean; // 成交加载
    trading: boolean; // 交易操作加载
  };
}
