<!-- PortfolioBuilder.vue — 策略组合配置：组合列表 + 权重分配 + 组合回测 -->
<template>
  <div class="portfolio-builder bg-gradient-mesh bg-noise">
    <div class="page-header">
      <h1 class="page-title">策略组合</h1>
      <p class="page-desc">组合多个策略，分配权重，回测组合表现</p>
      <div class="header-actions">
        <n-button size="small" type="primary" @click="showCreate = true">+ 新建组合</n-button>
      </div>
    </div>

    <div class="main-body">
      <template v-if="loading">
        <n-card :class="tokens.surface.card"><n-skeleton text :repeat="6" /></n-card>
      </template>
      <n-empty v-else-if="portfolios.length === 0" description="暂无策略组合，点击上方按钮创建">
        <template #extra><n-button type="primary" size="small" @click="showCreate = true">新建组合</n-button></template>
      </n-empty>
      <template v-else>
        <div class="portfolio-grid">
          <n-card v-for="p in portfolios" :key="p.id" :class="tokens.surface.card" size="small" class="portfolio-card">
            <div class="card-header">
              <h4>{{ p.name }}</h4>
              <n-tag size="tiny">{{ p.strategies?.length || 0 }} 策略</n-tag>
            </div>
            <div class="card-body">
              <div v-for="(s, i) in (p.strategies || [])" :key="i" class="strategy-row">
                <span class="s-name">{{ s.name }}</span>
                <n-progress class="s-weight" type="line" :percentage="Math.round((s.weight || 0) * 100)" :height="6" />
              </div>
            </div>
            <div class="card-footer">
              <span v-if="p.annualReturn !== undefined" class="perf-text" :class="p.annualReturn >= 0 ? 'text-up' : 'text-down'">
                年化 {{ (p.annualReturn * 100).toFixed(1) }}%
              </span>
              <n-button size="tiny" @click="backtestPortfolio(p)">回测组合</n-button>
            </div>
          </n-card>
        </div>
      </template>
    </div>

    <!-- 新建组合 Modal -->
    <n-modal v-model:show="showCreate" preset="dialog" title="新建策略组合" positive-text="创建" @positive-click="createPortfolio">
      <n-form size="small" label-width="80px">
        <n-form-item label="组合名称" required>
          <n-input v-model:value="newName" placeholder="例如：稳健价值组合" />
        </n-form-item>
        <n-form-item label="选择策略">
          <n-select :key="strategySelectKey" v-model:value="newStrategyIds" :options="strategyOptions" multiple filterable placeholder="选择1-N个策略" :menu-props="({ zIndex: 2000 } as any)" @update:value="() => strategySelectKey++" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import { NCard, NButton, NTag, NProgress, NModal, NForm, NFormItem, NInput, NSelect, NEmpty, NSkeleton, useMessage } from "naive-ui";
import { tokens } from "@/styles/design-tokens";
import strategyAPI from "@/api/strategy";

const router = useRouter();
const msg = useMessage();
const loading = ref(true);
const showCreate = ref(false);
const newName = ref("");
const newStrategyIds = ref<string[]>([]);
const strategySelectKey = ref(0);
const strategyOptions = ref<Array<{ label: string; value: string }>>([]);

interface PortfolioItem { id: string; name: string; strategies: Array<{ name: string; weight: number }>; annualReturn?: number; }
const portfolios = ref<PortfolioItem[]>([]);

const loadData = async () => {
  loading.value = true;
  try {
    const strategies = await strategyAPI.getStrategies().catch(() => []);
    if (Array.isArray(strategies)) {
      strategyOptions.value = strategies.map((s: any) => ({ label: s.name || s.id, value: s.id || s.name }));
    }
    // 加载已有组合（后端 list API 未就绪，暂时从 store 读取或显示空列表）
  } catch { /* skip */ }
  finally { loading.value = false; }
};

const createPortfolio = async () => {
  if (!newName.value.trim()) { msg.warning("请输入组合名称"); return; }
  if (newStrategyIds.value.length < 2) { msg.warning("请选择至少2个策略"); return; }
  const weight = 1 / newStrategyIds.value.length;
  const sWeights: Record<string, number> = {};
  newStrategyIds.value.forEach(id => { sWeights[id] = weight; });
  const sNames = newStrategyIds.value.map(id => {
    const opt = strategyOptions.value.find(o => o.value === id);
    return { name: opt?.label || id, weight };
  });
  try {
    await strategyAPI.createPortfolio({
      name: newName.value,
      description: "",
      strategy_weights: sWeights,
    });
    portfolios.value.unshift({ id: `pf_${Date.now()}`, name: newName.value, strategies: sNames });
    msg.success("组合已创建");
  } catch {
    portfolios.value.unshift({ id: `pf_${Date.now()}`, name: newName.value, strategies: sNames });
    msg.success("组合已创建（本地模式）");
  }
  showCreate.value = false;
  newName.value = "";
  newStrategyIds.value = [];
};

const backtestPortfolio = (p: PortfolioItem) => {
  const ids = p.strategies?.map(s => {
    const opt = strategyOptions.value.find(o => o.label === s.name);
    return opt?.value || s.name;
  }).join(",") || "";
  router.push(`/backtest?strategies=${ids}`);
};

onMounted(() => loadData());
</script>

<style lang="scss" scoped>
.portfolio-builder { height: 100%; overflow-y: auto; }
.page-header { padding: 24px 32px 10px; display: flex; justify-content: space-between; align-items: flex-start;
  .page-title { font-size: 22px; font-weight: 700; color: var(--color-text-primary); margin: 0 0 4px; }
  .page-desc { font-size: 13px; color: var(--color-text-tertiary); margin: 0; }
}
.main-body { padding: 12px 32px 32px; }
.portfolio-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 12px; }
.portfolio-card {
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;
    h4 { margin: 0; font-size: 15px; color: var(--color-text-primary); }
  }
  .card-body { margin-bottom: 10px; }
  .strategy-row { display: flex; align-items: center; gap: 8px; margin-bottom: 6px;
    .s-name { font-size: 12px; color: var(--color-text-secondary); width: 80px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .s-weight { flex: 1; }
  }
  .card-footer { display: flex; justify-content: space-between; align-items: center; }
  .perf-text { font-size: 13px; font-weight: 600; }
}
.text-up { color: #18a058 !important; }
.text-down { color: #d03050 !important; }
</style>
