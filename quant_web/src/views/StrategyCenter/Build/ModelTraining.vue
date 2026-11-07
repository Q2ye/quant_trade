<!-- ModelTraining.vue — LightGBM ETF 底部策略模型训练 v3.4（异步任务 + 轮询结果闭环） -->
<script setup lang="ts">
import { ref, reactive, computed, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import {
  NButton, NInputNumber, NSelect, NCard,
  NResult, NTag, NText, NSkeleton, NAlert, NSpace, NTooltip, NProgress,
} from "naive-ui";
import strategyAPI from "@/api/strategy";
import FeatureSetSelector from "@/components/strategy/FeatureSetSelector.vue";

const router = useRouter();

const pageState = ref<"loading" | "data" | "error">("data");
const training = ref(false);
const taskId = ref<string | null>(null);
const trainStatus = ref<"pending" | "running" | "completed" | "failed">("pending");
const trainProgress = ref(0);
const result = ref<any>(null);
const errorMsg = ref("");
let pollTimer: ReturnType<typeof setInterval> | null = null;

const config = reactive({
  featureSetIds: [] as string[],
  labelN: 10,
  labelX: 0.03,
  labelY: -0.05,
  numLeaves: 31,
  maxDepth: 5,
  learningRate: 0.05,
  nEstimators: 500,
  regAlpha: 0.5,
  regLambda: 1.0,
});

async function startTraining() {
  if (training.value) return;
  training.value = true;
  errorMsg.value = "";
  result.value = null;
  trainStatus.value = "pending";
  trainProgress.value = 0;
  try {
    const res = await strategyAPI.trainLgbModel({
      feature_set_ids: config.featureSetIds.length > 0 ? config.featureSetIds : undefined,
      label_N: config.labelN, label_X: config.labelX, label_Y: config.labelY,
      num_leaves: config.numLeaves, max_depth: config.maxDepth,
      learning_rate: config.learningRate, n_estimators: config.nEstimators,
      reg_alpha: config.regAlpha, reg_lambda: config.regLambda,
    });
    const data = res.data ?? res;
    taskId.value = data.task_id ?? null;
    if (!taskId.value) {
      errorMsg.value = "训练任务提交失败：未返回 task_id";
      training.value = false;
      return;
    }
    trainStatus.value = "running";
    startPolling();
  } catch (e: any) {
    errorMsg.value = e?.message || "训练任务提交失败";
    training.value = false;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(async () => {
    if (!taskId.value) return;
    try {
      const s = await strategyAPI.getTrainStatus(taskId.value);
      const d = s.data ?? s;
      trainStatus.value = d.status || "running";
      trainProgress.value = Math.round((d.progress ?? 0) * 100);
      if (d.status === "completed") {
        result.value = d.result || {
          auc_test: d.auc_test, threshold: d.threshold, test_win_rate: d.test_win_rate,
          test_signals: d.test_signals, features_n: d.features_n,
          n_samples: d.n_samples, model_path: d.model_path,
        };
        stopPolling();
        training.value = false;
      } else if (d.status === "failed") {
        errorMsg.value = d.error_message || "训练失败";
        stopPolling();
        training.value = false;
      }
    } catch (e: any) {
      // 轮询失败不中断，等待下次
    }
  }, 2000);
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

/** 特征重要性 Top5（归一化为百分比条） */
const topFeatures = computed(() => {
  const imp = result.value?.feature_importance || {};
  const entries = Object.entries(imp).map(([name, val]) => ({ name, val: Number(val) || 0 }));
  entries.sort((a, b) => b.val - a.val);
  const top = entries.slice(0, 5);
  const max = top.length ? top[0].val : 1;
  return top.map((f) => ({ ...f, pct: max > 0 ? Math.round((f.val / max) * 100) : 0 }));
});

onUnmounted(stopPolling);
</script>

<template>
  <div class="model-training bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">模型训练</h1>
          <p class="page-description">LightGBM ETF 底部策略 — 离线训练</p>
        </div>
      </div>
    </div>

    <div class="train-layout">
      <!-- Left: Config -->
      <n-card title="训练配置" size="small">
        <!-- 数据 -->
        <div class="config-section">
          <h4>📊 数据</h4>
          <div class="config-row">
            <span class="label">特征集</span>
            <FeatureSetSelector v-model="config.featureSetIds" />
          </div>

          <div class="config-row">
            <span class="label">标签参数</span>
            <div class="param-desc">
              未来 <b>N</b> 天内，最高价涨幅 ≥ <b>X</b> 且最大回撤 ≥ <b>Y</b> → 标记为底部成功(1)
            </div>
            <n-space style="margin-top:8px">
              <n-tooltip trigger="hover">
                <template #trigger><span style="font-size:12px">持有期 N</span></template>
                未来N个交易日内判断信号是否成功。越大信号越稀疏，越小越嘈杂。推荐: 5~15
              </n-tooltip>
              <n-input-number v-model:value="config.labelN" :min="1" :max="30" size="small" style="width:65px" />
              <n-tooltip trigger="hover">
                <template #trigger><span style="font-size:12px">目标涨幅 X</span></template>
                从底部反弹的目标涨幅。越大正样本越少，模型越保守。推荐: 2%~5%
              </n-tooltip>
              <n-input-number v-model:value="config.labelX" :min="0.01" :max="0.15" :step="0.01" size="small" style="width:80px" />
              <n-tooltip trigger="hover">
                <template #trigger><span style="font-size:12px">回撤容忍 Y</span></template>
                入场后允许的最大回撤(负值)。如-5%表示最多允许再跌5%。推荐: -3%~-8%
              </n-tooltip>
              <n-input-number v-model:value="config.labelY" :min="-0.15" :max="-0.01" :step="0.01" size="small" style="width:85px" />
            </n-space>
          </div>
        </div>

        <!-- 模型参数 -->
        <div class="config-section">
          <h4>⚙️ LightGBM 参数</h4>
          <div class="param-grid">
            <div class="param-item">
              <n-tooltip trigger="hover">
                <template #trigger><span class="label">num_leaves</span></template>
                每棵树的叶子节点数。越大模型越复杂，越容易过拟合。推荐: 15~63
              </n-tooltip>
              <n-input-number v-model:value="config.numLeaves" :min="7" :max="255" size="small" style="width:80px" />
            </div>
            <div class="param-item">
              <n-tooltip trigger="hover">
                <template #trigger><span class="label">max_depth</span></template>
                树的最大深度。-1为不限制。限制深度可防止过拟合。推荐: 3~8
              </n-tooltip>
              <n-input-number v-model:value="config.maxDepth" :min="2" :max="15" size="small" style="width:80px" />
            </div>
            <div class="param-item">
              <n-tooltip trigger="hover">
                <template #trigger><span class="label">learning_rate</span></template>
                学习率/步长。越小需要越多棵树，但泛化更好。推荐: 0.01~0.1
              </n-tooltip>
              <n-input-number v-model:value="config.learningRate" :min="0.005" :max="0.3" :step="0.005" size="small" style="width:80px" />
            </div>
            <div class="param-item">
              <n-tooltip trigger="hover">
                <template #trigger><span class="label">n_estimators</span></template>
                最大迭代轮数(树的数量)。配合 early_stopping 使用，设置大一些无妨。推荐: 200~1000
              </n-tooltip>
              <n-input-number v-model:value="config.nEstimators" :min="50" :max="3000" :step="50" size="small" style="width:80px" />
            </div>
            <div class="param-item">
              <n-tooltip trigger="hover">
                <template #trigger><span class="label">reg_alpha</span></template>
                L1 正则化。越大越稀疏，防止过拟合。推荐: 0~1.0
              </n-tooltip>
              <n-input-number v-model:value="config.regAlpha" :min="0" :max="5" :step="0.1" size="small" style="width:80px" />
            </div>
            <div class="param-item">
              <n-tooltip trigger="hover">
                <template #trigger><span class="label">reg_lambda</span></template>
                L2 正则化(权重衰减)。越大模型越保守。推荐: 0~2.0
              </n-tooltip>
              <n-input-number v-model:value="config.regLambda" :min="0" :max="5" :step="0.1" size="small" style="width:80px" />
            </div>
          </div>
          <div class="param-note">
            💡 <b>保守(防过拟合)</b>: num_leaves=15, max_depth=3, reg_alpha=1.0, reg_lambda=2.0<br/>
            💡 <b>激进(追求拟合)</b>: num_leaves=63, max_depth=7, reg_alpha=0.1, reg_lambda=0.3
          </div>
        </div>

        <n-button type="primary" block :loading="training" @click="startTraining" style="margin-top:12px">
          {{ training ? "训练中..." : "开始训练" }}
        </n-button>
      </n-card>

      <!-- Right: Results -->
      <n-card title="训练结果" size="small">
        <n-alert v-if="errorMsg" type="error" style="margin-bottom:12px" closable @close="errorMsg = ''">{{ errorMsg }}</n-alert>
        <n-skeleton v-if="training" :repeat="4" text />
        <n-empty v-else-if="!result" description="配置参数后点击「开始训练」" />
        <template v-else>
          <div class="progress-row" v-if="training && trainStatus === 'running'">
            <n-progress
              type="line"
              :percentage="trainProgress"
              :indicator-placement="'inside'"
              :height="20"
              :border-radius="4"
            />
          </div>
          <div class="metric-grid">
            <div class="metric">
              <span class="metric-label">AUC</span>
              <span class="metric-value">{{ result.auc_test?.toFixed(4) || "-" }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">最佳阈值</span>
              <span class="metric-value">{{ result.threshold?.toFixed(2) || "-" }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">胜率</span>
              <span class="metric-value">{{ result.test_win_rate ? (result.test_win_rate * 100).toFixed(1) + "%" : "-" }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">测试信号数</span>
              <span class="metric-value">{{ result.test_signals ?? "-" }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">特征数</span>
              <span class="metric-value">{{ result.features_n ?? "-" }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">样本数</span>
              <span class="metric-value">{{ result.n_samples ?? "-" }}</span>
            </div>
          </div>
          <div v-if="result.model_path" class="model-path">
            <n-tag type="success" size="small">模型已保存</n-tag>
            <n-text code depth="3" style="font-size:12px;margin-left:8px">{{ result.model_path }}</n-text>
          </div>
          <div v-if="result.feature_importance && Object.keys(result.feature_importance).length" class="feat-imp">
            <n-text depth="3" style="font-size:12px">Top 特征重要性</n-text>
            <div class="feat-bars">
              <div v-for="f in topFeatures" :key="f.name" class="feat-bar-row">
                <span class="feat-name">{{ f.name }}</span>
                <div class="feat-track"><div class="feat-fill" :style="{ width: f.pct + '%' }"></div></div>
                <span class="feat-val">{{ f.val }}</span>
              </div>
            </div>
          </div>
        </template>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.model-training { min-height: 100vh; padding: 20px; }
.page-header { margin-bottom: 20px; }
.page-title { font-size: 24px; color: var(--n-text-color-1); }
.page-description { font-size: 14px; color: var(--n-text-color-3); margin:0; }
.header-content { display: flex; justify-content: space-between; align-items: center; }
.train-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 900px) { .train-layout { grid-template-columns: 1fr; } }
.config-section { margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid var(--n-border-color); }
.config-section h4 { margin: 0 0 10px; font-size: 14px; color: var(--n-text-color-2); }
.config-row { margin-bottom: 12px; }
.config-row .label { display: inline-block; min-width: 60px; font-size: 13px; color: var(--n-text-color-3); margin-bottom: 4px; }
.param-desc { font-size: 12px; color: var(--n-text-color-3); margin-bottom: 4px; }
.param-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.param-item { display: flex; align-items: center; gap: 8px; }
.param-item .label { font-size: 12px; color: var(--n-text-color-2); min-width: 100px; cursor: help; }
.param-note { margin-top: 10px; font-size: 12px; color: var(--n-text-color-3); line-height: 1.6; }
.metric-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 16px; }
.metric { padding: 10px; background: var(--n-color-embedded); border-radius: 6px; text-align: center; }
.metric-label { display: block; font-size: 12px; color: var(--n-text-color-3); margin-bottom: 4px; }
.metric-value { font-size: 20px; font-weight: 600; color: var(--n-text-color-1); }
.model-path { margin-top: 12px; display: flex; align-items: center; }
.progress-row { margin-bottom: 14px; }
.feat-imp { margin-top: 14px; display: flex; flex-direction: column; gap: 6px; }
.feat-bars { display: flex; flex-direction: column; gap: 5px; }
.feat-bar-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.feat-name { min-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--n-text-color-2); }
.feat-track { flex: 1; height: 6px; background: var(--n-color-embedded); border-radius: 3px; overflow: hidden; }
.feat-fill { height: 100%; background: #3B82F6; border-radius: 3px; }
.feat-val { min-width: 40px; text-align: right; color: var(--n-text-color-3); font-variant-numeric: tabular-nums; }
</style>
