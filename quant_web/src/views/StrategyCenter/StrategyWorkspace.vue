<!-- StrategyWorkspace.vue — 策略工作台：编辑器 + 参数 | 回测结果 -->
<template>
  <div class="strategy-workspace bg-gradient-mesh bg-noise">
    <!-- A. 页头 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <n-button text size="small" @click="router.back()" style="margin-right:8px">
            <template #icon><SmartIcon name="ArrowLeft" /></template>
          </n-button>
          <n-input
            v-model:value="strategyName"
            class="strategy-name-input"
            placeholder="输入策略名称"
            size="small"
            :style="{ maxWidth: '300px', fontWeight: 600, fontSize: '16px' }"
          />
          <n-select
            v-model:value="strategyStatus"
            size="small"
            style="width:160px;margin-left:8px"
            :options="[
              { label: '📝 草稿', value: 'draft' },
              { label: '✅ 已验证', value: 'backtested' },
              { label: '⬜ 已停止', value: 'stopped' },
            ]"
          />
        </div>
        <div class="header-actions">
          <template v-if="isLive">
            <n-button size="small" :type="strategyStatus === 'running' ? 'warning' : 'success'" @click="toggleRun">
              {{ strategyStatus === 'running' ? '停止' : '启动' }}
            </n-button>
            <n-button size="small" @click="loadStrategy" :loading="loading">刷新</n-button>
          </template>
          <template v-else>
            <n-button size="small" :loading="saving" @click="saveStrategy">💾 保存</n-button>
            <n-button size="small" type="primary" :loading="isBacktesting" @click="openBacktestModal = true">
              ⚡ {{ isBacktesting ? `回测中 ${backtestProgress}%` : '回测' }}
            </n-button>
          </template>
          <n-dropdown v-model:show="moreDropdownVisible" trigger="click" :options="moreOptions" @select="handleMoreAction">
            <n-button size="small">⋮</n-button>
          </n-dropdown>
        </div>
      </div>
    </div>

    <!-- B. 主内容 — 左右两栏 -->
    <div class="workspace-body">
      <!-- B1. 左栏 -->
      <div class="left-col">
        <n-card size="small" title="策略代码" :segmented="true">
          <template #header-extra>
            <n-tag :bordered="false" size="tiny" type="info">Python</n-tag>
            <n-tag v-if="isLive" :bordered="false" size="tiny" type="warning" style="margin-left:4px">只读</n-tag>
          </template>
          <CodeEditorPanel
            :code="strategyCode"
            language="python"
            :readonly="isLive"
            @update:code="(v: string) => { if (!isLive) strategyCode = v; }"
            @save="saveStrategy"
          />
        </n-card>

        <n-card size="small" title="策略参数" style="margin-top:12px">
          <n-empty v-if="Object.keys(strategyParams).length === 0" description="无参数" size="small" style="padding:12px 0" />
          <div v-else class="params-grid">
            <div v-for="(val, key) in strategyParams" :key="key" class="param-row">
              <span class="param-label">{{ paramLabel(key) }}</span>
              <!-- v2.6: 类型感知输入 — boolean -->
              <n-switch v-if="typeof val === 'boolean'" :value="val" @update:value="(v: boolean) => setParam(key, v)" size="small" />
              <!-- v2.6: 类型感知输入 — integer -->
              <n-input-number v-else-if="typeof val === 'number' && Number.isInteger(val)" :value="val" @update:value="(v: number | null) => { if (v !== null) setParam(key, v) }" size="small" :step="1" style="width:180px" />
              <!-- v2.6: 类型感知输入 — float -->
              <n-input-number v-else-if="typeof val === 'number'" :value="val" @update:value="(v: number | null) => { if (v !== null) setParam(key, v) }" size="small" :step="0.01" style="width:180px" />
              <!-- v2.6: 类型感知输入 — array/object → JSON 文本 -->
              <n-input v-else-if="typeof val === 'object' && val !== null" :value="getJsonText(key, val)" @update:value="(v: string) => { jsonTexts[key] = v }" @blur="() => parseComplexParam(key)" size="small" style="width:180px" placeholder="JSON" />
              <!-- v2.6: 类型感知输入 — string -->
              <n-input v-else :value="val" @update:value="(v: string) => setParam(key, v)" size="small" style="width:180px" />
            </div>
          </div>
        </n-card>
      </div>

      <!-- B2. 右栏：区分实盘/回测 -->
      <div class="right-col" v-if="isLive">
        <!-- 实盘运行时状态 -->
        <n-card size="small" title="运行状态">
          <div class="runtime-grid">
            <div class="rt-item"><span class="rt-label">运行模式</span><n-tag :bordered="false" type="error" size="tiny">实盘</n-tag></div>
            <div class="rt-item"><span class="rt-label">执行模式</span><n-tag :bordered="false" :type="liveExecutionMode === 'semi_auto' ? 'warning' : 'info'" size="tiny">{{ liveExecutionMode === 'semi_auto' ? '半自动' : '全自动' }}</n-tag></div>
            <div class="rt-item"><span class="rt-label">启动时间</span><span class="rt-value">{{ liveStartedAt || '—' }}</span></div>
            <div class="rt-item"><span class="rt-label">上次心跳</span><span class="rt-value">{{ liveHeartbeat || '—' }}</span></div>
            <div class="rt-item"><span class="rt-label">今日信号</span><span class="rt-value">{{ liveSignalsToday }}</span></div>
            <div class="rt-item"><span class="rt-label">当前持仓</span><span class="rt-value">{{ livePositionsCount }}</span></div>
          </div>
        </n-card>

        <n-card size="small" title="当前持仓" style="margin-top:12px">
          <n-empty v-if="!livePositions.length" description="暂无持仓" size="small" style="padding:12px 0" />
          <div v-else>
            <div v-for="p in livePositions" :key="p.ts_code" class="pos-row">
              <n-tag size="tiny" :bordered="false">{{ p.ts_code }}</n-tag>
              <span class="pos-qty">{{ p.volume || p.quantity }}股</span>
              <span class="pos-pnl" :class="(p.pnl || 0) >= 0 ? 'text-up' : 'text-down'">{{ (p.pnl || 0) >= 0 ? '+' : '' }}{{ (p.pnl || 0).toFixed(2) }}</span>
            </div>
          </div>
        </n-card>

        <n-card size="small" title="最近信号" style="margin-top:12px">
          <n-empty v-if="!liveRecentSignals.length" description="暂无信号" size="small" style="padding:12px 0" />
          <div v-else>
            <div v-for="sig in liveRecentSignals.slice(0, 10)" :key="sig.id" class="sig-row">
              <n-tag size="tiny" :bordered="false" :type="sig.direction === 'LONG' || sig.direction === 'long' ? 'success' : 'error'">{{ sig.direction }}</n-tag>
              <span class="sig-code">{{ sig.ts_code }}</span>
              <span class="sig-price">{{ sig.price?.toFixed(2) }}</span>
              <span class="sig-time">{{ sig.timestamp || sig.generation_time }}</span>
            </div>
          </div>
        </n-card>
      </div>

      <!-- 回测右栏 -->
      <div class="right-col" v-else>
        <template v-if="isBacktesting">
          <n-card size="small" title="回测执行中">
            <n-spin size="medium" />
            <p style="text-align:center;margin:12px 0;color: var(--color-text-secondary)">{{ backtestProgress }}%</p>
            <n-progress type="line" :percentage="Number(backtestProgress)" :height="8" :border-radius="4" />
            <p style="text-align:center;font-size:12px;color:var(--color-text-tertiary);margin-top:8px">{{ backtestStatusText }}</p>
          </n-card>
        </template>
        <template v-else-if="!currentTaskId">
          <n-card size="small">
            <n-empty description="尚未执行回测" style="padding:40px 0">
              <template #extra>
                <n-button size="small" type="primary" @click="openBacktestModal = true">开始回测</n-button>
              </template>
            </n-empty>
          </n-card>
        </template>
        <template v-else>
          <n-spin :show="btResultLoading" size="small">
            <n-card size="small" title="回测结果">
              <template #header-extra>
                <n-select
                  v-if="backtestHistory.length > 0"
                  v-model:value="selectedHistoryTaskId"
                  :options="backtestHistory.map(h => ({ label: h.label, value: h.taskId }))"
                  size="tiny" placeholder="历史回测" style="width:160px"
                  @update:value="(v: string) => loadBacktestResult(v as string)" />
              </template>
              <div class="metrics-row">
                <div class="metric-item"><span class="metric-label">年化收益</span><span class="metric-value" :class="btSummary.annualReturn >= 0 ? 'text-up' : 'text-down'">{{ (btSummary.annualReturn * 100).toFixed(1) }}%</span></div>
                <div class="metric-item"><span class="metric-label">基准收益</span><span class="metric-value" :class="benchmarkReturn >= 0 ? 'text-up' : 'text-down'">{{ (benchmarkReturn * 100).toFixed(1) }}%</span></div>
                <div class="metric-item"><span class="metric-label">夏普比率</span><span class="metric-value">{{ btSummary.sharpeRatio.toFixed(2) }}</span></div>
                <div class="metric-item"><span class="metric-label">最大回撤</span><span class="metric-value text-down">{{ (btSummary.maxDrawdown * 100).toFixed(1) }}%</span></div>
                <div class="metric-item"><span class="metric-label">胜率</span><span class="metric-value">{{ (btSummary.winRate * 100).toFixed(1) }}%</span></div>
                <div class="metric-item"><span class="metric-label">交易笔数</span><span class="metric-value">{{ btSummary.tradesCount }}</span></div>
              </div>
              <BacktestSubplots :equity="btEquityPct" :benchmark="btBenchmarkPct" :dailyReturns="btDailyReturns" :dailyTurnover="btDailyTurnover" :drawdown="btDrawdown" :height="720" />
            </n-card>
          </n-spin>
        </template>
      </div>
    </div>

    <!-- C. 回测配置 Modal -->
    <n-modal v-model:show="openBacktestModal" preset="dialog" title="回测配置" positive-text="开始回测" negative-text="取消"
      @positive-click="handleBacktestSubmit" :loading="isBacktesting">
      <n-form label-width="90px" size="small">
        <n-form-item label="股票池"><n-dynamic-tags v-model:value="btConfig.symbols" /></n-form-item>
        <n-form-item label="开始日期"><n-date-picker v-model:value="btConfig.startDate" type="date" style="width:100%" /></n-form-item>
        <n-form-item label="结束日期"><n-date-picker v-model:value="btConfig.endDate" type="date" style="width:100%" /></n-form-item>
        <n-form-item label="初始资金"><n-input-number v-model:value="btConfig.initialCapital" :min="10000" :step="10000" style="width:100%" /></n-form-item>
        <n-form-item label="基准"><n-select v-model:value="btConfig.benchmark" :options="benchmarkSelectOptions" /></n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, reactive } from "vue";
import { useRouter, useRoute } from "vue-router";
import {
  NButton, NTag, NInput, NInputNumber, NSpin, NProgress, NSwitch,
  NEmpty, NSelect, NModal, NForm, NFormItem, NDatePicker, NDynamicTags, NDropdown, NCard,
  useMessage, useDialog,
} from "naive-ui";
import { useStore } from "vuex";
import SmartIcon from "@/components/common/SmartIcon.vue";
import CodeEditorPanel from "@/components/editors/CodeEditorPanel.vue";
import BacktestSubplots from "@/components/charts/BacktestSubplots.vue";
import TradeTable from "@/components/data/TradeTable.vue";
import strategyAPI from "@/api/strategy";
import { useStrategyWorkspace } from "@/composables/useStrategyWorkspace";
const router = useRouter();
const route = useRoute();
const store = useStore<any>();
const msg = useMessage();
const dialog = useDialog();

const {
  loading, error, saving, strategyName, strategyCode, strategyParams, strategyStatus,
  isBacktesting, backtestProgress, backtestStatus, currentTaskId,
  backtestHistory, selectedHistoryTaskId,
  btSummary, btEquityCurve, btBenchmark, btDrawdown, btMonthlyReturns, btDailyReturns, btDailyTurnover, btTrades, btResultLoading,
  loadStrategy, saveStrategy, submitBacktest, loadBacktestResult, loadBacktestHistory, clearPolling,
} = useStrategyWorkspace();

// v2.4: 参数中英文映射标签
const PARAM_LABELS: Record<string, string> = {
  fast_period: '快线周期', slow_period: '慢线周期', signal_period: '信号线周期',
  volume_ma_period: '成交量均线周期', min_volume: '最小成交量(万)',
  position_ratio: '每次开仓比例', lookback_period: '回看周期',
  entry_threshold: '入场阈值', exit_threshold: '出场阈值',
  rebalance_freq: '调仓频率(天)', top_n: '持仓数量',
  momentum_weight: '动量因子权重', value_weight: '价值因子权重', quality_weight: '质量因子权重',
  model_type: '模型类型', train_window: '训练窗口(天)', predict_window: '预测窗口(天)',
  retrain_freq: '重训频率(天)', seq_len: '序列长度', hidden_dim: '隐藏层维度', epochs: '训练轮数',
  universe: '候选 ETF 池', momentum_windows: '动量窗口', rank_weights: '窗口权重',
  rebalance_frequency: '调仓频率(天)', min_history: '最低数据条数',
  stop_loss: '止损比例(%)', take_profit: '止盈比例(%)', algorithm: '算法类型',
  feature_columns: '特征列', prediction_horizon: '预测周期(天)',
  confidence_threshold: '置信度阈值', retrain_interval: '重训间隔(天)',
  min_training_samples: '最小训练样本数', min_training_sequences: '最小训练序列数',
  batch_size: '批次大小', num_layers: '网络层数', dropout_rate: 'Dropout 比率',
  hidden_units: '隐藏单元数', learning_rate: '学习率', sequence_length: '序列长度',
  target_column: '目标列', d_model: '模型维度', nhead: '注意力头数',
  // V4 主线趋势策略参数
  top_n: '持仓行业数', cooling_period: '冷却期(天)', min_history: '最低数据条数',
  max_sector_limit: '同板块上限',
  trend_weight: '趋势权重', volume_weight: '量价权重', valuation_weight: '估值权重',
  momentum_weights: '动量窗口权重', momentum_accel_short: '加速短窗口',
  momentum_accel_long: '加速长窗口', rs_window: '相对强弱窗口', rs_benchmark: '基准指数代码',
  vol_ratio_short: '量比短窗口', vol_ratio_long: '量比长窗口', vol_price_window: '价量配合窗口',
  turnover_short: '换手短窗口', turnover_long: '换手长窗口',
  pe_percentile_years: 'PE分位回溯年数', pb_percentile_years: 'PB分位回溯年数',
  factor_override: '因子覆写', verbose_logging: '详细日志',
  universe_size: 'ETF 候选数量',
  v4_bull_width_min: 'BULL宽度', v4_bear_width_max: 'BEAR宽度',
  v4_confirm_min_score: '最低得分', v4_confirm_min_trend: '最低趋势分',
  v4_confirm_max_deviation: '最大MA20偏离', v4_confirm_stability_days: '稳定性回溯天数',
  v4_batch_1: '首批仓位', v4_batch_2: '二批仓位', v4_batch_3: '三批仓位',
  v4_batch_2_tolerance: '二批偏离容忍',
  v4_add_threshold_1: '加仓阈值1', v4_add_threshold_2: '加仓阈值2',
  v4_add_size_1: '加仓量1', v4_add_size_2: '加仓量2', v4_position_max: '仓位上限',
  v4_trail_stop_ratio: '移动止损', v4_heavy_stop_ratio: '重仓止损',
  v4_rs_sell_60d: 'RS60阈值', v4_rs_sell_20d: 'RS20阈值',
  v4_exit_cooldown_stop: '止损冷却',
  // 低吸轮动策略参数
  min_daily_volume: '近5日均量(手)', min_yesterday_rise: '昨日最低涨幅',
  min_volume_ratio: '最低量比', roc_threshold: 'ROC阈值',
  buy_below_high_rate: '低吸比率(低于20日新高)', new_stock_days: '新股过滤天数',
  lookback_days: '选股回溯天数', max_positions: '最大持仓数',
  csi500_ma_short: '中证500短期均线', csi500_ma_long: '中证500长期均线',
  csi500_sideways_pct: '震荡市判定阈值',
  bear_max_pos: '下跌市最大持仓', bear_stop_loss: '下跌市止损比例',
  sideways_max_pos: '震荡市最大持仓', rebalance_threshold: '再平衡浮盈阈值',
  regime_source: '行情判定来源',
  // 多资产ETF轮动策略参数
  etf_pool: 'ETF候选池', momentum_days: '动量回归窗口(天)',
  rsrs_window: 'RSRS计算窗口', rsrs_lookback: 'RSRS Beta回溯天数',
  rsrs_beta_window: 'RSRS Beta滚动窗口', volume_check_days: '量异常检测周期(天)',
  volume_threshold: '量异常阈值(倍)', intraday_stop_loss: '日内止损比例',
};
const paramLabel = (key: string) => PARAM_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

// v2.6: 类型感知参数编辑
const setParam = (key: string, value: any) => {
  strategyParams.value = { ...strategyParams.value, [key]: value };
};
const jsonTexts = reactive<Record<string, string>>({});
const getJsonText = (key: string, val: any) => {
  if (!(key in jsonTexts)) jsonTexts[key] = JSON.stringify(val);
  return jsonTexts[key];
};
const parseComplexParam = (key: string) => {
  const raw = jsonTexts[key];
  if (!raw || !raw.trim()) return;
  try {
    const parsed = JSON.parse(raw);
    strategyParams.value = { ...strategyParams.value, [key]: parsed };
    jsonTexts[key] = JSON.stringify(parsed); // normalize
  } catch {
    // JSON 格式错误 → 回退到旧值
    jsonTexts[key] = JSON.stringify(strategyParams.value[key]);
  }
};

// ---- 实盘运行时状态 ----
const isLive = computed(() => {
  const s = store.state.strategy?.strategies?.find((s: any) => s.id === route.params.id);
  return s?.run_mode === "live";
});
const liveExecutionMode = ref("");
const liveStartedAt = ref("");
const liveHeartbeat = ref("");
const liveSignalsToday = ref(0);
const livePositionsCount = ref(0);
const livePositions = ref<any[]>([]);
const liveRecentSignals = ref<any[]>([]);

const loadLiveData = async () => {
  const id = route.params.id as string;
  if (!id) return;
  try {
    // 策略状态
    const status = await strategyAPI.getStrategyStatus(id);
    if (status) {
      liveExecutionMode.value = (status as any).execution_mode || "";
      liveStartedAt.value = (status as any).started_at || "";
    }
    // 持仓
    livePositions.value = await strategyAPI.getStrategyPositions(id) || [];
    livePositionsCount.value = livePositions.value.length;
    // 信号
    const signals = await strategyAPI.getPendingSignals({ strategy_id: id });
    liveRecentSignals.value = signals || [];
    liveSignalsToday.value = signals?.length || 0;
    // 心跳（从 strategy_runs 查询）
    const runs = store.state.strategy?.strategyRuns?.[id];
    if (runs) {
      const hb = runs.state_snapshot?.last_heartbeat;
      if (hb) {
        liveHeartbeat.value = hb.trade_date || hb.updated_at || "";
        liveSignalsToday.value = hb.signals_count || 0;
      }
    }
  } catch (e) { /* ignore */ }
};

const toggleRun = async () => {
  const id = route.params.id as string;
  if (strategyStatus.value === "running") {
    dialog.warning({
      title: "停止确认", content: "确定停止该实盘策略？", positiveText: "停止", negativeText: "取消",
      onPositiveClick: async () => {
        try { await store.dispatch("strategy/stopStrategy", id); msg.success("已停止"); loadStrategy(); }
        catch (e: any) { msg.error("停止失败: " + (e.message || e)); }
      },
    });
  } else {
    // 从 store 读取已保存的账户配置
    const s = store.state.strategy?.strategiesMap?.get(id) || store.state.strategy?.strategies?.find((x: any) => x.id === id);
    const params: any = { run_mode: "live" };
    if (s?.account_id) params.account_id = s.account_id;
    if (s?.allocated_capital > 0) params.capital = s.allocated_capital;
    if (s?.execution_mode) params.execution_mode = s.execution_mode;
    try { await store.dispatch("strategy/startStrategy", { strategyId: id, params }); msg.success("已启动"); loadStrategy(); }
    catch (e: any) { msg.error("启动失败: " + (e.message || e)); }
  }
};

const btActiveTab = ref("equity");

const moreDropdownVisible = ref(false);

// 累计收益率百分比（百分比显示）
const btEquityPct = computed(() => {
  if (!btEquityCurve.value.length) return [];
  const base = btEquityCurve.value[0]?.value || 1;
  return btEquityCurve.value.map((p: any) => ({ date: p.date, value: (p.value / base - 1) * 100 }));
});
const btBenchmarkPct = computed(() => {
  if (!btBenchmark.value.length) return [];
  const base = btBenchmark.value[0]?.value || 1;
  return btBenchmark.value.map((p: any) => ({ date: p.date, value: (p.value / base - 1) * 100 }));
});
// 基准累计收益率（供指标行显示）
const benchmarkReturn = computed(() => {
  if (!btBenchmark.value.length) return 0;
  const base = btBenchmark.value[0]?.value || 1;
  const last = btBenchmark.value[btBenchmark.value.length - 1]?.value || base;
  return last / base - 1;
});

// 回测配置 Modal
const openBacktestModal = ref(false);
const btConfig = ref({
  symbols: [] as string[],
  startDate: Date.now() - 365 * 86400000,
  endDate: Date.now(),
  initialCapital: 1000000,
  benchmark: "000300.SH",
});

const benchmarkSelectOptions = [
  { label: "沪深300", value: "000300.SH" },
  { label: "上证指数", value: "000001.SH" },
  { label: "深证成指", value: "399001.SZ" },
  { label: "中证500", value: "000905.SH" },
  { label: "创业板指", value: "399006.SZ" },
];

const statusTagType = computed(() => {
  const map: Record<string, any> = { running: "success", paused: "info", error: "error", stopped: "warning" };
  return map[strategyStatus.value] || "default";
});

const backtestStatusText = computed(() => {
  const map: Record<string, string> = {
    pending: "排队中...", running: "模拟交易中...",
    data_loading: "加载行情数据...", completed: "已完成",
    failed: "失败", cancelled: "已取消",
  };
  return map[backtestStatus.value] || backtestStatus.value || "等待中...";
});

const moreOptions = [
  { label: "导出策略JSON", key: "export" },
  { label: "查看版本历史", key: "versions" },
  { label: "风控设置", key: "risk" },
];

const handleMoreAction = (key: string) => {
  moreDropdownVisible.value = false;
  if (key === "export") {
    const data = JSON.stringify({ name: strategyName.value, code: strategyCode.value, parameters: strategyParams.value }, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${strategyName.value}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  } else if (key === "versions") {
    router.push(`/strategies/versions/${router.currentRoute.value.params.id}`);
  } else if (key === "risk") {
    router.push(`/strategies/risk/${router.currentRoute.value.params.id || ""}`);
  }
};

const handleBacktestSubmit = () => {
  const start = new Date(btConfig.value.startDate).toISOString().slice(0, 10);
  const end = new Date(btConfig.value.endDate).toISOString().slice(0, 10);
  submitBacktest({
    symbols: btConfig.value.symbols,
    startDate: start,
    endDate: end,
    initialCapital: btConfig.value.initialCapital,
    commissionRate: 0.0003,
    slippageRate: 0.001,
    benchmark: btConfig.value.benchmark,
  });
};

onMounted(() => { loadStrategy(); loadBacktestHistory(); loadLiveData(); });
onBeforeUnmount(() => { clearPolling(); });

</script>

<style lang="scss" scoped>
.strategy-workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

/* ---- 页头 ---- */
.page-header {
  flex-shrink: 0;
  .header-content {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 24px;
  }
  .title-section { display: flex; align-items: center; gap: 4px; }
  .header-actions { display: flex; gap: 6px; }
}

/* ---- 两栏布局 ---- */
.workspace-body {
  flex: 1; overflow: hidden;
  display: grid;
  grid-template-columns: 650px 1fr;
  gap: 12px;
  padding: 0 24px 24px;
  min-height: 0;
}

.left-col {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  :deep(.n-card:first-child) { flex: 1; display: flex; flex-direction: column; min-height: 580px;
    > .n-card__content { flex: 1; display: flex; flex-direction: column; }
  }
}

.right-col {
  overflow-y: auto;
  min-width: 0;
}

/* ---- 参数列表 ---- */
.params-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px 24px;
  .param-row {
    display: grid; grid-template-columns: 100px 1fr; gap: 8px; align-items: center;
    padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
    .param-label { font-size: 12px; color: var(--color-text-tertiary); text-align: right; }
  }
}

/* ---- 指标行 ---- */
.metrics-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 12px; }
.metric-item {
  background: var(--color-bg-secondary, rgba(255,255,255,0.06));
  border-radius: 6px; padding: 8px 6px; text-align: center;
  .metric-label { font-size: 10px; color: var(--color-text-tertiary); display: block; margin-bottom: 2px; }
  .metric-value { font-size: 15px; font-weight: 700; color: var(--color-text-primary); }
}

/* ---- 图表工具栏 ---- */
/* ---- 卡片不透底 ---- */
:deep(.n-card) {
  background: var(--color-bg-solid, #0f1724) !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
}

.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }

/* ---- 实盘运行时网格 ---- */
.runtime-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.rt-item {
  background: var(--color-bg-secondary, rgba(255,255,255,0.06));
  border-radius: 6px; padding: 8px;
  .rt-label { font-size: 10px; color: var(--color-text-tertiary); display: block; margin-bottom: 2px; }
  .rt-value { font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
}

/* ---- 持仓行 ---- */
.pos-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.04);
  .pos-qty { font-size: 12px; color: var(--color-text-secondary); flex: 1; }
  .pos-pnl { font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
}

/* ---- 信号行 ---- */
.sig-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.03); font-size: 12px;
  .sig-code { color: var(--color-text-primary); flex: 1; font-family: monospace; }
  .sig-price { color: var(--color-text-secondary); font-variant-numeric: tabular-nums; }
  .sig-time { color: var(--color-text-tertiary); font-size: 10px; }
}
</style>
