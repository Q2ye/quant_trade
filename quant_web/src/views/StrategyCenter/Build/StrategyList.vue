<!-- StrategyList.vue — Tab 分类：实盘/仿真/回测 + 卡片网格 + 持仓展示 -->
<template>
  <div class="strategy-list bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略构建</h1>
          <p class="page-description">管理策略：回测调优、实盘运行</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="loadStrategies" quaternary><template #icon><SmartIcon name="Refresh" /></template></n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <n-result v-if="pageState === 'error'" status="500" title="加载失败">
        <template #footer><n-button @click="loadStrategies">重试</n-button></template>
      </n-result>

      <!-- Empty -->
      <div v-else-if="pageState === 'empty'" class="empty-state">
        <n-empty description="还没有策略">
          <template #extra>
            <n-button type="primary" size="small" style="margin-top:12px" @click="router.push('/strategies/workspace/new')">新建策略</n-button>
          </template>
        </n-empty>
      </div>

      <template v-else-if="pageState === 'data'">
        <!-- v4.0: 按策略生命周期状态筛选（取消全部，已停止+已淘汰 → 已归档） -->
        <div class="stats-bar">
          <span class="stat-item" :class="{ active: statusFilter === 'draft' }" @click="statusFilter = 'draft'">
            📝 草稿 <strong>{{ statusCounts.draft }}</strong>
          </span>
          <span class="stat-item" :class="{ active: statusFilter === 'backtested' }" @click="statusFilter = 'backtested'">
            ✅ 已验证 <strong>{{ statusCounts.backtested }}</strong>
          </span>
          <span class="stat-item" :class="{ active: statusFilter === 'running' }" @click="statusFilter = 'running'">
            🟢 运行中 <strong>{{ statusCounts.running + (statusCounts.paused || 0) }}</strong>
          </span>
          <span class="stat-item" :class="{ active: statusFilter === 'archived' }" @click="statusFilter = 'archived'">
            📦 已归档 <strong>{{ statusCounts.archived }}</strong>
          </span>
        </div>

        <!-- v4.0: 模板库（仅在"草稿"Tab 显示，新策略起点） -->
        <div v-if="statusFilter === 'draft'">
          <h3 class="section-title">模板库</h3>
          <div v-if="builtinLoading"><n-skeleton :repeat="3" text /></div>
          <div v-else-if="builtinStrategies.length > 0" class="card-grid">
            <div v-for="tpl in builtinStrategies" :key="tpl.id"
              :class="['strategy-card', 'builtin-card']"
              @click="createFromTemplate(tpl)">
              <div class="sc-top">
                <n-tag :type="builtinTypeTag(tpl.template_type || tpl.strategy_type)" size="tiny">{{ builtinTypeLabel(tpl.template_type || tpl.strategy_type) }}</n-tag>
              </div>
              <h4 class="sc-name">{{ builtinDisplayName(tpl) }}</h4>
              <span class="sc-type">{{ builtinDescription(tpl) }}</span>
              <div class="sc-footer">
                <span class="sc-action">使用模板 <SmartIcon name="ArrowRight" /></span>
              </div>
            </div>
          </div>
          <n-empty v-else description="暂无可用模板" size="small" />
        </div>

        <!-- v4.0: 策略卡片（版本分组） -->
        <h3 class="section-title">{{ tabLabel }} ({{ filteredStrategies.length }})</h3>
        <template v-if="filteredStrategies.length > 0">
          <!-- 单组版本（组内 >1 时显示组标题；单版本不分组） -->
          <div v-for="(group, cls) in groupStrategies" :key="cls" class="strategy-group">
            <div v-if="group.length > 1" class="group-header" @click="toggleGroup(cls)">
              <span class="group-toggle">{{ collapsedGroups.has(cls) ? '▸' : '▾' }}</span>
              <span class="group-name">{{ BUILTIN_DISPLAY[cls] || cls }}</span>
              <span class="group-count">({{ group.length }})</span>
            </div>
            <div v-if="!collapsedGroups.has(cls)" class="card-grid">
              <div v-for="s in group" :key="s.id"
                :class="['strategy-card', { selected: checkedKeys.includes(s.id), 'latest-card': isLatestInGroup(group, s) }]"
                @click="handleCardClick(s)">
                <div class="sc-top">
                  <n-tag :type="statusMap[s.status]" size="tiny">{{ statusText[s.status] || s.status }}</n-tag>
                  <n-tag v-if="group.length > 1 && isLatestInGroup(group, s)" type="success" size="tiny" :bordered="false">🆕 最新</n-tag>
                  <n-tag v-if="s.run_mode === 'live'" type="error" size="tiny" :bordered="false">实盘</n-tag>
                  <n-tag v-if="s.execution_mode === 'semi_auto'" type="warning" size="tiny" :bordered="false">半自动</n-tag>
                  <n-tag v-if="s.execution_mode === 'full_auto'" type="info" size="tiny" :bordered="false">全自动</n-tag>
                </div>
                <h4 class="sc-name">{{ s.name || s.id }}</h4>
                <span class="sc-type">{{ s.className || s.strategy_type || '自定义' }}</span>

                <!-- 回测绩效摘要 -->
                <div v-if="strategyPerf[s.id]?.total_return !== undefined" class="sc-perf">
                  <span :class="strategyPerf[s.id].total_return >= 0 ? 'text-up' : 'text-down'">
                    {{ (strategyPerf[s.id].total_return * 100).toFixed(1) }}%
                  </span>
                  <span class="sc-perf-label">总收益</span>
                  <span class="sc-perf-sub">
                    夏普 {{ strategyPerf[s.id].sharpe_ratio?.toFixed(2) || '—' }}
                  </span>
                </div>

                <!-- 持仓摘要 -->
                <div v-if="s.status === 'running' && strategyPositions[s.id]?.length" class="sc-positions">
                  <div class="pos-header">当前持仓</div>
                  <div v-for="p in strategyPositions[s.id].slice(0, 3)" :key="p.ts_code || p.symbol" class="pos-item">
                    <n-tag size="tiny" style="font-size:10px" :bordered="false">{{ p.ts_code || p.symbol }}</n-tag>
                    <span class="pos-qty">{{ p.volume || p.quantity || 0 }}股</span>
                  </div>
                </div>

                <!-- 实盘/仿真运行中额外信息 -->
                <div v-if="s.status === 'running' && s.run_mode === 'live'" class="sc-runtime">
                  <div class="rt-stat" title="策略启动时间">
                    🕐 {{ s.started_at ? new Date(s.started_at).toLocaleDateString() : '—' }}
                  </div>
                </div>

                <div class="sc-actions">
                  <!-- v3.3: 按状态显示操作按钮 -->
                  <template v-for="action in getActions(s.status)" :key="action">
                    <n-button v-if="action === 'edit'" size="tiny" @click.stop="editStrategy(s)">编辑</n-button>
                    <n-button v-else-if="action === 'backtest'" size="tiny" @click.stop="quickBacktest(s)">回测</n-button>
                    <n-button v-else-if="action === 'startLive'" size="tiny" type="success" quaternary @click.stop="quickStart(s)">启动实盘</n-button>
                    <n-button v-else-if="action === 'monitor'" size="tiny" quaternary @click.stop="viewReport(s)">监控</n-button>
                    <n-button v-else-if="action === 'pause'" size="tiny" type="warning" quaternary @click.stop="pauseStrategy(s)">暂停</n-button>
                    <n-button v-else-if="action === 'resume'" size="tiny" type="success" quaternary @click.stop="resumeStrategy(s)">恢复</n-button>
                    <n-button v-else-if="action === 'stop'" size="tiny" type="warning" quaternary @click.stop="stopStrategy(s)">停止</n-button>
                    <n-button v-else-if="action === 'delete'" size="tiny" quaternary @click.stop="deleteStrategy(s)" :loading="deleting.has(s.id)" :disabled="deleting.has(s.id)">{{ deleting.has(s.id) ? '删除中' : '删除' }}</n-button>
                    <n-button v-else-if="action === 'viewLog'" size="tiny" quaternary @click.stop="viewLog(s)">查看日志</n-button>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </template>
        <n-empty v-else :description="`暂无${tabLabel}`" />

        <!-- 批量操作栏（仅回测 Tab） -->
        <div v-if="activeTab === 'backtest' && checkedKeys.length > 0" class="batch-bar">
          <span>已选 {{ checkedKeys.length }} 项</span>
          <n-button size="tiny" @click="batchBacktest">批量回测</n-button>
          <n-button size="tiny" @click="batchDelete">批量删除</n-button>
        </div>
      </template>
    </div>

    <!-- v2.2: 实盘启动弹窗 — 选账户 + 选执行模式 + 设资金 -->
    <n-modal v-model:show="showStartModal" preset="dialog" title="启动实盘"
      positive-text="确认启动" negative-text="取消"
      @positive-click="confirmStart">
      <n-form label-width="90px" size="small">
        <n-form-item label="策略名称">
          <span class="text-secondary">{{ startTarget?.name }}</span>
        </n-form-item>
        <n-form-item label="交易账户" required>
          <n-select v-model:value="startAccountId" :options="accountOptions" placeholder="选择券商账户" style="width:100%" />
        </n-form-item>
        <n-form-item label="可用资金">
          <span class="text-secondary" v-if="selectedAccount">¥{{ (selectedAccount.available_balance || 0).toLocaleString() }}</span>
          <span class="text-muted" v-else>请先选择账户</span>
        </n-form-item>
        <n-form-item label="分配资金" required>
          <n-input-number v-model:value="startCapital" :min="10000" :step="100000" :max="selectedAccount?.available_balance || 999999999" style="width:100%" />
        </n-form-item>
        <n-form-item label="执行模式" required>
          <n-radio-group v-model:value="startExecutionMode">
            <n-radio value="semi_auto">
              <span style="font-weight:600">半自动</span>
              <span style="font-size:11px;color:var(--color-text-tertiary);display:block">
                策略发出信号 → 人工在券商端下单 → 回系统确认成交
              </span>
            </n-radio>
            <n-radio value="full_auto" style="margin-top:8px">
              <span style="font-weight:600">全自动</span>
              <span style="font-size:11px;color:var(--color-text-tertiary);display:block">
                策略发出信号 → 系统自动调用券商接口执行
              </span>
            </n-radio>
          </n-radio-group>
        </n-form-item>
      </n-form>
    </n-modal>
    <!-- v2.3: 内置策略配置弹窗 -->
    <n-modal v-model:show="showBuiltinModal" preset="dialog" title="配置系统策略"
      positive-text="创建并启动" negative-text="取消"
      @positive-click="confirmBuiltinStart">
      <n-form label-width="90px" size="small">
        <n-form-item label="策略名称">
          <n-input v-model:value="builtinForm.name" placeholder="输入策略名称" />
        </n-form-item>
        <n-form-item label="策略类型">
          <span class="text-secondary">{{ builtinForm.strategy_type }}</span>
        </n-form-item>
        <n-form-item label="执行模式" required>
          <n-radio-group v-model:value="builtinForm.execution_mode">
            <n-radio value="semi_auto">半自动（信号→人工确认）</n-radio>
            <n-radio value="full_auto">全自动（信号→直接下单）</n-radio>
          </n-radio-group>
        </n-form-item>
        <n-form-item label="分配资金" required>
          <n-input-number v-model:value="builtinForm.capital" :min="10000" :step="100000" style="width:100%" />
        </n-form-item>
        <n-form-item label="股票池">
          <n-input v-model:value="builtinForm.symbols" placeholder="000001.SZ,600519.SH（逗号分隔）" size="small" />
        </n-form-item>
        <n-form-item v-for="(val, key) in builtinForm.parameters" :key="key" :label="builtinForm.paramLabels[key] || key" size="small">
          <n-input-number v-model:value="builtinForm.parameters[key]" size="tiny" style="width:160px" />
        </n-form-item>
      </n-form>
    </n-modal>


    <!-- 新建/编辑对话框 -->
    <n-modal v-model:show="showDialog" preset="dialog" :title="dialogTitle" positive-text="保存" negative-text="取消"
      @positive-click="saveStrategy">
      <n-form :model="currentStrategy" label-width="80px" size="small">
        <n-form-item label="名称" required><n-input v-model:value="currentStrategy.name" /></n-form-item>
        <n-form-item label="描述"><n-input v-model:value="currentStrategy.description" type="textarea" :rows="2" /></n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="currentStrategy.type" :options="STRATEGY_TYPE_OPTIONS" />
        </n-form-item>
        <n-form-item label="状态">
          <n-select v-model:value="currentStrategy.status" :options="[
            { label: '📝 草稿', value: 'draft' },
            { label: '✅ 已验证(可实盘)', value: 'backtested' },
            { label: '🟢 运行中', value: 'running' },
            { label: '⬜ 已停止', value: 'stopped' },
          ]" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { useStore } from "vuex";
import { useMessage, useDialog, NTag, NButton } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import { STRATEGY_TYPE_OPTIONS } from "./constants";
import { STATUS_TYPE_MAP, STATUS_LABEL_MAP, STATUS_ACTIONS, ARCHIVED_STATUSES } from "@/constants/strategyMeta";
import backtestAPI from "@/api/backtest";
import strategyAPI from "@/api/strategy";
import request from "@/utils/request";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
const route = useRoute();
const store = useStore<any>();

type PageState = "loading" | "error" | "empty" | "data";
const pageState = ref<PageState>("loading");
const showDialog = ref(false);
const isEditing = ref(false);
const currentStrategy = ref({ id: null as any, name: "", description: "", type: "trend", className: "", parameters: {}, status: "draft" });
const checkedKeys = ref<string[]>([]);

const strategyPositions = ref<Record<string, any[]>>({});
const strategyPerf = ref<Record<string, { total_return: number; sharpe_ratio: number }>>({});
const positionsLoading = ref(false);

const strategies = computed(() => store.state.strategy?.strategies || []);

// v4.0: 按策略生命周期状态筛选（取消"全部"，草稿默认；已停止+已淘汰 → 已归档）
const statusFilter = ref<string>("draft");
const _filterInitialized = ref(false);
const statusCounts = computed(() => {
  const c: Record<string, number> = { draft: 0, backtested: 0, running: 0, paused: 0, stopped: 0, error: 0, archived: 0, retired: 0 };
  for (const s of strategies.value) {
    const st = s.status || "draft";
    c[st] = (c[st] || 0) + 1;
    if (ARCHIVED_STATUSES.includes(st)) c.archived = (c.archived || 0) + 1;
  }
  return c;
});
const filteredStrategies = computed(() => {
  const list = strategies.value;
  switch (statusFilter.value) {
    case "archived":
      return list.filter((s: any) => ARCHIVED_STATUSES.includes(s.status));
    case "running":
      return list.filter((s: any) => s.status === "running" || s.status === "paused");
    default:
      return list.filter((s: any) => s.status === statusFilter.value);
  }
});
const getActions = (status: string) => STATUS_ACTIONS[status] || [];

const liveCount = computed(() => strategies.value.filter((s: any) => s.run_mode === "live").length);
const backtestCount = computed(() => strategies.value.filter((s: any) => !s.run_mode || s.run_mode === "backtest").length);
// v3.3: 兼容旧模板引用
const activeTab = computed(() => statusFilter.value === "running" ? "live" : "backtest");
const tabLabel = computed(() => {
  if (statusFilter.value === "archived") return "已归档";
  return STATUS_LABEL_MAP[statusFilter.value] || "策略";
});

// v4.0: 版本分组 — 按 class_name 分组，最新版 🆕 徽标，组内可折叠
const versionNum = (s: any): number => {
  const m = (s.name || "").match(/[-_]v?(\d+(?:\.\d+)*)/i);
  return m ? parseFloat(m[1]) : 0;
};
const isLatestInGroup = (group: any[], s: any): boolean => {
  return group.every((g: any) => new Date(s.created_at) >= new Date(g.created_at));
};
const groupStrategies = computed(() => {
  const groups: Record<string, any[]> = {};
  for (const s of filteredStrategies.value) {
    const key = (s as any).class_name || (s as any).className || "未分类";
    (groups[key] = groups[key] || []).push(s);
  }
  // 组内按版本号降序，再按 created_at 降序
  for (const key in groups) {
    groups[key].sort((a: any, b: any) =>
      versionNum(b) - versionNum(a) ||
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }
  return groups;
});
const collapsedGroups = ref<Set<string>>(new Set());
const toggleGroup = (key: string) => {
  const next = new Set(collapsedGroups.value);
  next.has(key) ? next.delete(key) : next.add(key);
  collapsedGroups.value = next;
};

const dialogTitle = computed(() => isEditing.value ? "编辑策略" : "新建策略");

const statusMap = STATUS_TYPE_MAP;
const statusText = STATUS_LABEL_MAP;

// 系统策略 — 从 Registry 加载
const builtinStrategies = ref<any[]>([]);
const builtinLoading = ref(false);

// 内置策略中文映射
const BUILTIN_META: Record<string, { name: string; desc: string; params?: Record<string,string> }> = {
  MLStrategy: { name: '机器学习策略', desc: '基于随机森林、XGBoost 等传统 ML 算法的交易策略。',
    params: { model_type: '模型类型', train_window: '训练窗口(天)', predict_window: '预测窗口(天)',
      top_n: '持仓数量', retrain_freq: '重训频率(天)', stop_loss: '止损比例(%)',
      take_profit: '止盈比例(%)', feature_columns: '特征列', prediction_horizon: '预测周期(天)',
      confidence_threshold: '置信度阈值', min_training_samples: '最小训练样本数' } },
  DLStrategy: { name: '深度学习策略', desc: '基于 LSTM、Transformer 等深度学习模型的交易策略。',
    params: { model_type: '模型类型(LSTM/Transformer)', seq_len: '序列长度',
      hidden_dim: '隐藏层维度', epochs: '训练轮数', top_n: '持仓数量',
      batch_size: '批次大小', num_layers: '网络层数', dropout_rate: 'Dropout 比率',
      hidden_units: '隐藏单元数', learning_rate: '学习率', sequence_length: '序列长度',
      stop_loss: '止损比例(%)', take_profit: '止盈比例(%)' } },
    IndustryRotationStrategy: { name: '主线趋势策略 V4', desc: '申万31行业多因子评分(趋势55%+资金30%+估值15%)，市场三态分类，三层入场确认，趋势断裂+移动止损出场。',
    params: { rebalance_frequency: '调仓频率(天)', cooling_period: '冷却期(天)', min_history: '最低数据条数', max_sector_limit: '同板块上限',
      stop_loss: '硬止损比例', trend_weight: '趋势权重', volume_weight: '量价权重', valuation_weight: '估值权重',
      momentum_windows: '动量窗口', momentum_weights: '动量权重',
      v4_bull_width_min: 'BULL宽度', v4_bear_width_max: 'BEAR宽度',
      v4_confirm_min_score: '最低得分', v4_confirm_min_trend: '最低趋势分', v4_confirm_max_deviation: '最大MA20偏离',
      v4_batch_1: '首批仓位', v4_batch_2: '二批仓位', v4_batch_3: '三批仓位',
      v4_add_threshold_1: '加仓阈值1', v4_add_threshold_2: '加仓阈值2',
      v4_add_size_1: '加仓量1', v4_add_size_2: '加仓量2', v4_position_max: '仓位上限',
      v4_trail_stop_ratio: '移动止损', v4_heavy_stop_ratio: '重仓止损',
      v4_rs_sell_60d: 'RS60阈值', v4_rs_sell_20d: 'RS20阈值',
      factor_override: '因子覆写', verbose_logging: '详细日志' } },
    StockLowHighStrategy: { name: '低吸轮动策略', desc: '沪深主板强势股低吸轮动，全市场扫描选股+三档行情风控+半仓轮动。',
    params: { universe: '股票池范围', min_daily_volume: '近5日均量(手)', min_yesterday_rise: '昨日最低涨幅',
      min_volume_ratio: '最低量比', roc_threshold: 'ROC阈值',
      buy_below_high_rate: '低吸比率(低于20日新高)', new_stock_days: '新股过滤天数',
      lookback_days: '选股回溯天数', rebalance_frequency: '调仓频率(天)',
      max_positions: '最大持仓数', stop_loss: '止损比例',
      csi500_ma_short: '中证500短期均线', csi500_ma_long: '中证500长期均线',
      csi500_sideways_pct: '震荡市判定阈值',
      bear_max_pos: '下跌市最大持仓', bear_stop_loss: '下跌市止损比例',
      sideways_max_pos: '震荡市最大持仓', rebalance_threshold: '再平衡浮盈阈值',
      regime_source: '行情判定来源', verbose_logging: '详细日志' } },
};
// v4.0: class_name → 组标题中文名（复用 BUILTIN_META，未命中回退类名）
const BUILTIN_DISPLAY: Record<string, string> = Object.fromEntries(
  Object.entries(BUILTIN_META).map(([cls, meta]: [string, any]) => [cls, meta.name])
);
// v3.0: 从模板 code_template 提取 class_name 用于 BUILTIN_META 查表
const extractClassName = (tpl: any) => {
  const code = tpl.code_template || '';
  const m = code.match(/class\s+(\w+)\s*[(:]/);
  return m?.[1] || tpl.class_name || '';
};
const builtinDisplayName = (tpl: any) => {
  const cn = extractClassName(tpl);
  return BUILTIN_META[cn]?.name || (tpl.template_name || tpl.name || '').replace(/^内置策略:\s*/, '') || cn;
};
const builtinDescription = (tpl: any) => {
  const cn = extractClassName(tpl);
  // 优先 BUILTIN_META，其次 DB 描述（去掉"内置策略:"前缀），最后为空
  const dbDesc = (tpl.description || '').replace(/^内置策略:\s*/, '');
  return BUILTIN_META[cn]?.desc || dbDesc || tpl.module || '';
};
const builtinTypeLabel = (type: string) => {
  const m: Record<string, string> = { technical: '趋势跟踪', alpha: 'Alpha', ml: '机器学习', dl: '深度学习', rotation: '行业轮动' };
  return m[type] || type || '未知';
};
const builtinTypeTag = (type: string) => {
  const m: Record<string, string> = { technical: 'success', alpha: 'info', ml: 'error', dl: 'error', rotation: 'warning' };
  return (m[type] || 'default') as any;
};

const createFromTemplate = (tpl: any) => {
  // v3.0: 跳转模板详情页，不自动创建
  router.push('/strategies/template/' + tpl.id);
};

// ---- 内置策略配置弹窗 ----
const showBuiltinModal = ref(false);
const builtinTarget = ref<any>(null);
const builtinForm = reactive({
  name: '',
  strategy_type: '',
  execution_mode: 'semi_auto' as string,
  account_id: '',
  capital: 1_000_000,
  symbols: '000001.SZ,600519.SH',
  parameters: {} as Record<string, any>,
  paramLabels: {} as Record<string, string>,
});

const openBuiltinConfig = (tpl: any) => {
  // v3.0: 跳转模板详情页（"使用"按钮 → 详情页创建实例）
  router.push('/strategies/template/' + tpl.id);
};

const confirmBuiltinStart = async () => {
  const tpl = builtinTarget.value;
  if (!tpl) return;
  try {
    // v3.0: 统一从模板创建实例
    const tplId = tpl.id;
    const createRes = await request.post(`/quantTrade/strategy/templates/${tplId}/create-instance`, {
      name: builtinForm.name,
      account_id: builtinForm.account_id,
      capital: builtinForm.capital,
      run_mode: 'live',
    }).then((r: any) => r.data?.data || r.data);
    if (!createRes?.id) { message.error('创建失败'); return; }
    const sid = createRes.id;
    message.success("实例已创建");

    // 2. 启动策略
    await request.post(`/quantTrade/strategy/${sid}/start`, {
      capital: builtinForm.capital,
      run_mode: 'live',
      execution_mode: builtinForm.execution_mode,
    });
    message.success("策略已启动: " + builtinForm.name);
    showBuiltinModal.value = false;
    loadStrategies();
  } catch (e: any) { message.error("启动失败: " + (e.message || e)); }
};

const quickBacktestBuiltin = (tpl: any) => {
  // v3.0: 跳转模板详情页
  router.push('/strategies/template/' + tpl.id);
};
const handleCardClick = (s: any) => { openWorkspace(s); };
const toggleCheck = (id: string) => {
  if (checkedKeys.value.includes(id)) checkedKeys.value = checkedKeys.value.filter(k => k !== id);
  else checkedKeys.value.push(id);
};

const openWorkspace = (s: any) => {
  if (!s?.id) { message.warning("策略数据异常"); return; }
  router.push(`/strategies/workspace/${s.id}`);
};
const quickBacktest = (s: any) => router.push(`/backtest?strategies=${s.id}`);
const viewReport = async (s: any) => {
  try {
    const tasks: any = await backtestAPI.getTasks({ strategy_id: s.id, status: "completed", page_size: 1 });
    const items = Array.isArray(tasks) ? tasks : (tasks?.data || tasks?.items || []);
    const latest = items.find((t: any) => t.status === "completed") || items[0];
    if (latest) router.push({ name: "BacktestReport", params: { taskId: latest.task_id || latest.id } });
    else message.warning("暂无已完成回测");
  } catch { message.error("查询失败"); }
};
  // v2.2: 实盘启动弹窗状态（含账户选择）
  const showStartModal = ref(false);
  const startTarget = ref<any>(null);
  const startExecutionMode = ref<"semi_auto" | "full_auto">("semi_auto");
  const startCapital = ref<number>(1000000);
  const startAccountId = ref<string | null>(null);
  const accountOptions = ref<any[]>([]);
  const accounts = ref<any[]>([]);

  const selectedAccount = computed(() =>
    accounts.value.find((a: any) => a.id === startAccountId.value)
  );

  const loadAccounts = async () => {
    try {
      const res = await request.get("/quantTrade/account/list", { params: { page: 1, page_size: 100, status: "active" } });
      accounts.value = (res?.data?.data || res?.data || []);
      accountOptions.value = accounts.value.map((a: any) => ({
        label: `${a.broker || ''} ${a.account_name || a.account_number || a.id}`,
        value: a.id,
      }));
    } catch { accounts.value = []; }
  };

  const quickStart = async (s: any) => {
    // 已配置过账户 → 一键重启，否则弹出配置弹窗
    if (s.account_id && s.allocated_capital > 0) {
      try {
        await store.dispatch("strategy/startStrategy", {
          strategyId: s.id,
          params: {
            run_mode: "live",
            execution_mode: s.execution_mode || "semi_auto",
            capital: s.allocated_capital,
            account_id: s.account_id,
          },
        });
        message.success("已启动实盘");
        await loadStrategies();
      } catch (e: any) { message.error("启动失败: " + (e.message || e)); }
    } else {
      openStartModal(s);
    }
  };

  const openStartModal = (s: any) => {
    startTarget.value = s;
    startExecutionMode.value = "semi_auto";
    startCapital.value = s.allocated_capital > 0 ? parseFloat(s.allocated_capital) : 1000000;
    startAccountId.value = s.account_id || null;
    loadAccounts();
    showStartModal.value = true;
  };

  const confirmStart = async () => {
    if (!startTarget.value) return;
    try {
      await store.dispatch("strategy/startStrategy", {
        strategyId: startTarget.value.id,
        params: {
          run_mode: "live",
          execution_mode: startExecutionMode.value,
          capital: startCapital.value,
          account_id: startAccountId.value,
        },
      });
      message.success(
        startExecutionMode.value === "semi_auto" ? "已启动实盘（半自动）" : "已启动实盘（全自动）"
      );
      showStartModal.value = false;
      await loadStrategies();
    } catch (e: any) {
      message.error("启动失败: " + (e.message || e));
    }
  };

  const stopStrategy = async (s: any) => {
    try {
      await store.dispatch("strategy/stopStrategy", s.id);
      message.success("已停止");
      await loadStrategies();
    } catch (e: any) { message.error("停止失败: " + e.message); }
  };
const cloneStrategy = async (s: any) => {
  try {
    await store.dispatch("strategy/cloneStrategy", { id: s.id, newName: s.name + "_副本" });
    message.success(`已克隆`); loadStrategies();
  } catch (e: any) { message.error("克隆失败: " + (e.message || e)); }
};
const handleClone = cloneStrategy;
const deleting = ref<Set<string>>(new Set());
const deleteStrategy = (s: any) => {
  // 防止重复点击：已在删除中则直接返回
  if (deleting.value.has(s.id)) return;
  const dlg = dialog.warning({
    title: "删除确认", content: `确定删除"${s.name}"？不可撤销。`, positiveText: "删除", negativeText: "取消",
    onPositiveClick: async () => {
      dlg.destroy();  // 立即关闭弹窗，避免用户重复点击
      deleting.value.add(s.id);
      try { await store.dispatch("strategy/deleteStrategy", s.id); message.success("已删除"); loadStrategies(); }
      catch (e: any) { message.error("删除失败"); }
      finally { deleting.value.delete(s.id); }
    },
  });
};

// v3.3 新增：状态流转操作
const editStrategy = (s: any) => router.push(`/strategies/workspace/${s.id}`);
const pauseStrategy = async (s: any) => {
  try { await request.post(`/quantTrade/strategy/${s.id}/pause`); message.success('已暂停'); await loadStrategies(); }
  catch { message.error('暂停失败'); }
};
const resumeStrategy = async (s: any) => {
  try { await request.post(`/quantTrade/strategy/${s.id}/resume`); message.success('已恢复'); await loadStrategies(); }
  catch { message.error('恢复失败'); }
};
const viewLog = (s: any) => { message.info('日志查看功能开发中'); };

const batchBacktest = () => { if (checkedKeys.value.length) router.push(`/backtest?strategies=${checkedKeys.value.join(",")}`); };
const batchDelete = () => {
  const dlg = dialog.warning({
    title: "批量删除", content: `确定删除 ${checkedKeys.value.length} 个策略？`, positiveText: "删除", negativeText: "取消",
    onPositiveClick: async () => {
      dlg.destroy();
      for (const id of checkedKeys.value) { try { await store.dispatch("strategy/deleteStrategy", id); } catch { } }
      message.success("已删除"); checkedKeys.value = []; loadStrategies();
    },
  });
};

const saveStrategy = async () => {
  try {
    if (isEditing.value) await store.dispatch("strategy/updateStrategy", currentStrategy.value);
    else await store.dispatch("strategy/createStrategy", currentStrategy.value);
    showDialog.value = false; loadStrategies(); message.success("保存成功");
  } catch (e: any) { message.error("保存失败"); }
};

const loadBuiltin = async () => {
  try {
    builtinLoading.value = true;
    // v3.0: 从模板 API 加载（DB 中的 strategy_templates 表）
    const res = await request.get('/quantTrade/strategy/templates', { params: { is_builtin: true, page_size: 50 } })
      .then((r: any) => r?.data || []);
    console.log('[StrategyList] 模板库:', res?.length || 0, '个', res);
    builtinStrategies.value = res || [];
  } catch (e) {
    // 回退到旧 builtin API
    try {
      const res = await strategyAPI.getBuiltinStrategies();
      builtinStrategies.value = res || [];
    } catch (e2) {
      console.error('[StrategyList] 模板加载失败:', e2);
      builtinStrategies.value = [];
    }
  } finally {
    builtinLoading.value = false;
  }
};

const loadStrategies = async () => {
  pageState.value = "loading";
  try {
    await Promise.all([store.dispatch("strategy/loadStrategies"), loadBuiltin()]);
    pageState.value = "data";

    // v4.0: 默认选中"草稿"Tab（新策略起点 + 模板引导）；有运行中时切运行中
    if (!route.query.tab && !_filterInitialized.value) {
      statusFilter.value = liveCount.value > 0 ? "running" : "draft";
      _filterInitialized.value = true;
    }

    // 加载运行中策略的持仓
    const running = strategies.value.filter((s: any) => s.status === "running");
    if (running.length > 0) {
      const results = await Promise.allSettled(
        running.map((s: any) => strategyAPI.getStrategyPositions(s.id).catch(() => []))
      );
      results.forEach((r: any, i: number) => { if (r.status === "fulfilled") strategyPositions.value[running[i].id] = r.value || []; });
    }

    // 加载回测结果（显示绩效摘要）
    const withResults = strategies.value.filter((s: any) => s.run_mode === "backtest" || !s.run_mode);
    if (withResults.length > 0) {
      const perfResults = await Promise.allSettled(
        withResults.map((s: any) =>
          backtestAPI.getTasks({ strategy_id: s.id, status: "completed", page_size: 1 }).catch(() => [])
        )
      );
      perfResults.forEach((r: any, i: number) => {
        if (r.status === "fulfilled") {
          const tasks: any = r.value;
          const items = Array.isArray(tasks) ? tasks : (tasks?.data || tasks?.items || []);
          const latest = items.find((t: any) => t.status === "completed") || items[0];
          if (latest) {
            const perf = latest.result?.total_return !== undefined
              ? { total_return: latest.result.total_return, sharpe_ratio: latest.result.sharpe_ratio || 0 }
              : latest.total_return !== undefined
                ? { total_return: latest.total_return, sharpe_ratio: latest.sharpe_ratio || 0 }
                : null;
            if (perf) strategyPerf.value[withResults[i].id] = perf;
          }
        }
      });
    }
  } catch { pageState.value = "error"; }
};

onMounted(() => loadStrategies());
</script>

<style lang="scss" scoped>
.strategy-list { height: 100%; overflow-y: auto; background: transparent; }
.main-content { padding: 12px 19px 24px; }

.empty-state { padding: 40px 0; text-align: center; }

/* 统计条 — 可点击切换 Tab */
.stats-bar { display: flex; gap: 0; margin-bottom: 14px; border-radius: 8px; overflow: hidden; background: var(--color-bg-card, rgba(12,18,32,0.5)); }
.stat-item { flex: 1; text-align: center; padding: 10px 8px; font-size: 13px; color: var(--color-text-tertiary); cursor: pointer; transition: all 0.15s; border-bottom: 2px solid transparent;
  strong { display: block; font-size: 20px; color: var(--color-text-primary); margin-top: 2px; }
  &:hover { background: rgba(124,111,247,0.05); color: var(--color-text-secondary); }
  &.active { color: var(--color-text-primary); border-bottom-color: var(--color-primary, #7C3AED); background: rgba(124,111,247,0.08); }
}

/* 模板 */
.tpl-section { margin-bottom: 14px; }
.section-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 0 0 8px; }
.tpl-row { display: flex; gap: 10px; flex-wrap: wrap; }
.tpl-card { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 8px; background: var(--color-bg-card, rgba(12,18,32,0.6)); border: 1px solid rgba(255,255,255,0.06); cursor: pointer; transition: all 0.2s;
  &:hover { border-color: var(--color-primary, #7C3AED); transform: translateY(-1px); }
  .tpl-name { font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
  .tpl-desc { font-size: 11px; color: var(--color-text-tertiary); }
}

/* 卡片 */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 14px; }
.strategy-card { padding: 14px; border-radius: 8px; cursor: pointer; transition: all 0.15s; position: relative; z-index: 1;
  background: var(--color-bg-card, rgba(12,18,32,0.6)); border: 1px solid rgba(255,255,255,0.05);
  &:hover { border-color: rgba(124,111,247,0.3); }
  &.selected { border-color: var(--color-primary, #7C3AED); background: rgba(124,111,247,0.08); }
}
.sc-top { display: flex; gap: 6px; align-items: center; margin-bottom: 8px; }
.sc-name { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 0 0 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-type { font-size: 11px; color: var(--color-text-tertiary); display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.5; min-height: calc(11px * 1.5 * 3); }
.builtin-hint { margin: 6px 0 0; font-size: 11px; color: var(--color-text-quaternary); opacity: 0.7; }
.sc-footer { margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: flex-end; }
.sc-action { font-size: 12px; color: var(--color-text-tertiary); display: inline-flex; align-items: center; gap: 4px; transition: color 0.15s; cursor: pointer;
  .strategy-card:hover & { color: var(--n-color-primary, #7c6ff7); }
}

.sc-perf { margin-top: 8px; display: flex; align-items: baseline; gap: 6px;
  span:first-child { font-size: 16px; font-weight: 700; }
  .sc-perf-label { font-size: 10px; color: var(--color-text-tertiary); }
  .sc-perf-sub { font-size: 10px; color: var(--color-text-tertiary); margin-left: 4px; }
}

.sc-positions { margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.04);
  .pos-header { font-size: 10px; color: var(--color-text-tertiary); margin-bottom: 3px; }
  .pos-item { display: flex; align-items: center; gap: 4px; margin-bottom: 2px; }
  .pos-qty { font-size: 11px; color: var(--color-text-secondary); }
}

.sc-runtime { margin-top: 6px;
  .rt-stat { font-size: 10px; color: var(--color-text-tertiary); }
}

.sc-actions { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.04); }

.batch-bar { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; background: var(--color-bg-card, rgba(12,18,32,0.6)); font-size: 13px; color: var(--color-text-secondary); }

.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }

/* v4.0: 版本分组 */
.strategy-group { margin-bottom: 12px; }
.group-header { display: flex; align-items: center; gap: 6px; padding: 8px 4px; cursor: pointer; user-select: none; font-size: 13px; color: var(--color-text-primary); transition: color 0.15s;
  &:hover { color: var(--color-primary, #7C3AED); }
}
.group-toggle { font-size: 11px; color: var(--color-text-tertiary); width: 12px; }
.group-name { font-weight: 600; }
.group-count { font-size: 11px; color: var(--color-text-tertiary); }
.latest-card { border-color: var(--color-primary, #7C3AED) !important; }
</style>
