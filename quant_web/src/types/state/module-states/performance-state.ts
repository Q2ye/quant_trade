// 绩效分析状态管理
// 负责管理策略和账户的绩效分析数据

import {
  AccountPerformance,
  StrategyPerformance
} from '@/types/entities/performance';
import { StrategyListItem } from '@/types/api/performance';

export interface PerformanceState {
  // 账户绩效数据，按accountId索引
  accountPerformance: Record<string, AccountPerformance>;

  // 策略绩效数据，按strategyId索引
  strategyPerformance: Record<string, StrategyPerformance>;

  // 对比分析数据
  comparisonData: any;

  // 分析报告
  analysisReports: Record<string, any>;

  // 加载状态
  loading: {
    account: boolean;
    strategy: boolean;
    comparison: boolean;
  };

  // 策略列表
  tlist: StrategyListItem[];

  // 当前选中的策略
  currentStrategy: {
    id: string | null;
    detail: any;
    tradeRecords: any[];
  };
}