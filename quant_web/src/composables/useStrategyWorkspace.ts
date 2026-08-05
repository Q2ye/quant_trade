/**
 * useStrategyWorkspace.ts — StrategyWorkspace 数据管理
 *
 * 职责：策略加载/保存、回测提交/轮询/结果加载、参数管理
 *
 * 模式区分：
 * - 创建模式：route.name === "StrategyWorkspaceCreate" → 无 :id 参数，ID 由后端生成
 * - 编辑模式：route.name === "StrategyWorkspace"    → 有 :id 参数，值来自后端 UUID
 */
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useMessage } from "naive-ui";
import strategyAPI from "@/api/strategy";
import backtestAPI from "@/api/backtest";
import { useBacktestPolling } from "@/composables/useBacktestPolling";

/** 策略回测历史记录项 */
export interface BacktestHistoryItem {
  taskId: string;
  label: string;
  createdAt: string;
  status: string;
}

export function useStrategyWorkspace() {
  const route = useRoute();
  const router = useRouter();
  const message = useMessage();

  // ---- 页面模式 ----
  const isCreateMode = computed(() => route.name === "StrategyWorkspaceCreate");
  // 编辑模式下有真实 ID，创建模式下为 null
  const strategyId = computed(() => isCreateMode.value ? null : (route.params.id as string));

  // ---- 策略状态 ----
  const loading = ref(true);
  const error = ref(false);
  const saving = ref(false);
  const strategyName = ref("未命名策略");
  const strategyCode = ref("# 在此编写策略代码\n");
  const strategyParams = ref<Record<string, any>>({});
  const strategyStatus = ref("draft");

  // ---- 回测状态 ----
  const isBacktesting = ref(false);
  const backtestProgress = ref(0);
  const backtestStatus = ref("");
  const currentTaskId = ref("");
  const backtestHistory = ref<BacktestHistoryItem[]>([]);
  const selectedHistoryTaskId = ref("");

  // ---- 回测结果 ----
  const btSummary = ref({
    annualReturn: 0, totalReturn: 0, maxDrawdown: 0,
    sharpeRatio: 0, winRate: 0, profitFactor: 0,
    tradesCount: 0, avgTradeReturn: 0,
  });
  const btEquityCurve = ref<any[]>([]);
  const btBenchmark = ref<any[]>([]);
  const btDrawdown = ref<any[]>([]);
  const btMonthlyReturns = ref<any[]>([]);
  const btDailyReturns = ref<any[]>([]);
  const btDailyTurnover = ref<any[]>([]);
  const btTrades = ref<any[]>([]);
  const btResultLoading = ref(false);

  // ---- 回测轮询（自适应间隔 + 容错） ----

  const { start: startPolling, stop: clearPolling } = useBacktestPolling(
    currentTaskId,
    {
      onProgress: (task) => {
        backtestProgress.value = task.progress_percent ?? task.progress ?? 0;
        backtestStatus.value = task.status || backtestStatus.value;
      },
      onCompleted: async (_task) => {
        message.success("回测完成");
        isBacktesting.value = false;
        await loadBacktestResult(currentTaskId.value);
        await loadBacktestHistory();  // 从 API 刷新历史列表
        selectedHistoryTaskId.value = currentTaskId.value;
      },
      onFailed: (task) => {
        message.error(task?.error_message || "回测失败");
        isBacktesting.value = false;
      },
      onCancelled: () => {
        message.warning("回测已取消");
        isBacktesting.value = false;
      },
    },
  );

  // ---- 策略加载 ----

  const loadStrategy = async () => {
    // 创建模式：使用默认值，不从 API 加载
    if (isCreateMode.value) {
      const templateId = (route.query.template as string) || "";
      if (templateId) {
        try {
          const tpl: any = await strategyAPI.getTemplate(templateId);
          if (tpl) {
            strategyName.value = tpl.name || "新建策略";
            strategyCode.value = tpl.code_template || "# 在此编写策略代码\n";
            strategyParams.value = tpl.default_parameters || tpl.parameters || {};
            strategyStatus.value = "draft";
            loading.value = false;
            return;
          }
        } catch { /* 模板加载失败，回退到默认值 */ }
      }
      strategyName.value = "新建策略";
      strategyCode.value = [
        '# ================================================================',
        '# 策略模板 — 修改 on_bar 方法即可运行',
        '# ================================================================',
        'from typing import Dict, List, Optional, Any',
        'import numpy as np',
        'import pandas as pd',
        'import logging',
        '',
        'from modules.strategy.strategies.base.base_strategy import BaseStrategy',
        'from modules.strategy.constants import StrategyType, SignalDirection',
        'from modules.strategy.models import TradingSignal',
        'from core.engines.types.entities import BarData',
        '',
        'logger = logging.getLogger(__name__)',
        '',
        '',
        'class MyStrategy(BaseStrategy):',
        '    """',
        '    策略说明：在这里描述你的策略逻辑',
        '',
        '    参数（可从 UI 参数面板覆盖默认值）：',
        '      param1  — 说明',
        '    """',
        '    strategy_type = StrategyType.CTA',
        '',
        '    def __init__(self, name="我的策略", strategy_type=None, parameters=None):',
        '        super().__init__(',
        '            name=name,',
        '            strategy_type=strategy_type or self.strategy_type,',
        '            parameters=parameters,',
        '        )',
        '        self._params = parameters or {}',
        '',
        '    # ================================================================',
        '    # 核心逻辑 — 每个交易日触发一次',
        '    # ================================================================',
        '    def on_bar(self, bar: BarData):',
        '        """',
        '        bar 字段:',
        '          bar.trade_date   — 交易日期',
        '          bar.ts_code      — 股票代码',
        '          bar.open / bar.high / bar.low / bar.close / bar.volume',
        '        """',
        '        pass',
        '',
        '    # ================================================================',
        '    # 可选生命周期',
        '    # ================================================================',
        '    def on_start(self):',
        '        """策略启动时执行一次"""',
        '        pass',
        '',
        '    def on_stop(self):',
        '        """策略停止时执行一次"""',
        '        pass',
      ].join('\n');
      strategyParams.value = {};
      strategyStatus.value = "draft";
      loading.value = false;
      return;
    }

    // 编辑模式：从 API 加载已有策略
    const id = strategyId.value;
    if (!id) { error.value = true; loading.value = false; return; }

    loading.value = true;
    error.value = false;
    try {
      const s: any = await strategyAPI.getStrategy(id).catch(() => null);
      if (s) {
        strategyName.value = s.name || s.id || "未命名策略";
        strategyCode.value = s.code || "";
        strategyParams.value = s.parameters || {};
        strategyStatus.value = s.status || "draft";
      } else {
        error.value = true;
      }
    } catch {
      error.value = true;
    } finally {
      loading.value = false;
    }
  };

  // ---- 策略保存 ----

  const saveStrategy = async () => {
    saving.value = true;
    try {
      if (isCreateMode.value) {
        // 创建模式 → POST（后端生成 ID）
        const created: any = await strategyAPI.createStrategy({
          name: strategyName.value,
          description: "",
          code: strategyCode.value,
          parameters: strategyParams.value,
        });
        if (!created?.id) {
          message.error("创建失败：未获取到策略 ID");
          return;
        }
        // 从创建路由切换到编辑路由
        await router.replace({ name: "StrategyWorkspace", params: { id: created.id } });
        // 路由切为编辑模式后，从 API 拉取完整策略数据（代码 + 参数）
        await loadStrategy();
        message.success("策略已创建");
      } else {
        // 编辑模式 → PUT（使用已有 ID）
        const id = strategyId.value;
        if (!id) { message.error("策略 ID 无效"); return; }
        await strategyAPI.updateStrategy(id, {
          name: strategyName.value,
          code: strategyCode.value,
          parameters: strategyParams.value,
          status: strategyStatus.value,
        });
        message.success("策略已保存");
      }
    } catch {
      message.error("保存失败");
    } finally {
      saving.value = false;
    }
  };

  // ---- 回测操作 ----

  const submitBacktest = async (config: {
    symbols: string[];
    startDate: string;
    endDate: string;
    initialCapital: number;
    commissionRate: number;
    slippageRate: number;
    benchmark: string;
  }) => {
    // 杀掉任何残留的旧轮询，确保不会和新回测交错
    clearPolling();
    if (isBacktesting.value) return;
    isBacktesting.value = true;
    backtestProgress.value = 0;
    backtestStatus.value = "pending";
    currentTaskId.value = "";

    try {
      const res = await backtestAPI.createTask({
        name: `${strategyName.value}_回测_${config.startDate}`,
        strategy_id: strategyId.value ?? undefined,
        start_date: config.startDate,
        end_date: config.endDate,
        initial_capital: config.initialCapital,
        commission_rate: config.commissionRate,
        slippage_rate: config.slippageRate,
        symbols: config.symbols,
        parameters: { ...strategyParams.value, benchmark: config.benchmark },
      });

      currentTaskId.value = res.task_id;
      backtestStatus.value = "running";
      startPolling();
    } catch {
      message.error("回测提交失败");
      isBacktesting.value = false;
    }
  };

  /** 从 API 加载此策略的回测历史，并自动选中最近完成的任务 */
  const loadBacktestHistory = async () => {
    if (!strategyId.value) return;
    try {
      const res: any = await backtestAPI.getTasks({ page_size: 50 });
      const items = Array.isArray(res) ? res : (res?.data || []);
      const filtered = items
        .filter((t: any) => t.strategy_id === strategyId.value)
        .map((t: any) => ({
          taskId: t.id || t.task_id,
          label: t.name || (t.id || t.task_id)?.slice(0, 8) || '',
          createdAt: t.created_at || '',
          status: t.status || 'unknown',
        }))
        // 按创建时间倒序排列（最新的在前）
        .sort((a: BacktestHistoryItem, b: BacktestHistoryItem) =>
          (b.createdAt || '').localeCompare(a.createdAt || '')
        );

      backtestHistory.value = filtered;

      // 如果当前没有选中任务且有历史记录，自动选中最近完成的任务
      if (!currentTaskId.value && filtered.length > 0) {
        // 优先选择最近完成的
        const latestCompleted = filtered.find((h: BacktestHistoryItem) => h.status === 'completed');
        const autoSelect = latestCompleted || filtered[0];
        selectedHistoryTaskId.value = autoSelect.taskId;
        // 先加载结果数据，再设置 currentTaskId — 确保 NetValueChart 挂载时已有数据
        await loadBacktestResult(autoSelect.taskId);
        currentTaskId.value = autoSelect.taskId;
      }
    } catch { /* 静默失败 */ }
  };

  const loadBacktestResult = async (taskId: string) => {
    btResultLoading.value = true;
    try {
      const [result, equity, trades] = await Promise.all([
        backtestAPI.getResult(taskId).catch(() => null),
        backtestAPI.getEquityCurve(taskId).catch(() => []),
        backtestAPI.getTrades(taskId).catch(() => []),
      ]);

      const r: Record<string, any> = result || {};
      const eq = Array.isArray(equity) ? equity : [];
      const tr = Array.isArray(trades) ? trades : [];

      btSummary.value = {
        annualReturn: r.annual_return ?? 0,
        totalReturn: r.total_return ?? 0,
        maxDrawdown: r.max_drawdown ?? 0,
        sharpeRatio: r.sharpe_ratio ?? 0,
        winRate: r.win_rate ?? 0,
        profitFactor: r.profit_factor ?? 0,
        tradesCount: r.num_trades ?? tr.length,
        avgTradeReturn: r.avg_trade_return ?? 0,
      };
      btEquityCurve.value = eq.map((p: any) => ({ date: p.trade_date || p.date, value: p.total_assets || p.equity || 0 }));
      btBenchmark.value = (r.benchmark_curve || []).map((p: any) => ({ date: p.trade_date || p.date, value: p.total_assets || (p.cumulative_return ? (1 + p.cumulative_return) * 100000 : p.value || 0) }));
      btDrawdown.value = (r.drawdown_curve || []).map((p: any) => ({ date: p.trade_date || p.date, value: p.drawdown || p.max_drawdown || 0 }));
      btMonthlyReturns.value = (r.monthly_returns || []).map((p: any) => ({ month: p.month || p.trade_date || "", return: p.return || p.monthly_return || 0 }));
      btDailyReturns.value = (r.daily_returns || []).map((p: any) => ({ trade_date: p.trade_date || p.date || "", daily_return: p.daily_return ?? 0, daily_pnl: p.daily_pnl ?? 0 }));
      btDailyTurnover.value = (r.daily_turnover || []).map((p: any) => ({ trade_date: p.trade_date || p.date || "", turnover: p.turnover ?? 0 }));
      btTrades.value = tr.map((t: any) => {
        const side = t.side || t.direction || '';
        const qty = Number(t.volume || t.quantity || 0);
        const px = Number(t.price || 0);
        return {
          id: t.id || t.trade_id,
          symbol: t.symbol || t.ts_code || '',
          name: t.symbol || t.ts_code || '',
          direction: (side === 'LONG' || side === 'buy') ? 'buy' : 'sell',
          date: t.datetime || t.trade_date || t.date || '',
          price: px,
          quantity: qty,
          amount: px * qty,
          fee: 0, // 后端暂不返回手续费明细
        };
      });
    } catch {
      message.error("加载回测结果失败");
    } finally {
      btResultLoading.value = false;
    }
  };

  return {
    // state
    loading, error, saving, isCreateMode, strategyId, strategyName, strategyCode,
    strategyParams, strategyStatus,
    isBacktesting, backtestProgress, backtestStatus, currentTaskId,
    backtestHistory, selectedHistoryTaskId,
    btSummary, btEquityCurve, btBenchmark, btDrawdown, btMonthlyReturns, btDailyReturns, btDailyTurnover, btTrades, btResultLoading,
    // actions
    loadStrategy, saveStrategy, submitBacktest, loadBacktestResult, loadBacktestHistory, clearPolling,
  };
}
