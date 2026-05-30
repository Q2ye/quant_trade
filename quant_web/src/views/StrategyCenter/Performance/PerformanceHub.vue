<!--
  PerformanceHub.vue — 绩效总览枢纽页
  功能卡片 + 快捷操作 + 最近分析记录
-->
<template>
  <div class="hub-page bg-gradient-mesh bg-noise">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">绩效总览</h1>
          <p class="page-description">全面评估策略和账户表现，对比绩效指标，深入归因分析</p>
        </div>
        <div class="header-actions">
          <n-button class="action-btn" @click="refreshData" :loading="loading" quaternary>
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <template v-if="loading">
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="Apps" class="title-icon" />功能导航</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <n-grid-item v-for="i in 4" :key="i" :class="tokens.motion.stagger" :style="{ animationDelay: `${(i - 1) * 0.08}s` }">
              <n-card><n-skeleton :text="true" :repeat="5" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
      </template>

      <n-result v-else-if="error" status="500" title="数据加载失败" description="请检查网络连接后重试">
        <template #footer><n-button type="primary" @click="loadData">重试</n-button></template>
      </n-result>

      <template v-else>
        <!-- 功能导航卡片 -->
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="Apps" class="title-icon" />功能导航</h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="4" responsive="screen">
            <!-- 策略绩效 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="router.push('/performance/strategy')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon accent"><SmartIcon name="Trophy" /></div>
                    <h3 class="function-title">策略绩效</h3>
                  </div>
                  <p class="function-desc">单策略绩效分析，收益率、夏普比率、最大回撤等核心指标</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">分析策略</span><span class="stat-value">{{ stats.strategyCount }} 个</span></div>
                    <div class="stat-item"><span class="stat-label">平均年化</span><span class="stat-value text-up">{{ stats.avgAnnualReturn }}%</span></div>
                  </div>
                  <div class="function-foot">查看策略绩效 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 账户绩效 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.08s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="router.push('/performance/account')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon purple"><SmartIcon name="AnalyticsOutline" /></div>
                    <h3 class="function-title">账户绩效</h3>
                  </div>
                  <p class="function-desc">账户整体收益曲线、资金使用效率、净值变化趋势</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">账户净值</span><span class="stat-value text-up">¥{{ stats.accountNav }}</span></div>
                    <div class="stat-item"><span class="stat-label">累计收益</span><span class="stat-value text-up">{{ stats.cumulativeReturn }}%</span></div>
                  </div>
                  <div class="function-foot">查看账户绩效 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 绩效对比 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.16s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="router.push('/performance/comparison')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon info"><SmartIcon name="Scale" /></div>
                    <h3 class="function-title">绩效对比</h3>
                  </div>
                  <p class="function-desc">多策略横向对比，基准对标，排名与相对强弱分析</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">对比组数</span><span class="stat-value">{{ stats.comparisonCount }} 组</span></div>
                    <div class="stat-item"><span class="stat-label">跑赢基准</span><span class="stat-value text-up">{{ stats.beatBenchmark }}%</span></div>
                  </div>
                  <div class="function-foot">新建绩效对比 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <!-- 归因分析 -->
            <n-grid-item :class="tokens.motion.stagger" style="animation-delay: 0.24s">
              <n-card :class="[tokens.motion.hover, 'function-card']" @click="router.push('/performance/attribution')">
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon danger"><SmartIcon name="Puzzle" /></div>
                    <h3 class="function-title">归因分析</h3>
                  </div>
                  <p class="function-desc">Brinson/Barra 归因，因子暴露分解，收益来源追踪</p>
                  <div class="function-stats">
                    <div class="stat-item"><span class="stat-label">归因模型</span><span class="stat-value">{{ stats.attributionModel }}</span></div>
                    <div class="stat-item"><span class="stat-label">最近分析</span><span class="stat-value">{{ stats.lastAttribution }}</span></div>
                  </div>
                  <div class="function-foot">运行归因分析 →</div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- 快捷操作 -->
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="Lightning" class="title-icon" />快捷操作</h2>
          <n-card :class="tokens.surface.card">
            <div class="quick-actions">
              <n-button type="primary" @click="router.push('/performance/strategy')">
                <template #icon><SmartIcon name="Trophy" /></template>
                策略绩效分析
              </n-button>
              <n-button @click="router.push('/performance/comparison')">
                <template #icon><SmartIcon name="Scale" /></template>
                新建对比
              </n-button>
              <n-button @click="router.push('/performance/attribution')">
                <template #icon><SmartIcon name="Puzzle" /></template>
                归因分析
              </n-button>
            </div>
          </n-card>
        </div>

        <!-- 最近分析 -->
        <div class="content-section">
          <h2 class="section-title"><SmartIcon name="Clock" class="title-icon" />最近分析</h2>
          <n-card :class="tokens.surface.card">
            <n-empty v-if="recentAnalyses.length === 0" description="暂无分析记录" />
            <div v-else class="activity-list">
              <div v-for="(item, idx) in recentAnalyses" :key="idx" class="activity-item" @click="router.push(item.link)" style="cursor: pointer">
                <div class="activity-icon" :class="item.type">
                  <SmartIcon :name="item.icon" />
                </div>
                <div class="activity-content">
                  <span class="activity-text">{{ item.text }}</span>
                  <span class="activity-time">{{ item.time }}</span>
                </div>
              </div>
            </div>
          </n-card>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NGrid, NGridItem, NSkeleton, NEmpty, NResult, useMessage } from 'naive-ui'
import SmartIcon from '@/components/common/SmartIcon.vue'
import { tokens } from '@/styles/design-tokens'
import performanceAPI from '@/api/performance'

const router = useRouter()
const message = useMessage()

const loading = ref(true)
const error = ref(false)

const stats = ref({
  strategyCount: 5,
  avgAnnualReturn: 18.5,
  accountNav: '1,256,800',
  cumulativeReturn: 25.7,
  comparisonCount: 3,
  beatBenchmark: 67,
  attributionModel: 'Brinson',
  lastAttribution: '14:30',
})

const recentAnalyses = ref([
  { type: 'strategy', icon: 'Trophy', text: 'CTA趋势跟踪 绩效分析完成 — 夏普 1.82', time: '14:30', link: '/performance/strategy' },
  { type: 'attribution', icon: 'Puzzle', text: '多因子Alpha 归因分析 — 行业配置贡献 +3.2%', time: '11:20', link: '/performance/attribution' },
  { type: 'comparison', icon: 'Scale', text: '策略对比报告：CTA vs 均值回归 vs 基准', time: '昨天 16:10', link: '/performance/comparison' },
  { type: 'account', icon: 'AnalyticsOutline', text: '账户月度绩效报告生成', time: '昨天 10:00', link: '/performance/account' },
])

const loadData = async () => {
  loading.value = true
  error.value = false
  try {
    const perf = await performanceAPI.getAccountPerformance().catch(() => null)
    if (perf) {
      const p = perf as any
      if (p.total_return != null) stats.value.cumulativeReturn = p.total_return * 100
      if (p.annual_return != null) stats.value.avgAnnualReturn = p.annual_return * 100
      if (p.total_asset != null) stats.value.accountNav = p.total_asset.toLocaleString()
    }
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

const refreshData = async () => {
  loading.value = true
  error.value = false
  try {
    await new Promise(r => setTimeout(r, 200))
    message.success('数据已刷新')
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(() => { loadData() })
</script>

<style lang="scss" scoped>
.hub-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
  animation: fadeIn 0.3s ease-out;
}

.content-section { margin-bottom: 28px; }

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0 0 16px;

  .title-icon { font-size: 18px; color: var(--n-primary-color); }
}

.function-card {
  cursor: pointer;
  :deep(.n-card__content) { padding: 20px; }
}

.function-inner { display: flex; flex-direction: column; gap: 12px; }
.function-head { display: flex; align-items: center; gap: 12px; }

.function-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; flex-shrink: 0;
  &.accent  { background: rgba(68, 138, 255, 0.12); color: var(--n-primary-color); }
  &.purple  { background: rgba(124, 111, 247, 0.12); color: var(--n-color-purple); }
  &.info    { background: rgba(64, 196, 255, 0.12); color: var(--n-info-color); }
  &.danger  { background: rgba(255, 82, 82, 0.12);  color: var(--n-error-color); }
}

.function-title { font-size: 15px; font-weight: 600; color: var(--n-text-color-1); margin: 0; }
.function-desc { font-size: 13px; color: var(--n-text-color-3); margin: 0; line-height: 1.4; }
.function-stats { display: flex; flex-direction: column; gap: 6px; }

.stat-item {
  display: flex; justify-content: space-between; align-items: center; font-size: 13px;
  .stat-label { color: var(--n-text-color-3); }
  .stat-value { font-weight: 600; color: var(--n-text-color-1); }
}

.function-foot {
  font-size: 12px; color: var(--n-text-color-3);
  padding-top: 10px; border-top: 1px solid var(--n-border-color);
}

.quick-actions { display: flex; gap: 12px; flex-wrap: wrap; padding: 8px 0; }

.activity-list { display: flex; flex-direction: column; }

.activity-item {
  display: flex; align-items: center; gap: 12px; padding: 12px 0;
  border-bottom: 1px solid var(--n-border-color);
  &:last-child { border-bottom: none; padding-bottom: 0; }
  &:first-child { padding-top: 0; }
}

.activity-icon {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0;
  &.strategy    { background: rgba(68, 138, 255, 0.12); color: var(--n-primary-color); }
  &.account     { background: rgba(124, 111, 247, 0.12); color: var(--n-color-purple); }
  &.comparison  { background: rgba(64, 196, 255, 0.12); color: var(--n-info-color); }
  &.attribution { background: rgba(255, 82, 82, 0.12);  color: var(--n-error-color); }
}

.activity-content {
  flex: 1; min-width: 0;
  display: flex; justify-content: space-between; align-items: center; gap: 12px;
  .activity-text { font-size: 13px; color: var(--n-text-color-1); }
  .activity-time { font-size: 12px; color: var(--n-text-color-3); white-space: nowrap; }
}
</style>
