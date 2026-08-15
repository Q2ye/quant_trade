<!-- CompositeCenter.vue — 组合实盘管理：列表 + 详情 + 成员管理 + 净值曲线 -->
<template>
  <div class="composite-center bg-gradient-mesh bg-noise">
    <!-- ═══════ 页头（公共 page-header 结构） ═══════ -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">组合实盘</h1>
          <p class="page-description">共享资金池 · CapitalAllocator 按行情分配</p>
        </div>
        <div class="header-actions">
          <n-button size="small" type="primary" @click="openCreate = true">
            <template #icon><Icon icon="mdi:plus" /></template>新建组合
          </n-button>
          <n-button class="action-btn" @click="loadGroups" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <!-- ═══════ 内容区（.main-content 提供左右 19px 边距） ═══════ -->
    <div class="main-content">

    <!-- ═══════ 组合列表 ═══════ -->
    <n-skeleton v-if="loading && !groups.length" text :repeat="3" style="margin-top:16px" />
    <n-empty v-else-if="!loading && !error && !groups.length" description="暂无组合，点击右上角新建" style="margin-top:40px" />
    <n-result v-else-if="error" status="error" :title="error" style="margin-top:24px">
      <template #footer><n-button size="small" @click="loadGroups">重试</n-button></template>
    </n-result>

    <div v-else class="group-grid">
      <n-card
        v-for="g in groups"
        :key="g.id"
        class="group-card card-surface hover-lift"
        :class="{ 'group-card--active': selected?.id === g.id }"
        size="small"
        hoverable
        @click="selectGroup(g)"
      >
        <div class="group-card__head">
          <span class="group-name">{{ g.name }}</span>
          <n-tag :type="regimeMeta(g.current_regime).type" size="small" round>
            <template #icon>
              <Icon :icon="regimeMeta(g.current_regime).icon" :size="14" />
            </template>
            {{ regimeMeta(g.current_regime).label }}
          </n-tag>
        </div>
        <div class="group-card__meta">
          <span>{{ (g.strategy_ids || []).length }} 个策略</span>
          <span>·</span>
          <span>{{ statusText(g.status) }}</span>
          <template v-if="g.last_rebalance_at">
            <span>·</span>
            <span>rebalance {{ fmtDate(g.last_rebalance_at) }}</span>
          </template>
        </div>
        <div
          v-if="g.current_allocation && Object.keys(g.current_allocation).length"
          class="group-card__alloc"
        >
          <div
            v-for="(w, aid) in g.current_allocation"
            :key="aid"
            class="alloc-row"
          >
            <div class="alloc-row__head">
              <span class="alloc-row__name">{{ aid }}</span>
              <span class="alloc-row__pct">{{ (w * 100).toFixed(0) }}%</span>
            </div>
            <n-progress
              type="line"
              :percentage="Math.max(2, Math.round(w * 100))"
              :show-indicator="false"
              :height="5"
              :border-radius="3"
              color="var(--n-primary-color)"
            />
          </div>
        </div>
      </n-card>
    </div>

    <!-- ═══════ 组合详情 ═══════ -->
    <n-card v-if="selected" class="detail-card card-surface" size="small" style="margin-top:16px">
      <template #header>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-weight:600">{{ selected.name }} — 详情</span>
          <n-tag :type="regimeMeta(selected.current_regime).type" size="small" round>
            <template #icon>
              <Icon :icon="regimeMeta(selected.current_regime).icon" :size="14" />
            </template>
            {{ regimeMeta(selected.current_regime).label }}
          </n-tag>
          <n-button size="tiny" secondary :loading="rebRunning" @click="runRebalance">Rebalance</n-button>
          <n-button size="tiny" secondary :loading="trigRunning" @click="runTrigger">触发</n-button>
        </div>
      </template>

      <!-- 策略成员表 -->
      <n-data-table
        :columns="memberColumns"
        :data="members"
        :loading="detailLoading"
        size="small"
        :bordered="false"
      />

      <div class="detail-footer">
        <n-button size="small" secondary @click="openAdd = true">
          <template #icon><Icon icon="mdi:plus" /></template>添加策略
        </n-button>
        <span class="hint">权重 = 熊/震荡/牛 三档，相加需为 1（添加时自动缩放旧策略）</span>
      </div>

      <!-- 净值曲线 -->
      <div class="nav-section">
        <h4>组合净值</h4>
        <v-chart v-if="navData.length" class="nav-chart" :option="navOption" autoresize />
        <n-empty v-else description="暂无净值数据（每日 rebalance 后生成）" size="small" />
      </div>
    </n-card>
    </div>

    <!-- ═══════ 新建组合弹窗 ═══════ -->
    <n-modal v-model:show="openCreate" preset="card" title="新建组合" style="width:520px">
      <n-form label-placement="top">
        <n-form-item label="组合名称">
          <n-input v-model:value="createForm.name" placeholder="如：进攻防御组合" />
        </n-form-item>
        <n-form-item label="共享账户">
          <n-input v-model:value="createForm.account_id" placeholder="账户 ID（可留空，默认用第一个账户）" />
        </n-form-item>
        <n-form-item label="选择策略（至少 2 个）">
          <n-select
            v-model:value="createForm.strategy_ids"
            multiple
            :options="availableStrategies"
            placeholder="选择 live 策略"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button size="small" :loading="creating" @click="createGroup">创建</n-button>
        <n-button size="small" secondary @click="openCreate = false">取消</n-button>
      </template>
    </n-modal>

    <!-- ═══════ 添加策略弹窗 ═══════ -->
    <n-modal v-model:show="openAdd" preset="card" title="添加策略到组合" style="width:520px">
      <n-form label-placement="top">
        <n-form-item label="策略">
          <n-select v-model:value="addForm.strategy_id" :options="availableStrategies" placeholder="选择 live 策略" />
        </n-form-item>
        <n-form-item label="allocator_id（权重 key）">
          <n-input v-model:value="addForm.allocator_id" placeholder="默认=策略名" />
        </n-form-item>
        <div class="weight-grid">
          <n-form-item label="熊市权重 w0">
            <n-input-number v-model:value="addForm.w0" :min="0" :max="1" :step="0.05" style="width:100%" />
          </n-form-item>
          <n-form-item label="震荡权重 w1">
            <n-input-number v-model:value="addForm.w1" :min="0" :max="1" :step="0.05" style="width:100%" />
          </n-form-item>
          <n-form-item label="牛市权重 w2">
            <n-input-number v-model:value="addForm.w2" :min="0" :max="1" :step="0.05" style="width:100%" />
          </n-form-item>
        </div>
      </n-form>
      <template #footer>
        <n-button size="small" type="primary" :loading="adding" @click="addStrategy">添加</n-button>
        <n-button size="small" secondary @click="openAdd = false">取消</n-button>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from "vue";
import { useMessage } from "naive-ui";
import { NButton, NPopconfirm, NTag } from "naive-ui";
import { Icon } from "@iconify/vue";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import VChart from "vue-echarts";
import compositeAPI, { CompositeGroup } from "@/api/composite";
import strategyAPI from "@/api/strategy";

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent]);

const msg = useMessage();
const loading = ref(false);
const error = ref("");
const groups = ref<CompositeGroup[]>([]);
const selected = ref<CompositeGroup | null>(null);
const members = ref<Array<Record<string, any>>>([]);
const navData = ref<Array<Record<string, any>>>([]);
const detailLoading = ref(false);
const rebRunning = ref(false);
const trigRunning = ref(false);

// 弹窗状态
const openCreate = ref(false);
const openAdd = ref(false);
const creating = ref(false);
const adding = ref(false);
const createForm = ref({ name: "", account_id: "", strategy_ids: [] as string[] });
const addForm = ref({ strategy_id: "", allocator_id: "", w0: 0.2, w1: 0.5, w2: 0.3 });

const regimeMeta = (r: number) =>
  r === 0 ? { label: "熊市", type: "warning" as const, icon: "mdi:trending-down" }
  : r === 2 ? { label: "牛市", type: "success" as const, icon: "mdi:trending-up" }
  : { label: "震荡", type: "info" as const, icon: "mdi:swap-horizontal" };

const statusText = (s: string) => {
  const map: Record<string, string> = { running: "运行中", stopped: "已停止", created: "已创建", archived: "已归档" };
  return map[s] || s || "--";
};

const fmtDate = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (!isNaN(d.getTime())) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  return String(iso).slice(0, 10);
};

const strategies = ref<Array<{ id: string; name: string; status: string }>>([]);

async function loadStrategies() {
  try {
    const list = (await strategyAPI.getStrategies()) as any[];
    strategies.value = (list || []).map((s) => ({
      id: s.id,
      name: s.name || s.id,
      status: s.status || "",
    }));
  } catch (e) {
    strategies.value = [];
  }
}

// 可选策略：排除已在当前组合中的；创建组合时（selected 为空）显示全部
const availableStrategies = computed(() => {
  const inGroup = new Set((selected.value?.strategy_ids || []).map((c: any) => c.strategy_id));
  return strategies.value
    .filter((s) => !inGroup.has(s.id))
    .map((s) => ({ label: `${s.name} (${s.status})`, value: s.id }));
});

async function loadGroups() {
  loading.value = true;
  error.value = "";
  try {
    groups.value = await compositeAPI.listGroups();
  } catch (e: any) {
    error.value = e?.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

async function selectGroup(g: CompositeGroup) {
  selected.value = g;
  detailLoading.value = true;
  try {
    const detail = await compositeAPI.getGroup(g.id);
    selected.value = detail;
    // merge 策略状态（运行中/已停止），供成员表格状态列展示
    const statusMap = new Map(strategies.value.map((s) => [s.id, s.status]));
    members.value = (detail.strategy_ids || []).map((c: any) => ({
      strategy_id: c.strategy_id,
      allocator_id: c.allocator_id || c.strategy_id,
      status: statusMap.get(c.strategy_id) || "stopped",
      // 从 current_allocation 或 allocator_config 取权重（简化：显示当前分配）
      weight: (detail.current_allocation || {})[c.allocator_id || c.strategy_id] ?? 0,
    }));
    navData.value = await compositeAPI.getNav(g.id);
  } catch (e: any) {
    msg.error(e?.message || "加载详情失败");
  } finally {
    detailLoading.value = false;
  }
}

async function runRebalance() {
  if (!selected.value) return;
  rebRunning.value = true;
  try {
    const res = await compositeAPI.rebalance(selected.value.id);
    msg.success(`Rebalance 完成：regime=${regimeMeta(res.regime).label}`);
    await selectGroup(selected.value);
    await loadGroups();
  } catch (e: any) {
    msg.error(e?.message || "Rebalance 失败");
  } finally {
    rebRunning.value = false;
  }
}

async function runTrigger() {
  if (!selected.value) return;
  trigRunning.value = true;
  try {
    const res = await compositeAPI.trigger({
      composite_group_id: selected.value.id,
      trade_date: todayLocal(),
    });
    msg.success(`触发完成：${res.strategies_triggered?.length ?? 0} 个策略，${res.total_signals ?? 0} 个信号`);
  } catch (e: any) {
    msg.error(e?.message || "触发失败");
  } finally {
    trigRunning.value = false;
  }
}

async function addStrategy() {
  if (!selected.value || !addForm.value.strategy_id) return;
  adding.value = true;
  try {
    await compositeAPI.addStrategy(selected.value.id, {
      strategy_id: addForm.value.strategy_id,
      allocator_id: addForm.value.allocator_id || addForm.value.strategy_id,
      w0: addForm.value.w0,
      w1: addForm.value.w1,
      w2: addForm.value.w2,
    });
    msg.success("策略已加入组合");
    openAdd.value = false;
    await selectGroup(selected.value);
  } catch (e: any) {
    msg.error(e?.message || "添加失败");
  } finally {
    adding.value = false;
  }
}

async function removeMember(strategyId: string) {
  if (!selected.value) return;
  try {
    await compositeAPI.removeStrategy(selected.value.id, strategyId);
    msg.success("策略已移出组合");
    await selectGroup(selected.value);
  } catch (e: any) {
    msg.error(e?.message || "移除失败");
  }
}

async function createGroup() {
  if (!createForm.value.name || createForm.value.strategy_ids.length < 2) {
    msg.warning("请填写名称并选择至少 2 个策略");
    return;
  }
  creating.value = true;
  try {
    await compositeAPI.createGroup({
      name: createForm.value.name,
      account_id: createForm.value.account_id || undefined,
      strategy_configs: createForm.value.strategy_ids.map((sid) => ({ strategy_id: sid })),
    });
    msg.success("组合已创建");
    openCreate.value = false;
    await loadGroups();
  } catch (e: any) {
    msg.error(e?.message || "创建失败");
  } finally {
    creating.value = false;
  }
}

// 净值曲线 option
const navOption = computed(() => ({
  tooltip: { trigger: "axis" },
  legend: { data: ["组合净值"], bottom: 0 },
  grid: { left: 50, right: 16, top: 16, bottom: 32 },
  xAxis: { type: "category", data: navData.value.map((d) => d.trade_date), boundaryGap: false },
  yAxis: { type: "value", scale: true },
  series: [{
    name: "组合净值",
    type: "line",
    smooth: true,
    symbol: "none",
    data: navData.value.map((d) => d.total_nav),
    areaStyle: { opacity: 0.12 },
    lineStyle: { width: 2 },
  }],
}));

const memberColumns = [
  { title: "策略 ID", key: "strategy_id", ellipsis: { tooltip: true } },
  { title: "allocator_id", key: "allocator_id" },
  {
    title: "状态", key: "status", width: 80,
    render: (row: any) =>
      row.status === "running"
        ? h(NTag, { size: "tiny", type: "success", bordered: false }, { default: () => "运行中" })
        : h(NTag, { size: "tiny", type: "default", bordered: false }, { default: () => "已停止" }),
  },
  { title: "当前权重", key: "weight", render: (row: any) => `${((row.weight || 0) * 100).toFixed(0)}%` },
  {
    title: "操作",
    key: "actions",
    width: 100,
    render: (row: any) =>
      h(NPopconfirm, { onPositiveClick: () => removeMember(row.strategy_id) }, {
        trigger: () => h(NButton, { size: "tiny", type: "error", quaternary: true }, { default: () => "移除" }),
        default: () => `确定移除 ${row.strategy_id}？`,
      }),
  },
];

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

onMounted(() => {
  loadGroups();
  loadStrategies();
});
</script>

<style scoped lang="scss">
.composite-center {
  min-height: 100vh;
}
.group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}
.group-card {
  cursor: pointer;
  transition: all 0.2s var(--n-bezier);
  &--active { outline: 2px solid var(--n-primary-color); }
  &__head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .group-name { font-weight: 600; font-size: 15px; }
  &__meta {
    display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
    color: var(--n-text-color-3); font-size: 12px; margin-bottom: 10px;
  }
  &__alloc { display: flex; flex-direction: column; gap: 8px; }
  .alloc-row {
    &__head { display: flex; justify-content: space-between; align-items: center; font-size: 12px; margin-bottom: 2px; }
    &__name { color: var(--n-text-color-2); }
    &__pct { color: var(--n-text-color-3); font-variant-numeric: tabular-nums; }
  }
}
.detail-card {
  .detail-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
  .hint { color: var(--n-text-color-3); font-size: 12px; }
  .nav-section { margin-top: 16px;
    h4 { margin: 0 0 8px; font-size: 15px; }
  }
  .nav-chart { height: 260px; }
}
.weight-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
</style>
