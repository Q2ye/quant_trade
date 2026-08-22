<template>
  <div class="template-detail bg-gradient-mesh bg-noise">
    <!-- Loading -->
    <n-spin v-if="loading" size="large" class="center-spin"/>

    <!-- Error -->
    <n-result v-else-if="error" status="500" title="加载失败" :description="error">
      <template #footer>
        <n-button @click="load">重试</n-button>
      </template>
    </n-result>

    <!-- 404 -->
    <n-result v-else-if="!template" status="404" title="模板不存在" description="该模板可能已被删除"/>

    <!-- Data -->
    <template v-else>
      <div class="page-header">
        <div class="header-content">
          <div class="title-section">
            <div>
              <h1 class="page-title">{{ displayName }}</h1>
              <p class="page-description">
                <n-tag :type="builtinTypeTag(template.template_type)" size="tiny">
                  {{ builtinTypeLabel(template.template_type) }}
                </n-tag>
                <n-tag v-if="template.is_builtin" type="info" size="tiny" :bordered="false" style="margin-left:4px">
                  内置
                </n-tag>
              </p>
            </div>
          </div>
          <div class="header-actions">
            <n-button class="action-btn" @click="load" quaternary>
              <template #icon>
                <Icon icon="material-symbols:refresh"/>
              </template>
            </n-button>
            <n-button class="action-btn" @click="router.back()" quaternary>
              <template #icon>
                <Icon icon="material-symbols:arrow-back"/>
              </template>
            </n-button>
          </div>
        </div>
      </div>

      <div class="main-content">
        <div class="td-body">
          <!-- 左栏: 代码预览 -->
          <div class="td-left">
            <n-card title="策略代码" size="small" class="code-card">
              <CodeEditorPanel
                  :code="template.code_template || ''"
                  language="python"
                  :read-only="true"
                  class="td-editor"
              />
            </n-card>
          </div>

          <!-- 右栏: 信息 + 参数 + 创建 -->
          <div class="td-right">
            <!-- 模板信息 -->
            <n-card title="模板信息" size="small">
              <n-descriptions :column="1" label-placement="left" size="small">
                <n-descriptions-item label="类型">{{ builtinTypeLabel(template.template_type) }}</n-descriptions-item>
                <n-descriptions-item label="分类">{{ template.category || '-' }}</n-descriptions-item>
                <n-descriptions-item label="描述">{{ displayDesc || '暂无描述' }}</n-descriptions-item>
              </n-descriptions>
            </n-card>

            <!-- 策略参数 -->
            <n-card title="策略参数" size="small" v-if="paramEntries.length > 0">
              <n-form label-placement="left" size="small">
                <n-grid :cols="2" :x-gap="12">
                  <n-form-item-gi v-for="p in paramEntries" :key="p.key" :label="p.label">
                    <!-- v2.6: 类型感知输入 — boolean -->
                    <n-switch
                        v-if="p.valueType === 'boolean'"
                        :value="overrideParams[p.key] ?? p.value"
                        @update:value="(v: boolean) => { overrideParams = { ...overrideParams, [p.key]: v } }"
                        size="small"
                    />
                    <!-- v2.6: 类型感知输入 — integer -->
                    <n-input-number
                        v-else-if="p.valueType === 'integer'"
                        :value="overrideParams[p.key] ?? p.value"
                        @update:value="(v: number | null) => { if (v !== null) overrideParams = { ...overrideParams, [p.key]: v } }"
                        size="small" :step="1" style="width:100%"
                        :placeholder="String(p.value)"
                    />
                    <!-- v2.6: 类型感知输入 — float -->
                    <n-input-number
                        v-else-if="p.valueType === 'float'"
                        :value="overrideParams[p.key] ?? p.value"
                        @update:value="(v: number | null) => { if (v !== null) overrideParams = { ...overrideParams, [p.key]: v } }"
                        size="small" :step="0.01" style="width:100%"
                        :placeholder="String(p.value)"
                    />
                    <!-- v2.6: 类型感知输入 — array/object → JSON -->
                    <n-input
                        v-else-if="p.valueType === 'array' || p.valueType === 'object'"
                        :value="getJsonText(p.key, overrideParams[p.key] ?? p.value)"
                        @update:value="(v: string) => { jsonTexts[p.key] = v }"
                        @blur="() => parseJsonParam(p.key)"
                        size="small" placeholder="JSON"
                    />
                    <!-- v2.6: 类型感知输入 — string -->
                    <n-input
                        v-else
                        :value="overrideParams[p.key] ?? p.value"
                        @update:value="(v: string) => { overrideParams = { ...overrideParams, [p.key]: v } }"
                        size="small"
                        :placeholder="String(p.value)"
                    />
                  </n-form-item-gi>
                </n-grid>
              </n-form>
            </n-card>

            <!-- 创建策略 -->
            <n-card title="创建策略实例" size="small">
              <n-form label-placement="top" size="small">
                <n-form-item label="实例名称">
                  <n-input v-model:value="instanceName" placeholder="留空自动使用模板名"/>
                </n-form-item>
              </n-form>
              <n-button
                  type="primary"
                  block
                  :loading="creating"
                  @click="handleCreateInstance"
                  style="margin-bottom:8px"
              >
                创建策略实例
              </n-button>
              <n-button
                  type="info"
                  block
                  secondary
                  :loading="quickBacktesting"
                  @click="handleQuickBacktest"
              >
                ⚡ 快速回测
              </n-button>
              <p class="td-hint">快速回测不创建策略，验证效果满意后再保存为正式策略。</p>
            </n-card>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {computed, onMounted, reactive, ref} from 'vue';
import {useRoute, useRouter} from 'vue-router';
import {useMessage, NDescriptions, NDescriptionsItem} from 'naive-ui';
import {Icon} from '@iconify/vue';
import request from '@/utils/request';
import CodeEditorPanel from '@/components/editors/CodeEditorPanel.vue';

const route = useRoute();
const router = useRouter();
const message = useMessage();

const loading = ref(true);
const error = ref('');
const creating = ref(false);
const quickBacktesting = ref(false);
const template = ref<any>(null);
const instanceName = ref('');
const overrideParams = ref<Record<string, any>>({});

// v3.0: 内置策略中文映射（class_name → 中文名+描述+参数标签）
const BUILTIN_META: Record<string, { name: string; desc: string; params?: Record<string, string> }> = {
  MLStrategy: {
    name: '机器学习策略', desc: '基于随机森林、XGBoost 等传统 ML 算法的交易策略。',
    params: {
      model_type: '模型类型',
      train_window: '训练窗口(天)',
      predict_window: '预测窗口(天)',
      top_n: '持仓数量',
      retrain_freq: '重训频率(天)'
    }
  },
  DLStrategy: {
    name: '深度学习策略', desc: '基于 LSTM、Transformer 等深度学习模型的交易策略。',
    params: {
      model_type: '模型类型(LSTM/Transformer)',
      seq_len: '序列长度',
      hidden_dim: '隐藏层维度',
      epochs: '训练轮数',
      top_n: '持仓数量'
    }
  },
  IndustryRotationStrategy: {
    name: '主线趋势策略 V4',
    desc: '申万31行业多因子评分(趋势55%+资金30%+估值15%)，市场三态分类，三层入场确认，趋势断裂+移动止损出场。',
    params: {
      rebalance_frequency: '调仓频率(天)',
      cooling_period: '冷却期(天)',
      min_history: '最低数据条数',
      max_sector_limit: '同板块上限',
      stop_loss: '硬止损比例',
      trend_weight: '趋势权重',
      volume_weight: '量价权重',
      valuation_weight: '估值权重',
      momentum_windows: '动量窗口',
      momentum_weights: '动量权重',
      v4_bull_width_min: 'BULL宽度',
      v4_bear_width_max: 'BEAR宽度',
      v4_confirm_min_score: '最低得分',
      v4_confirm_min_trend: '最低趋势分',
      v4_confirm_max_deviation: '最大MA20偏离',
      v4_batch_1: '首批仓位',
      v4_batch_2: '二批仓位',
      v4_batch_3: '三批仓位',
      v4_add_threshold_1: '加仓阈值1',
      v4_add_threshold_2: '加仓阈值2',
      v4_add_size_1: '加仓量1',
      v4_add_size_2: '加仓量2',
      v4_position_max: '仓位上限',
      v4_trail_stop_ratio: '移动止损',
      v4_heavy_stop_ratio: '重仓止损',
      v4_rs_sell_60d: 'RS60阈值',
      v4_rs_sell_20d: 'RS20阈值',
      factor_override: '因子覆写',
      verbose_logging: '详细日志'
    }
  },
  StockLowHighStrategy: {
    name: '低吸轮动策略',
    desc: '沪深主板强势股低吸轮动，全市场扫描选股+三档行情风控+半仓轮动。',
    params: {
      universe: '股票池范围',
      min_daily_volume: '近5日均量(手)',
      min_yesterday_rise: '昨日最低涨幅',
      min_volume_ratio: '最低量比',
      roc_threshold: 'ROC阈值',
      buy_below_high_rate: '低吸比率(低于20日新高)',
      new_stock_days: '新股过滤天数',
      lookback_days: '选股回溯天数',
      max_positions: '最大持仓数',
      rebalance_frequency: '调仓频率(天)',
      csi500_ma_short: '中证500短期均线',
      csi500_ma_long: '中证500长期均线',
      csi500_sideways_pct: '震荡市判定阈值',
      bear_max_pos: '下跌市最大持仓',
      bear_stop_loss: '下跌市止损比例',
      sideways_max_pos: '震荡市最大持仓',
      stop_loss: '止损比例',
      rebalance_threshold: '再平衡浮盈阈值',
      regime_source: '行情判定来源',
      verbose_logging: '详细日志',
    }
  },
};

// 从模板代码中提取 class_name 用于匹配 BUILTIN_META
const extractedClassName = computed(() => {
  const code = template.value?.code_template || '';
  const m = code.match(/class\s+(\w+)\s*[(:]/);
  return m?.[1] || '';
});
const meta = computed(() => BUILTIN_META[extractedClassName.value] || null);
const displayName = computed(() => {
  const raw = meta.value?.name || template.value?.template_name || template.value?.name || '';
  return raw.replace(/^内置策略:\s*/, '');
});
const displayDesc = computed(() => {
  return meta.value?.desc || (template.value?.description || '').replace(/^内置策略:\s*/, '');
});

// v2.6: 推断参数值类型
type ParamType = 'boolean' | 'integer' | 'float' | 'array' | 'object' | 'string';

function inferParamType(v: any): ParamType {
  if (typeof v === 'boolean') return 'boolean';
  if (Array.isArray(v)) return 'array';
  if (typeof v === 'object' && v !== null) return 'object';
  if (typeof v === 'number' && Number.isInteger(v)) return 'integer';
  if (typeof v === 'number') return 'float';
  return 'string';
}

const paramEntries = computed(() => {
  const params = template.value?.default_parameters;
  if (!params || typeof params !== 'object') return [];
  return Object.entries(params).map(([key, value]) => ({
    key,
    value,
    valueType: inferParamType(value),
    label: paramLabels.value[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    step: typeof value === 'number' && Number.isInteger(value) ? 1 : 0.01,
  }));
});

// v2.6: JSON 参数文本编辑缓存
const jsonTexts = reactive<Record<string, string>>({});
const getJsonText = (key: string, val: any) => {
  if (!(key in jsonTexts)) jsonTexts[key] = JSON.stringify(val);
  return jsonTexts[key];
};
const parseJsonParam = (key: string) => {
  const raw = jsonTexts[key];
  if (!raw || !raw.trim()) return;
  try {
    const parsed = JSON.parse(raw);
    overrideParams.value = {...overrideParams.value, [key]: parsed};
    jsonTexts[key] = JSON.stringify(parsed);
  } catch {
    jsonTexts[key] = JSON.stringify(overrideParams.value[key] ?? template.value?.default_parameters?.[key]);
  }
};

// 参数中文标签：优先使用 BUILTIN_META 定义的标签，回退到通用映射
const paramLabels = computed(() => {
  const labels: Record<string, string> = {...FLAT_PARAM_LABELS};
  if (meta.value?.params) Object.assign(labels, meta.value.params);
  return labels;
});
const FLAT_PARAM_LABELS: Record<string, string> = {
  // 通用参数
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
  // ML/DL 策略参数
  stop_loss: '止损比例(%)', take_profit: '止盈比例(%)',
  algorithm: '算法类型', feature_columns: '特征列',
  prediction_horizon: '预测周期(天)', confidence_threshold: '置信度阈值',
  retrain_interval: '重训间隔(天)', min_training_samples: '最小训练样本数',
  batch_size: '批次大小', num_layers: '网络层数',
  dropout_rate: 'Dropout 比率', hidden_units: '隐藏单元数',
  learning_rate: '学习率', sequence_length: '序列长度',
  min_training_sequences: '最小训练序列数', target_column: '目标列',
  // V4 主线趋势策略参数
  cooling_period: '冷却期(天)', max_sector_limit: '同板块上限',
  trend_weight: '趋势权重', volume_weight: '量价权重', valuation_weight: '估值权重',
  momentum_accel_short: '加速短窗口', momentum_accel_long: '加速长窗口',
  rs_window: '相对强弱窗口', rs_benchmark: '基准指数代码',
  vol_ratio_short: '量比短窗口', vol_ratio_long: '量比长窗口', vol_price_window: '价量配合窗口',
  turnover_short: '换手短窗口', turnover_long: '换手长窗口',
  pe_percentile_years: 'PE分位回溯年数', pb_percentile_years: 'PB分位回溯年数',
  verbose_logging: '详细日志',
  v4_bull_width_min: 'BULL行业宽度下限', v4_bear_width_max: 'BEAR行业宽度上限',
  v4_confirm_min_score: '入场最低综合得分', v4_confirm_min_trend: '入场最低趋势得分',
  v4_confirm_max_deviation: '最大MA20偏离比例', v4_confirm_stability_days: '趋势稳定性回溯天数',
  v4_batch_1: '首批建仓仓位', v4_batch_2: '二批建仓仓位', v4_batch_3: '三批建仓仓位',
  v4_batch_2_tolerance: '二批价格偏离容忍度',
  v4_add_threshold_1: '首次加仓浮盈阈值', v4_add_threshold_2: '二次加仓浮盈阈值',
  v4_add_size_1: '首次加仓量', v4_add_size_2: '二次加仓量', v4_position_max: '单主线仓位上限',
  v4_trail_stop_ratio: '移动止损回撤比例', v4_heavy_stop_ratio: '重仓回撤比例',
  v4_rs_sell_60d: 'RS卖出60日阈值', v4_rs_sell_20d: 'RS卖出20日阈值',
  v4_exit_cooldown_stop: '止损出场冷却天数',
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

const builtinTypeLabel = (type: string) => {
  const m: Record<string, string> = {
    technical: '趋势跟踪', alpha: 'Alpha', ml: '机器学习', dl: '深度学习', rotation: '行业轮动',
  };
  return m[type] || type || '未知';
};
const builtinTypeTag = (type: string) => {
  const m: Record<string, string> = {
    technical: 'success', alpha: 'info', ml: 'error', dl: 'error', rotation: 'warning',
  };
  return m[type] || 'default';
};

const load = async () => {
  loading.value = true;
  error.value = '';
  const id = route.params.id as string;
  if (!id) { error.value = '缺少模板ID'; loading.value = false; return; }
  try {
    const res = await request.get('/quantTrade/strategy/templates/' + id);
    template.value = res?.data || res;
    if (template.value?.template_name) {
      instanceName.value = template.value.template_name.replace(/^内置策略:\s*/, '');
    }
  } catch (e: any) {
    error.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
};

const handleBack = () => {
  if (window.history.length > 1) router.go(-1);
  else router.push('/strategies');
};

const handleCreateInstance = async () => {
  if (creating.value) return;
  const id = route.params.id as string;
  if (!id) return;
  creating.value = true;
  try {
    const res = await request.post('/quantTrade/strategy/templates/' + id + '/create-instance', {
      name: instanceName.value || undefined,
      run_mode: 'backtest',
    });
    if (res?.data?.id) {
      message.success('策略创建成功');
      router.push('/strategies/workspace/' + res.data.id);
    }
  } catch (e: any) {
    message.error('创建失败: ' + (e?.message || '未知错误'));
  } finally {
    creating.value = false;
  }
};

const handleQuickBacktest = async () => {
  if (quickBacktesting.value) return;
  const id = route.params.id as string;
  if (!id) return;
  quickBacktesting.value = true;
  try {
    // 收集参数覆写值
    const overrides: Record<string, any> = {};
    if (template.value?.params) {
      for (const [key, spec] of Object.entries(template.value.params) as [string, any][]) {
        const val = overrideParams.value?.[key] ?? spec.default;
        if (val !== spec.default) overrides[key] = val;
      }
    }
    const res = await request.post('/quantTrade/backtest/run-scenario', {
      name: (instanceName.value || template.value?.name || '快速回测'),
      code: template.value?.code_template || '',
      parameters: overrides,
      config: {
        start_date: '2023-01-01',
        end_date: '2024-12-31',
        initial_capital: 1000000,
      },
      template_id: id,
    });
    if (res?.data?.task_id) {
      message.success('回测已启动');
      router.push('/backtest?task=' + res.data.task_id);
    }
  } catch (e: any) {
    message.error('快速回测失败: ' + (e?.message || '未知错误'));
  } finally {
    quickBacktesting.value = false;
  }
};

onMounted(() => { load(); });

</script>

<style lang="scss" scoped>
.template-detail {
  height: 100%;
  padding: 0;
  display: flex; flex-direction: column;
  overflow: hidden;
}
.center-spin {
  display: flex; justify-content: center; margin-top: 200px;
}
.main-content {
  flex: 1; min-height: 0; overflow: hidden;
  padding: 0 24px 16px;
}
.td-body {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
  height: 100%; min-height: 0;
  @media (max-width: 900px) { grid-template-columns: 1fr; height: auto; }
}
.td-left {
  display: flex; flex-direction: column; height: 100%; min-height: 0; overflow: hidden;
  .code-card {
    flex: 1; display: flex; flex-direction: column; min-height: 0;
    :deep(.n-card__content) { flex: 1; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
    :deep(.td-editor) { flex: 1; min-height: 0; }
  }
}
.td-right {
  display: flex; flex-direction: column; gap: 12px;
  overflow-y: auto;
}
.td-hint {
  margin-top: 8px; font-size: 12px; color: var(--n-text-color-3); text-align: center;
}
</style>
