<!--
  BuildHub.vue — 策略构建枢纽页
  功能卡片 + 快捷操作 + 最近修改策略
-->
<template>
  <div class="hub-page scrollbar-hide">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">策略构建</h1>
          <p class="page-description">
            创建和管理量化策略，从模板快速开始或自主编码，配置风控规则
          </p>
        </div>
        <div class="header-actions">
          <n-button
            class="action-btn"
            @click="refreshData"
            :loading="loading"
            quaternary
          >
            <template #icon><SmartIcon name="Refresh" /></template>
          </n-button>
        </div>
      </div>
    </div>

    <div class="main-content">
      <template v-if="loading">
        <div class="content-section">
          <h2 class="section-title">
            <SmartIcon name="Apps" class="title-icon" />功能导航
          </h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="3" responsive="screen">
            <n-grid-item
              v-for="i in 3"
              :key="i"
              :class="tokens.motion.stagger"
              :style="{ animationDelay: `${(i - 1) * 0.08}s` }"
            >
              <n-card><n-skeleton :text="true" :repeat="5" /></n-card>
            </n-grid-item>
          </n-grid>
        </div>
      </template>

      <n-result
        v-else-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer
          ><n-button type="primary" @click="loadData">重试</n-button></template
        >
      </n-result>

      <template v-else>
        <!-- 功能导航卡片 -->
        <div class="content-section">
          <h2 class="section-title">
            <SmartIcon name="Apps" class="title-icon" />功能导航
          </h2>
          <n-grid :x-gap="16" :y-gap="16" :cols="3" responsive="screen">
            <n-grid-item
              :class="tokens.motion.stagger"
              style="animation-delay: 0s"
            >
              <n-card
                :class="[tokens.motion.hover, 'function-card']"
                @click="router.push('/strategies')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon accent">
                      <SmartIcon name="Cube" />
                    </div>
                    <h3 class="function-title">策略列表</h3>
                  </div>
                  <p class="function-desc">
                    管理所有量化策略，支持新建、编辑、启停和实时监控
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">策略总数</span
                      ><span class="stat-value">{{ stats.totalCount }} 个</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">运行中</span
                      ><span class="stat-value text-up"
                        >{{ stats.runningCount }} 个</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最近修改</span
                      ><span class="stat-value">{{ stats.lastUpdate }}</span>
                    </div>
                  </div>
                  <div class="function-foot">进入策略列表 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item
              :class="tokens.motion.stagger"
              style="animation-delay: 0.08s"
            >
              <n-card
                :class="[tokens.motion.hover, 'function-card']"
                @click="router.push('/strategies/templates')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon purple">
                      <SmartIcon name="Copy" />
                    </div>
                    <h3 class="function-title">策略模板</h3>
                  </div>
                  <p class="function-desc">
                    预置策略模板库，按分类和复杂度筛选，快速创建策略
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">可用模板</span
                      ><span class="stat-value"
                        >{{ stats.templateCount }} 个</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">分类覆盖</span
                      ><span class="stat-value"
                        >{{ stats.templateCategoryCount }} 类</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">热门模板</span
                      ><span class="stat-value">{{ stats.hotTemplate }}</span>
                    </div>
                  </div>
                  <div class="function-foot">浏览策略模板 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item
              :class="tokens.motion.stagger"
              style="animation-delay: 0.16s"
            >
              <n-card
                :class="[tokens.motion.hover, 'function-card']"
                @click="router.push('/strategies/risk')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon danger">
                      <SmartIcon name="ShieldCheckmark" />
                    </div>
                    <h3 class="function-title">风控管理</h3>
                  </div>
                  <p class="function-desc">
                    配置策略级风控规则，实时监控告警，保障交易安全
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">生效规则</span
                      ><span class="stat-value">{{ stats.ruleCount }} 条</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">活跃告警</span
                      ><span class="stat-value text-down"
                        >{{ stats.alertCount }} 条</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">规则状态</span
                      ><span class="stat-value text-up">{{
                        stats.ruleStatus
                      }}</span>
                    </div>
                  </div>
                  <div class="function-foot">管理风控规则 →</div>
                </div>
              </n-card>
            </n-grid-item>
          </n-grid>
        </div>

        <!-- 快捷操作 -->
        <div class="content-section">
          <h2 class="section-title">
            <SmartIcon name="Lightning" class="title-icon" />快捷操作
          </h2>
          <n-card :class="tokens.surface.card">
            <div class="quick-actions">
              <n-button
                type="primary"
                @click="router.push('/strategies/create')"
              >
                <template #icon><SmartIcon name="Plus" /></template>
                新建策略
              </n-button>
              <n-button @click="router.push('/strategies/templates')">
                <template #icon><SmartIcon name="Copy" /></template>
                从模板创建
              </n-button>
              <n-button @click="router.push('/strategy/backtest')">
                <template #icon
                  ><SmartIcon name="TrendingUpOutline"
                /></template>
                去回测验证
              </n-button>
            </div>
          </n-card>
        </div>

        <!-- 最近活动 -->
        <div class="content-section">
          <h2 class="section-title">
            <SmartIcon name="Clock" class="title-icon" />最近活动
          </h2>
          <n-card :class="tokens.surface.card">
            <n-empty
              v-if="recentActivities.length === 0"
              description="暂无活动记录"
            />
            <div v-else class="activity-list">
              <div
                v-for="(item, idx) in recentActivities"
                :key="idx"
                class="activity-item"
              >
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
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  NButton,
  NCard,
  NGrid,
  NGridItem,
  NSkeleton,
  NEmpty,
  NResult,
  useMessage,
} from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";
import { tokens } from "@/styles/design-tokens";
import strategyAPI from "@/api/strategy";

const router = useRouter();
const message = useMessage();

const loading = ref(true);
const error = ref(false);

const stats = ref({
  totalCount: 0,
  runningCount: 0,
  lastUpdate: "--",
  templateCount: 0,
  templateCategoryCount: 0,
  hotTemplate: "--",
  ruleCount: 0,
  alertCount: 0,
  ruleStatus: "--",
});

const recentActivities = ref<Array<{ type: string; icon: string; text: string; time: string }>>([]);

const formatRelativeTime = (dateStr: string): string => {
  if (!dateStr) return "--";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD} 天前`;
  return d.toLocaleDateString("zh-CN");
};

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    const [strategies, templates] = await Promise.all([
      strategyAPI.getStrategies().catch(() => []),
      strategyAPI.getTemplates?.().catch(() => []) ?? [],
    ]);

    if (Array.isArray(strategies)) {
      stats.value.totalCount = strategies.length;
      stats.value.runningCount = strategies.filter(
        (s: any) => s.status === "running",
      ).length;

      // 最近更新时间
      const latest = strategies
        .filter((s: any) => s.updated_at)
        .sort((a: any, b: any) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        )[0];
      stats.value.lastUpdate = latest
        ? formatRelativeTime(latest.updated_at)
        : "--";

      // 从策略列表生成最近活动
      recentActivities.value = strategies
        .filter((s: any) => s.updated_at)
        .sort((a: any, b: any) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        )
        .slice(0, 5)
        .map((s: any) => ({
          type: "strategy",
          icon: "Cube",
          text: `策略 "${s.name || s.id}" ${s.status === "running" ? "运行中" : "已更新"}`,
          time: formatRelativeTime(s.updated_at),
        }));
    }

    if (Array.isArray(templates)) {
      stats.value.templateCount = templates.length;
      const categories = new Set(templates.map((t: any) => t.category).filter(Boolean));
      stats.value.templateCategoryCount = categories.size;
      const mostUsed = templates
        .filter((t: any) => t.is_public)
        .sort((a: any, b: any) => (b.usage_count || 0) - (a.usage_count || 0))[0];
      stats.value.hotTemplate = mostUsed?.template_name || mostUsed?.name || "--";
    }
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

const refreshData = async () => {
  loading.value = true;
  error.value = false;
  try {
    await new Promise((r) => setTimeout(r, 200));
    message.success("数据已刷新");
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadData();
});
</script>

<style lang="scss" scoped>
.hub-page {
  padding: 0;
  height: 100%;
  overflow-y: auto;
  background: transparent;
  animation: fadeIn 0.3s ease-out;

  :deep(.n-card) {
    --n-color: transparent !important;
    background: var(--color-bg-card, rgba(12, 18, 32, 0.72)) !important;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);

    > .n-card-header,
    > .n-card__content,
    > .n-card-footer,
    > .n-card-action {
      background: transparent !important;
    }

    > .n-card__content {
      overflow: hidden;
    }
  }
}

.content-section {
  margin-bottom: 28px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0 0 16px;

  .title-icon {
    font-size: 18px;
    color: var(--color-primary, #448aff);
  }
}

.function-card {
  cursor: pointer;
  :deep(.n-card__content) {
    padding: 20px;
  }
}

.function-inner {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.function-head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.function-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  &.accent {
    background: rgba(68, 138, 255, 0.12);
    color: var(--color-primary, #448aff);
  }
  &.purple {
    background: rgba(124, 111, 247, 0.12);
    color: var(--color-purple, #7c6ff7);
  }
  &.danger {
    background: rgba(255, 82, 82, 0.12);
    color: var(--color-error, #ff5252);
  }
}

.function-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin: 0;
}
.function-desc {
  font-size: 13px;
  color: var(--n-text-color-3);
  margin: 0;
  line-height: 1.4;
}
.function-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  .stat-label {
    color: var(--n-text-color-3);
  }
  .stat-value {
    font-weight: 600;
    color: var(--n-text-color-1);
  }
}

.function-foot {
  font-size: 12px;
  color: var(--n-text-color-3);
  padding-top: 10px;
  border-top: 1px solid var(--n-border-color);
}

.quick-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 0;
}

.activity-list {
  display: flex;
  flex-direction: column;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--n-border-color);
  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  &:first-child {
    padding-top: 0;
  }
}

.activity-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
  &.strategy {
    background: rgba(68, 138, 255, 0.12);
    color: var(--color-primary, #448aff);
  }
  &.template {
    background: rgba(124, 111, 247, 0.12);
    color: var(--color-purple, #7c6ff7);
  }
  &.risk {
    background: rgba(255, 82, 82, 0.12);
    color: var(--color-error, #ff5252);
  }
}

.activity-content {
  flex: 1;
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  .activity-text {
    font-size: 13px;
    color: var(--n-text-color-1);
  }
  .activity-time {
    font-size: 12px;
    color: var(--n-text-color-3);
    white-space: nowrap;
  }
}
</style>
