// quant_web/src/store/modules/strategyStudio.ts
// 策略工作室Vuex模块
// 负责策略开发、回测、参数优化等高级功能的状态管理
import { Module } from "vuex";
import { RootState } from "@/types";
import request from "@/utils/request";
import webSocketService from "@/api/websocket";

/**
 * 策略参数接口
 */
interface StrategyParameter {
  name: string;
  type: string;
  value: any;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

/**
 * 回测配置接口
 */
interface BacktestConfig {
  startDate: string;
  endDate: string;
  initialCapital: number;
  universe: string[];
  benchmark: string;
  frequency: "daily" | "minute";
}

/**
 * 日志条目接口
 */
interface LogEntry {
  timestamp: number;
  level: "info" | "warning" | "error";
  message: string;
}

/**
 * 文件条目接口
 */
interface FileEntry {
  name: string;
  content: string;
  type: "strategy" | "module" | "config";
}

/**
 * 优化结果接口
 */
interface OptimizationResult {
  parameters: any;
  metrics: any;
}

/**
 * 策略工作室状态接口
 */
export interface StrategyStudioState {
  // 当前编辑的策略代码
  currentCode: string;
  originalCode: string;

  // 代码编辑器状态
  editor: {
    language: string;
    theme: string;
    fontSize: number;
    wordWrap: boolean;
  };

  // 策略参数
  parameters: StrategyParameter[];

  // 回测配置
  backtestConfig: BacktestConfig;

  // 回测结果
  backtestResult: any | null;
  backtestProgress: number;
  isBacktesting: boolean;

  // 参数优化
  optimization: {
    isRunning: boolean;
    progress: number;
    results: OptimizationResult[];
    bestParameters: any | null;
  };

  // 实时日志
  logs: LogEntry[];

  // 文件管理
  files: FileEntry[];

  // 工作区状态
  workspace: {
    layout: "single" | "dual" | "triple";
    activePanel: "editor" | "backtest" | "optimization" | "logs";
  };
}

const state: StrategyStudioState = {
  currentCode: "",
  originalCode: "",
  editor: {
    language: "python",
    theme: "vs-dark",
    fontSize: 14,
    wordWrap: false,
  },
  parameters: [],
  backtestConfig: {
    startDate: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split("T")[0], // 一年前
    endDate: new Date().toISOString().split("T")[0], // 今天
    initialCapital: 1000000,
    universe: ["000001.SZ", "000002.SZ"],
    benchmark: "000300.SH",
    frequency: "daily",
  },
  backtestResult: null,
  backtestProgress: 0,
  isBacktesting: false,
  optimization: {
    isRunning: false,
    progress: 0,
    results: [],
    bestParameters: null,
  },
  logs: [],
  files: [],
  workspace: {
    layout: "dual",
    activePanel: "editor",
  },
};

const mutations = {
  /**
   * 设置策略代码
   */
  SET_CURRENT_CODE(state: StrategyStudioState, code: string) {
    state.currentCode = code;
    if (!state.originalCode) {
      state.originalCode = code;
    }
  },

  /**
   * 重置代码为原始版本
   */
  RESET_CODE(state: StrategyStudioState) {
    state.currentCode = state.originalCode;
  },

  /**
   * 更新编辑器设置
   */
  UPDATE_EDITOR_SETTINGS(
    state: StrategyStudioState,
    settings: Partial<StrategyStudioState["editor"]>,
  ) {
    state.editor = { ...state.editor, ...settings };
  },

  /**
   * 设置策略参数
   */
  SET_PARAMETERS(state: StrategyStudioState, parameters: StrategyParameter[]) {
    state.parameters = parameters;
  },

  /**
   * 更新参数值
   */
  UPDATE_PARAMETER(
    state: StrategyStudioState,
    { name, value }: { name: string; value: any },
  ) {
    const param = state.parameters.find((p) => p.name === name);
    if (param) {
      param.value = value;
    }
  },

  /**
   * 更新回测配置
   */
  UPDATE_BACKTEST_CONFIG(
    state: StrategyStudioState,
    config: Partial<BacktestConfig>,
  ) {
    state.backtestConfig = { ...state.backtestConfig, ...config };
  },

  /**
   * 设置回测结果
   */
  SET_BACKTEST_RESULT(state: StrategyStudioState, result: any) {
    state.backtestResult = result;
    state.isBacktesting = false;
    state.backtestProgress = 100;
  },

  /**
   * 更新回测进度
   */
  UPDATE_BACKTEST_PROGRESS(state: StrategyStudioState, progress: number) {
    state.backtestProgress = progress;
  },

  /**
   * 设置回测状态
   */
  SET_BACKTESTING_STATUS(state: StrategyStudioState, isBacktesting: boolean) {
    state.isBacktesting = isBacktesting;
    if (!isBacktesting) {
      state.backtestProgress = 0;
    }
  },

  /**
   * 开始参数优化
   */
  START_OPTIMIZATION(state: StrategyStudioState) {
    state.optimization.isRunning = true;
    state.optimization.progress = 0;
    state.optimization.results = [];
  },

  /**
   * 更新优化进度
   */
  UPDATE_OPTIMIZATION_PROGRESS(state: StrategyStudioState, progress: number) {
    state.optimization.progress = progress;
  },

  /**
   * 添加优化结果
   */
  ADD_OPTIMIZATION_RESULT(
    state: StrategyStudioState,
    result: OptimizationResult,
  ) {
    state.optimization.results.push(result);
  },

  /**
   * 设置最佳参数
   */
  SET_BEST_PARAMETERS(state: StrategyStudioState, parameters: any) {
    state.optimization.bestParameters = parameters;
    state.optimization.isRunning = false;
  },

  /**
   * 停止优化
   */
  STOP_OPTIMIZATION(state: StrategyStudioState) {
    state.optimization.isRunning = false;
    state.optimization.progress = 0;
  },

  /**
   * 添加日志
   */
  ADD_LOG(state: StrategyStudioState, log: LogEntry) {
    state.logs.unshift(log); // 新的日志放在前面

    // 保持最多1000条日志
    if (state.logs.length > 1000) {
      state.logs.splice(1000);
    }
  },

  /**
   * 清空日志
   */
  CLEAR_LOGS(state: StrategyStudioState) {
    state.logs = [];
  },

  /**
   * 设置文件列表
   */
  SET_FILES(state: StrategyStudioState, files: FileEntry[]) {
    state.files = files;
  },

  /**
   * 更新工作区布局
   */
  UPDATE_WORKSPACE_LAYOUT(
    state: StrategyStudioState,
    layout: StrategyStudioState["workspace"]["layout"],
  ) {
    state.workspace.layout = layout;
  },

  /**
   * 设置活动面板
   */
  SET_ACTIVE_PANEL(
    state: StrategyStudioState,
    panel: StrategyStudioState["workspace"]["activePanel"],
  ) {
    state.workspace.activePanel = panel;
  },
};

const actions = {
  /**
   * 加载策略模板
   */
  async loadStrategyTemplate({ commit }: any, templateName: string) {
    try {
      const response = await request.get(
        `/quantTrade/strategy/templates/${templateName}`
      );
      commit("SET_CURRENT_CODE", response.code || response.data?.code);
      commit("SET_PARAMETERS", response.parameters || response.data?.parameters || []);
      return response;
    } catch (error) {
      console.error("加载策略模板失败:", error);
      throw error;
    }
  },

  /**
   * 验证策略代码
   */
  async validateCode({ state }: any) {
    try {
      const response = await request.post("/quantTrade/strategies/validate", {
        code: state.currentCode,
      });
      return response;
    } catch (error) {
      console.error("代码验证失败:", error);
      throw error;
    }
  },

  /**
   * 运行回测
   */
  async runBacktest({ commit, state, rootState }: any) {
    if (!rootState.user.isAuthenticated) {
      throw new Error("请先登录");
    }

    commit("SET_BACKTESTING_STATUS", true);
    commit("CLEAR_LOGS");

    try {
      // 使用 WebSocketService 单例（复用重连逻辑 + 消息路由）
      const wsUrl =
        import.meta.env.VITE_WS_URL || `ws://${window.location.host}/backtest`;

      webSocketService.connect(wsUrl);

      // 发送回测启动消息
      const parametersObj = state.parameters.reduce(
        (acc: Record<string, any>, param: StrategyParameter) => {
          acc[param.name] = param.value;
          return acc;
        },
        {} as Record<string, any>,
      );

      webSocketService.sendMessage({
        type: "start_backtest",
        code: state.currentCode,
        parameters: parametersObj,
        config: state.backtestConfig,
      });

      // 订阅回测消息频道
      webSocketService.subscribe("backtest:progress", (data: any) => {
        commit("UPDATE_BACKTEST_PROGRESS", data.progress);
      });

      webSocketService.subscribe("backtest:log", (data: any) => {
        commit("ADD_LOG", {
          timestamp: Date.now(),
          level: data.level,
          message: data.message,
        });
      });

      webSocketService.subscribe("backtest:result", (data: any) => {
        commit("SET_BACKTEST_RESULT", data.result);
        webSocketService.disconnect();
      });

      webSocketService.subscribe("backtest:error", (data: any) => {
        commit("ADD_LOG", {
          timestamp: Date.now(),
          level: "error",
          message: data.error || data.message,
        });
        commit("SET_BACKTESTING_STATUS", false);
        webSocketService.disconnect();
      });

      // WebSocketService 内置 onerror 处理和指数退避重连
    } catch (error) {
      console.error("运行回测失败:", error);
      commit("SET_BACKTESTING_STATUS", false);
      throw error;
    }
  },

  /**
   * 停止回测
   */
  async stopBacktest({ commit }: any) {
    commit("SET_BACKTESTING_STATUS", false);
    commit("UPDATE_BACKTEST_PROGRESS", 0);
  },

  /**
   * 运行参数优化
   */
  async runOptimization({ commit, state }: any, optimizationConfig: any) {
    commit("START_OPTIMIZATION");
    commit("CLEAR_LOGS");

    try {
      const response = await request.post("/quantTrade/strategies/optimize", {
        code: state.currentCode,
        parameterRanges: optimizationConfig.parameterRanges,
        method: optimizationConfig.method,
        metric: optimizationConfig.metric,
        config: state.backtestConfig,
      }, {
        responseType: "stream",
      });

      const reader = response.body?.getReader();
      if (!reader) throw new Error("无法读取优化结果");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = new TextDecoder().decode(value);
        const lines = text.split("\n");

        for (const line of lines) {
          if (line.trim()) {
            const data = JSON.parse(line);

            if (data.type === "progress") {
              commit("UPDATE_OPTIMIZATION_PROGRESS", data.progress);
            } else if (data.type === "result") {
              commit("ADD_OPTIMIZATION_RESULT", data.result);
            } else if (data.type === "best") {
              commit("SET_BEST_PARAMETERS", data.parameters);
            }
          }
        }
      }
    } catch (error) {
      console.error("参数优化失败:", error);
      commit("STOP_OPTIMIZATION");
      throw error;
    }
  },

  /**
   * 停止优化
   */
  async stopOptimization({ commit }: any) {
    commit("STOP_OPTIMIZATION");
  },

  /**
   * 保存策略
   */
  async saveStrategy({ state, rootState }: any, strategyName: string) {
    if (!rootState.user.isAuthenticated) {
      throw new Error("请先登录");
    }

    try {
      const response = await request.post("/quantTrade/strategies", {
        name: strategyName,
        code: state.currentCode,
        parameters: state.parameters,
      });
      return response;
    } catch (error) {
      console.error("保存策略失败:", error);
      throw error;
    }
  },

  /**
   * 导出策略
   */
  exportStrategy({ state }: any) {
    const strategyData = {
      code: state.currentCode,
      parameters: state.parameters,
      backtestConfig: state.backtestConfig,
      exportTime: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(strategyData, null, 2)], {
      type: "application/json",
    });

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `strategy_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },

  /**
   * 导入策略
   */
  importStrategy({ commit }: any, file: File) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          const strategyData = JSON.parse(e.target?.result as string);
          commit("SET_CURRENT_CODE", strategyData.code);
          commit("SET_PARAMETERS", strategyData.parameters || []);

          if (strategyData.backtestConfig) {
            commit("UPDATE_BACKTEST_CONFIG", strategyData.backtestConfig);
          }

          resolve(strategyData);
        } catch (error) {
          reject(new Error("文件格式错误"));
        }
      };

      reader.onerror = () => reject(new Error("文件读取失败"));
      reader.readAsText(file);
    });
  },
};

const getters = {
  /**
   * 获取代码是否修改
   */
  isCodeModified: (state: StrategyStudioState) => {
    return state.currentCode !== state.originalCode;
  },

  /**
   * 获取回测指标
   */
  getBacktestMetrics: (state: StrategyStudioState) => {
    if (!state.backtestResult) return null;

    return {
      totalReturn: state.backtestResult.total_return,
      annualReturn: state.backtestResult.annual_return,
      sharpeRatio: state.backtestResult.sharpe_ratio,
      maxDrawdown: state.backtestResult.max_drawdown,
      winRate: state.backtestResult.win_rate,
    };
  },

  /**
   * 获取优化结果排序
   */
  getSortedOptimizationResults:
    (state: StrategyStudioState) =>
    (metric: string = "sharpe") => {
      return [...state.optimization.results].sort((a, b) => {
        return b.metrics[metric] - a.metrics[metric];
      });
    },

  /**
   * 获取错误日志
   */
  getErrorLogs: (state: StrategyStudioState) => {
    return state.logs.filter((log) => log.level === "error");
  },

  /**
   * 获取最近日志
   */
  getRecentLogs:
    (state: StrategyStudioState) =>
    (limit: number = 50) => {
      return state.logs.slice(0, limit);
    },
};

const strategyStudioModule: Module<StrategyStudioState, RootState> = {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
};

export default strategyStudioModule;
