// quant_web/src/types/state/module-states/strategy-state.ts
// 策略管理状态
// 负责管理策略的创建、编辑、回测、执行等操作的状态

import { Strategy } from '@/types/entities/strategy';

export interface StrategyState {
  // 策略列表
  strategyList: Strategy[];

  // 当前选中的策略
  currentStrategy: Strategy | null;

  // 策略模板库
  strategyTemplates: Array<{
    id: string;                     // 模板ID
    name: string;                   // 模板名称
    category: string;               // 策略类别
    description: string;            // 策略描述
    code: string;                   // 策略代码
    parameters: any;                // 默认参数
  }>;

  // 策略运行状态
  strategyStatus: Map<string, {
    strategyId: string;             // 策略ID
    status: 'running' | 'stopped' | 'error'; // 运行状态
    startTime: string | null;       // 启动时间
    lastSignalTime: string | null;  // 最后信号时间
    performance: any;               // 实时绩效
  }>;

  // 策略参数编辑
  parameterEditing: {
    currentParameters: any;         // 当前编辑的参数
    originalParameters: any;        // 原始参数（用于重置）
    hasChanges: boolean;            // 是否有未保存的更改
  };

  // 策略代码编辑
  codeEditing: {
    currentCode: string;            // 当前编辑的代码
    originalCode: string;           // 原始代码
    hasChanges: boolean;            // 是否有未保存的更改
    syntaxErrors: any[];            // 语法错误
  };

  // 加载状态
  loading: {
    list: boolean;                  // 列表加载
    detail: boolean;                // 详情加载
    templates: boolean;             // 模板加载
    create: boolean;                // 创建策略
    update: boolean;                // 更新策略
    delete: boolean;                // 删除策略
    start: boolean;                 // 启动策略
    stop: boolean;                  // 停止策略
  };

  // 错误信息
  error: {
    list: string | null;
    detail: string | null;
    create: string | null;
    update: string | null;
    delete: string | null;
    operation: string | null;       // 操作错误（启动/停止）
  };
}