<!--
  FactorHub.vue — 因子研究枢纽页
  功能卡片 + 快捷操作 + 最近活动
-->
<template>
  <div class="hub-page scrollbar-hide">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">因子研究</h1>
          <p class="page-description">
            探索量化因子、管理因子库，为策略构建提供数据驱动的研究基础
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
                @click="router.push('/research/factor-research')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon purple">
                      <SmartIcon name="Flask" />
                    </div>
                    <h3 class="function-title">因子探索</h3>
                  </div>
                  <p class="function-desc">
                    快速测试和比较量化因子，发现有效的 alpha 因子
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">最近研究</span
                      ><span class="stat-value"
                        >{{ stats.researchCount }} 个因子</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">有效因子</span
                      ><span class="stat-value text-up"
                        >{{ stats.activeCount }} 个</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最近更新</span
                      ><span class="stat-value">{{
                        stats.researchUpdateTime
                      }}</span>
                    </div>
                  </div>
                  <div class="function-foot">进入因子探索工作室 →</div>
                </div>
              </n-card>
            </n-grid-item>
            <n-grid-item
              :class="tokens.motion.stagger"
              style="animation-delay: 0.08s"
            >
              <n-card
                :class="[tokens.motion.hover, 'function-card']"
                @click="router.push('/research/factor-library')"
              >
                <div class="function-inner">
                  <div class="function-head">
                    <div class="function-icon accent">
                      <SmartIcon name="Options" />
                    </div>
                    <h3 class="function-title">因子库</h3>
                  </div>
                  <p class="function-desc">
                    管理量化因子库，支持新建、导入导出和批量操作
                  </p>
                  <div class="function-stats">
                    <div class="stat-item">
                      <span class="stat-label">入库因子</span
                      ><span class="stat-value"
                        >{{ stats.libraryCount }} 个</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">分类覆盖</span
                      ><span class="stat-value"
                        >{{ stats.categoryCount }} 类</span
                      >
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最近入库</span
                      ><span class="stat-value">{{
                        stats.libraryUpdateTime
                      }}</span>
                    </div>
                  </div>
                  <div class="function-foot">管理因子库 →</div>
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
                @click="router.push('/research/factor-research')"
              >
                <template #icon><SmartIcon name="Flask" /></template>
                快速因子测试
              </n-button>
              <n-button @click="router.push('/research/factor-library')">
                <template #icon><SmartIcon name="Plus" /></template>
                新建因子
              </n-button>
              <n-button @click="router.push('/strategy/build')">
                <template #icon><SmartIcon name="Cube" /></template>
                去构建策略
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
import dataAPI from "@/api/data";

const router = useRouter();
const message = useMessage();

const loading = ref(true);
const error = ref(false);

const stats = ref({
  researchCount: 12,
  activeCount: 5,
  researchUpdateTime: "10:30",
  libraryCount: 28,
  categoryCount: 6,
  libraryUpdateTime: "09:45",
});

const recentActivities = ref([
  {
    type: "research",
    icon: "Flask",
    text: '因子 "动量反转" 测试完成，夏普比率 1.82',
    time: "10:30",
  },
  {
    type: "library",
    icon: "Options",
    text: "导入 3 个技术指标因子到因子库",
    time: "09:45",
  },
  {
    type: "research",
    icon: "Flask",
    text: '因子 "波动率聚集" 研究已保存',
    time: "昨天 16:20",
  },
  {
    type: "library",
    icon: "Options",
    text: '因子 "流动性冲击" 分类更新',
    time: "昨天 14:10",
  },
]);

const loadData = async () => {
  loading.value = true;
  error.value = false;
  try {
    const stocks = await dataAPI.getStockList().catch(() => []);
    if (Array.isArray(stocks) && stocks.length > 0) {
      stats.value.libraryCount = stocks.length;
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
    await dataAPI.getStockList().catch(() => []);
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

/* 快捷操作 */
.quick-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 0;
}

/* 最近活动 */
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
  &.research {
    background: rgba(124, 111, 247, 0.12);
    color: var(--color-purple, #7c6ff7);
  }
  &.library {
    background: rgba(68, 138, 255, 0.12);
    color: var(--color-primary, #448aff);
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
