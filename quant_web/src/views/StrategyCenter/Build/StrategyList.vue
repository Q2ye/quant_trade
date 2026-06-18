<!-- StrategyList.vue — 策略构建：模板快速开始 + 策略卡片网格 + 批量操作 -->
<template>
  <div class="strategy-list bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略构建</h1>
          <p class="page-description">从模板快速开始或自主编写策略代码</p>
        </div>
        <div class="header-actions">
          <n-button type="primary" @click="router.push('/strategies/workspace/new')">
            <template #icon><SmartIcon name="Plus" /></template>
            新建策略
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <!-- Error -->
      <n-result v-if="pageState === 'error'" status="500" title="加载失败">
        <template #footer><n-button @click="loadStrategies">重试</n-button></template>
      </n-result>

      <!-- Empty — 引导式空状态 -->
      <div v-else-if="pageState === 'empty'" class="empty-state">
        <n-empty description="还没有策略，选择一个模板快速开始">
          <template #extra>
            <div class="empty-templates">
              <div
                v-for="tpl in DEFAULT_TEMPLATES.slice(0, 4)" :key="tpl.id"
                class="empty-tpl-card" @click="router.push(`/strategies/workspace/new?template=${tpl.id}`)"
              >
                <SmartIcon :name="tpl.icon" size="24" />
                <span class="et-name">{{ tpl.name }}</span>
                <span class="et-desc">{{ tpl.description }}</span>
              </div>
            </div>
            <n-button type="primary" size="small" style="margin-top:16px" @click="router.push('/strategies/workspace/new')">
              从空白开始
            </n-button>
          </template>
        </n-empty>
      </div>

      <template v-else-if="pageState === 'data'">
        <!-- 模板快速开始 -->
        <div class="tpl-section">
          <h3 class="section-title">从模板快速开始</h3>
          <div class="tpl-row">
            <div
              v-for="tpl in DEFAULT_TEMPLATES" :key="tpl.id"
              :class="tokens.motion.hover" class="tpl-card"
              @click="router.push(`/strategies/workspace/new?template=${tpl.id}`)"
            >
              <SmartIcon :name="tpl.icon" size="20" :style="{ color: tpl.color }" />
              <span class="tpl-name">{{ tpl.name }}</span>
              <span class="tpl-desc">{{ tpl.description }}</span>
            </div>
          </div>
        </div>

        <!-- 统计条 -->
        <div class="stats-bar">
          <span>📋 <strong>{{ strategies.length }}</strong> 个策略</span>
          <span>🟢 <strong>{{ runningCount }}</strong> 运行中</span>
          <span>⚪ <strong>{{ stoppedCount }}</strong> 已停止</span>
          <span>📝 <strong>{{ draftCount }}</strong> 草稿</span>
        </div>

        <!-- 策略卡片网格 -->
        <h3 class="section-title" v-if="strategies.length > 0">我的策略</h3>
        <div v-if="strategies.length > 0" class="card-grid">
          <div
            v-for="s in strategies" :key="s.id"
            :class="['strategy-card', tokens.surface.card, { selected: checkedKeys.includes(s.id) }]"
            @click="handleCardClick(s)"
          >
            <div class="sc-top">
              <n-checkbox
                :checked="checkedKeys.includes(s.id)"
                @click.stop="toggleCheck(s.id)"
              />
              <n-tag :type="statusMap[s.status] as any" size="tiny">{{ statusText[s.status] || s.status }}</n-tag>
            </div>
            <h4 class="sc-name">{{ s.name || s.id }}</h4>
            <span class="sc-type">{{ s.className || s.strategy_type || '自定义' }}</span>
            <div v-if="s.performance?.annualReturn" class="sc-perf">
              <span :class="s.performance.annualReturn >= 0 ? 'text-up' : 'text-down'">
                {{ (s.performance.annualReturn * 100).toFixed(1) }}%
              </span>
              <span class="sc-perf-label">年化收益</span>
            </div>
            <div class="sc-actions">
              <n-button size="tiny" type="primary" @click.stop="openWorkspace(s)">编辑</n-button>
              <n-button size="tiny" @click.stop="quickBacktest(s)">回测</n-button>
              <n-dropdown trigger="click" :options="moreOpts" @select="(k: string) => handleMore(k, s)">
                <n-button size="tiny" @click.stop>⋮</n-button>
              </n-dropdown>
            </div>
          </div>
        </div>

        <!-- 批量操作栏 -->
        <div v-if="checkedKeys.length > 0" class="batch-bar">
          <span>已选 {{ checkedKeys.length }} 项</span>
          <n-button size="tiny" @click="batchBacktest">批量回测</n-button>
          <n-button size="tiny" @click="batchStart">批量启动</n-button>
          <n-button size="tiny" @click="batchStop">批量停止</n-button>
          <n-button size="tiny" type="error" @click="batchDelete">批量删除</n-button>
        </div>
      </template>
    </div>

    <!-- 新建/编辑 对话框（保留快速创建入口） -->
    <n-modal v-model:show="showDialog" preset="dialog" :title="dialogTitle" positive-text="保存" negative-text="取消"
      @positive-click="saveStrategy">
      <n-form :model="currentStrategy" label-width="80px" size="small">
        <n-form-item label="名称" required><n-input v-model:value="currentStrategy.name" /></n-form-item>
        <n-form-item label="描述"><n-input v-model:value="currentStrategy.description" type="textarea" :rows="2" /></n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="currentStrategy.type" :options="STRATEGY_TYPE_OPTIONS" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h } from "vue";
import { useRouter } from "vue-router";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { useStore } from "vuex";
import { useMessage, useDialog, NTag, NButton, NDropdown, NCheckbox, NResult } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import { STRATEGY_TYPE_OPTIONS, STRATEGY_STATUS_MAP, STRATEGY_STATUS_TEXT } from "./constants";

const message = useMessage();
const dialog = useDialog();
const router = useRouter();
const store = useStore<any>();

type PageState = "loading" | "error" | "empty" | "data";
const pageState = ref<PageState>("loading");
const showDialog = ref(false);
const isEditing = ref(false);
const currentStrategy = ref({ id: null as any, name: "", description: "", type: "trend", className: "", parameters: {}, status: "draft" });
const checkedKeys = ref<string[]>([]);

const strategies = computed(() => store.state.strategy?.strategies || []);
const dialogTitle = computed(() => isEditing.value ? "编辑策略" : "新建策略");
const runningCount = computed(() => strategies.value.filter((s: any) => s.status === "running").length);
const stoppedCount = computed(() => strategies.value.filter((s: any) => s.status === "stopped").length);
const draftCount = computed(() => strategies.value.filter((s: any) => !s.status || s.status === "draft").length);

const statusMap: Record<string, string> = { running: "success", stopped: "warning", draft: "default", deployed: "info", error: "error" };
const statusText: Record<string, string> = { running: "运行中", stopped: "已停止", draft: "草稿", deployed: "已部署", error: "异常" };

const DEFAULT_TEMPLATES = [
  { id: "tpl_001", name: "双均线趋势", description: "金叉/死叉 + 成交量过滤", icon: "TrendingUpOutline", color: "#448AFF" },
  { id: "tpl_002", name: "MACD 信号", description: "零轴交叉 + 柱状图", icon: "PulseOutline", color: "#00E676" },
  { id: "tpl_003", name: "多因子选股", description: "PE/PB/ROE 综合打分", icon: "Options", color: "#FFC107" },
  { id: "tpl_004", name: "均值回归", description: "布林带 + RSI", icon: "StatsChart", color: "#7C4DFF" },
  { id: "tpl_005", name: "动量跟踪", description: "N日动量排名轮动", icon: "TrendingUp", color: "#FF6D00" },
];

const moreOpts = [
  { label: "启动/停止", key: "toggle" },
  { label: "查看报告", key: "report" },
  { label: "克隆", key: "clone" },
  { label: "导出JSON", key: "export" },
  { label: "删除", key: "delete" },
];

// 卡片交互
const handleCardClick = (s: any) => { if (checkedKeys.value.length > 0) toggleCheck(s.id); else openWorkspace(s); };
const toggleCheck = (id: string) => {
  if (checkedKeys.value.includes(id)) checkedKeys.value = checkedKeys.value.filter(k => k !== id);
  else checkedKeys.value.push(id);
};

const handleMore = (key: string, s: any) => {
  if (key === "toggle") toggleStrategy(s);
  else if (key === "report") viewReport(s);
  else if (key === "clone") cloneStrategy(s);
  else if (key === "export") exportStrategy(s);
  else if (key === "delete") deleteStrategy(s);
};

// 策略操作
const openWorkspace = (s: any) => {
  if (!s?.id) { message.warning("策略数据异常，无法打开"); return; }
  router.push(`/strategies/workspace/${s.id}`);
};
const quickBacktest = (s: any) => router.push(`/backtest?strategies=${s.id}`);
const viewReport = (s: any) => router.push({ name: "BacktestReport", params: { taskId: s.id } });
const toggleStrategy = async (s: any) => {
  try {
    if (s.status === "running") await store.dispatch("strategy/stopStrategy", s.id);
    else await store.dispatch("strategy/startStrategy", { strategyId: s.id });
    message.success(s.status === "running" ? "已停止" : "已启动");
  } catch (e: any) { message.error("操作失败: " + e.message); }
};

// 批量操作
const batchBacktest = () => { if (checkedKeys.value.length) router.push(`/backtest?strategies=${checkedKeys.value.join(",")}`); };
const batchStart = async () => {
  for (const id of checkedKeys.value) { try { await store.dispatch("strategy/startStrategy", { strategyId: id }); } catch { /* skip */ } }
  message.success(`已启动 ${checkedKeys.value.length} 个策略`); checkedKeys.value = []; loadStrategies();
};
const batchStop = async () => {
  for (const id of checkedKeys.value) { try { await store.dispatch("strategy/stopStrategy", id); } catch { /* skip */ } }
  message.success(`已停止 ${checkedKeys.value.length} 个策略`); checkedKeys.value = []; loadStrategies();
};
const batchDelete = () => {
  dialog.warning({
    title: "批量删除", content: `确定删除 ${checkedKeys.value.length} 个策略？不可撤销。`,
    positiveText: "删除", negativeText: "取消",
    onPositiveClick: async () => {
      for (const id of checkedKeys.value) { try { await store.dispatch("strategy/deleteStrategy", id); } catch { /* skip */ } }
      message.success("已删除"); checkedKeys.value = []; loadStrategies();
    },
  });
};

// 对话框
const createStrategy = () => { currentStrategy.value = { id: null, name: "", description: "", type: "trend", className: "", parameters: {}, status: "draft" }; isEditing.value = false; showDialog.value = true; };
const editStrategy = (s: any) => { currentStrategy.value = { ...s }; isEditing.value = true; showDialog.value = true; };
const saveStrategy = async () => {
  try {
    if (isEditing.value) await store.dispatch("strategy/updateStrategy", currentStrategy.value);
    else await store.dispatch("strategy/createStrategy", currentStrategy.value);
    showDialog.value = false; message.success("保存成功");
  } catch (e: any) { message.error("保存失败: " + e.message); }
};
const cloneStrategy = (s: any) => { currentStrategy.value = { ...s, id: null, name: s.name + "_副本" }; isEditing.value = false; showDialog.value = true; };
const exportStrategy = (s: any) => {
  const blob = new Blob([JSON.stringify(s, null, 2)], { type: "application/json" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${s.name}.json`; a.click(); URL.revokeObjectURL(a.href);
};
const deleteStrategy = (s: any) => {
  dialog.warning({
    title: "删除确认", content: `确定删除"${s.name}"？不可撤销。`, positiveText: "删除", negativeText: "取消",
    onPositiveClick: async () => { try { await store.dispatch("strategy/deleteStrategy", s.id); message.success("已删除"); loadStrategies(); } catch (e: any) { message.error("删除失败: " + e.message); } },
  });
};

const loadStrategies = async () => {
  pageState.value = "loading";
  try { await store.dispatch("strategy/loadStrategies"); pageState.value = strategies.value.length === 0 ? "empty" : "data"; }
  catch { pageState.value = "error"; }
};

onMounted(() => loadStrategies());
</script>

<style lang="scss" scoped>
.strategy-list { height: 100%; overflow-y: auto; background: transparent; }
.main-content { padding: 16px 32px 24px; }

/* 空状态 */
.empty-state { padding: 40px 0; text-align: center; }
.empty-templates { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; margin-top: 12px; }
.empty-tpl-card { padding: 16px 20px; border-radius: 8px; background: var(--color-bg-card, rgba(12,18,32,0.6)); border: 1px solid rgba(255,255,255,0.06); cursor: pointer; text-align: center; width: 140px; transition: all 0.2s;
  &:hover { border-color: var(--color-primary, #7C3AED); }
  .et-name { font-size: 13px; font-weight: 600; color: var(--color-text-primary); display: block; margin-top: 8px; }
  .et-desc { font-size: 11px; color: var(--color-text-tertiary); display: block; margin-top: 2px; }
}

/* 模板行 */
.tpl-section { margin-bottom: 14px; }
.section-title { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 0 0 8px; }
.tpl-row { display: flex; gap: 10px; flex-wrap: wrap; }
.tpl-card { display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 8px; background: var(--color-bg-card, rgba(12,18,32,0.6)); border: 1px solid rgba(255,255,255,0.06); cursor: pointer; transition: all 0.2s;
  &:hover { border-color: var(--color-primary, #7C3AED); transform: translateY(-1px); }
  .tpl-name { font-size: 13px; font-weight: 600; color: var(--color-text-primary); }
  .tpl-desc { font-size: 11px; color: var(--color-text-tertiary); }
}

/* 统计条 */
.stats-bar { display: flex; gap: 20px; padding: 8px 14px; margin-bottom: 12px; border-radius: 6px; background: var(--color-bg-card, rgba(12,18,32,0.5)); font-size: 13px; color: var(--color-text-secondary);
  strong { color: var(--color-text-primary); margin-left: 4px; }
}

/* 卡片网格 */
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-bottom: 14px; }
.strategy-card { padding: 14px; border-radius: 8px; cursor: pointer; transition: all 0.15s; position: relative;
  background: var(--color-bg-card, rgba(12,18,32,0.6)); border: 1px solid rgba(255,255,255,0.05);
  &:hover { border-color: rgba(124,111,247,0.3); }
  &.selected { border-color: var(--color-primary, #7C3AED); background: rgba(124,111,247,0.08); }
}
.sc-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.sc-name { font-size: 14px; font-weight: 600; color: var(--color-text-primary); margin: 0 0 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-type { font-size: 11px; color: var(--color-text-tertiary); }
.sc-perf { margin-top: 8px; display: flex; align-items: baseline; gap: 6px;
  span:first-child { font-size: 16px; font-weight: 700; }
  .sc-perf-label { font-size: 10px; color: var(--color-text-tertiary); }
}
.sc-actions { display: flex; gap: 4px; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.04); }

/* 批量 */
.batch-bar { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 6px; background: var(--color-bg-card, rgba(12,18,32,0.6)); font-size: 13px; color: var(--color-text-secondary); }

.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
</style>
