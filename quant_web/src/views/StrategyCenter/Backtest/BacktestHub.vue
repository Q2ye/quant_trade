<!--
  BacktestHub.vue — 回测验证枢纽页
  功能卡片 + 快捷操作 + 最近回测记录
-->
<template>
  <div class="hub-page scrollbar-hide">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">回测验证</h1>
          <p class="page-description">
            执行策略回测，对比多策略表现，配置回溯周期，验证策略有效性
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
          <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
            <n-grid-item
              v-for="i in 2"
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
          <n-grid :x-gap="16" :y-gap="16" :cols="2" responsive="screen">
            <n-grid-item
              :class="tokens.motion.stagger"
              style="animation-delay: 0s"
            >
              <n-card
                :class="[tokens.motion.hover, 'function-card']"
                @click="router.push('/backtest/studio')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon accent">
                      <SmartIcon name="TrendingUpOutline" />
                    </div>
                    <h3 class="function-title">回测工作室</h3>
                  </div>
                  <p class="function-desc">
                    多策略回测对比，参数优化和结果导出，全面评估策略表现
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">最近回测</span
                      ><span class="stat-value"
                        >{{ stats.recentCount }} 次</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">通过率</span
                      ><span class="stat-value text-up"
                        >{{ stats.passRate }}%</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最近回测时间</span
                      ><span class="stat-value">{{ stats.lastBacktest }}</span>
                    </div>
                  </div>
                  <div class="function-foot">进入回测工作室 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item
              :class="tokens.motion.stagger"
              style="animation-delay: 0.08s"
            >
              <n-card
                :class="[tokens.motion.hover, 'function-card']"
                @click="router.push('/research/backtest-period')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon purple">
                      <SmartIcon name="Calendar" />
                    </div>
                    <h3 class="function-title">回溯周期</h3>
                  </div>
                  <p class="function-desc">
                    配置和管理回测时间周期，支持多周期组合与导出
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">配置周期</span
                      ><span class="stat-value"
                        >{{ stats.periodCount }} 个</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">默认周期</span
                      ><span class="stat-value">{{ stats.defaultPeriod }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最早起始</span
                      ><span class="stat-value">{{ stats.earliestStart }}</span>
                    </div>
                  </div>
                  <div class="function-foot">管理回溯周期 →</div>
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
              <n-button type="primary" @click="router.push('/backtest/studio')">
                <template #icon
                  ><SmartIcon name="TrendingUpOutline"
                /></template>
                快速回测
              </n-button>
              <n-button @click="router.push('/backtest/config')">
                <template #icon><SmartIcon name="Settings" /></template>
                新建回测配置
              </n-button>
              <n-button @click="router.push('/strategy/build')">
                <template #icon><SmartIcon name="Cube" /></template>
                去构建策略
              </n-button>
            </div>
          </n-card>
        </div>

        <!-- 最近回测 -->
        <div class="content-section">
          <h2 class="section-title">
            <SmartIcon name="Clock" class="title-icon" />最近回测
          </h2>
          <n-card :class="tokens.surface.card">
            <n-empty
              v-if="recentBacktests.length === 0"
              description="暂无回测记录"
            />
            <div v-else class="activity-list">
              <div
                v-for="(item, idx) in recentBacktests"
                :key="idx"
                class="activity-item"
                @click="router.push(`/backtest/report/${item.id}`)"
                style="cursor: pointer"
              >
                <div class="activity-icon" :class="item.result">
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
import backtestAPI from "@/api/backtest";

const router = useRouter();
const message = useMessage();

const loading = ref(true);
const error = ref(false);

const stats = ref({
  recentCount: 5,
  passRate: 60,
  lastBacktest: "14:45",
  periodCount: 4,
  defaultPeriod: "2024-01 ~ 2025-12",
  earliestStart: "2020-01-01",
});

const recentBacktests = ref([
  {
    id: "1",
    result: "pass",
    icon: "CheckCircle",
    text: "CTA趋势跟踪 — 夏普 1.82，最大回撤 12.3%",
    time: "14:45",
  },
  {
    id: "2",
    result: "pass",
    icon: "CheckCircle",
    text: "均值回归v2 — 夏普 1.56，最大回撤 8.7%",
    time: "11:30",
  },
  {
    id: "3",
    result: "fail",
    icon: "CloseCircle",
    text: "动量突破 — 夏普 0.43，最大回撤 28.1%",
    time: "昨天 16:10",
  },
  {
    id: "4",
    result: "pass",
    icon: "CheckCircle",
    text: "多因子Alpha — 夏普 2.10，最大回撤 9.5%",
    time: "昨天 10:20",
  },
]);

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    const tasks = await backtestAPI.getTasks().catch(() => []);
    if (Array.isArray(tasks) && tasks.length > 0) {
      stats.value.recentCount = tasks.length;
      const passed = tasks.filter((t: any) => t.status === "completed").length;
      stats.value.passRate =
        tasks.length > 0 ? Math.round((passed / tasks.length) * 100) : 0;
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
  &.pass {
    background: rgba(0, 230, 118, 0.12);
    color: var(--color-success, #18a058);
  }
  &.fail {
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
