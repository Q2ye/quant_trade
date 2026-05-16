<!-- IndexDetail.vue - 使用 Naive UI 重构 -->
<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import {
  NCard,
  NTabs,
  NTabPane,
  NDescriptions,
  NDescriptionsItem,
  NTag,
  NGrid,
  NGridItem,
  NStatistic,
  NSpace,
  NIcon,
  NButton,
  NResult,
  useLoadingBar,
} from "naive-ui";
import SmartIcon from "@/components/SmartIcon.vue";

const route = useRoute();
const indexCode = ref(route.params.code as string);
const loadingBar = useLoadingBar();

// 指数详情接口
interface IndexDetail {
  ts_code: string;
  name: string;
  fullname: string;
  market: string;
  publisher: string;
  category: string;
  base_date: string;
  base_point: number;
  list_date: string;
  current_point: number;
  change: number;
  change_percent: number;
  open: number;
  high: number;
  low: number;
  pre_close: number;
  volume: number;
  amount: number;
  pe: number;
  pb: number;
  components_count: number;
}

const loading = ref(false);
const error = ref(false);
const indexDetail = ref<IndexDetail | null>(null);
const activeTab = ref("overview");

// 加载指数详情
const loadIndexDetail = async () => {
  loading.value = true;
  error.value = false;
  loadingBar.start();
  try {
    const response = await fetch(`/api/market/indexes/${indexCode.value}`);
    indexDetail.value = await response.json();
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
    loadingBar.finish();
  }
};

// 计算涨跌颜色样式
const getChangeColor = (change?: number) => {
  if (!change && change !== 0) return "";
  return change >= 0 ? "text-green-600" : "text-red-600";
};

// 计算统计值样式
const getStatisticStyle = (value?: number) => {
  if (!value && value !== 0) return {};
  return {
    color: value >= 0 ? "var(--n-success-color)" : "var(--n-error-color)",
  };
};

onMounted(() => {
  loadIndexDetail();
});
</script>

<template>
  <div class="index-detail-page bg-gradient-mesh bg-noise">
    <NCard :loading="loading" class="detail-card">
      <!-- 标题区域 -->
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <h2 class="page-title">
              {{ indexDetail?.name || "指数详情" }}
              <span class="index-code">
                {{ indexDetail?.ts_code }}
              </span>
            </h2>
          </div>
          <div v-if="indexDetail" class="header-right">
            <div class="price-display">
              <span class="current-price">{{
                indexDetail.current_point?.toFixed(2)
              }}</span>
              <span
                :class="[
                  'price-change',
                  getChangeColor(indexDetail.change_percent),
                ]"
              >
                {{ indexDetail.change >= 0 ? "+" : ""
                }}{{ indexDetail.change?.toFixed(2) }} ({{
                  indexDetail.change_percent >= 0 ? "+" : ""
                }}{{ indexDetail.change_percent?.toFixed(2) }}%)
              </span>
            </div>
          </div>
        </div>
      </template>

      <!-- 标签页 -->
      <n-result
        v-if="error"
        status="500"
        title="数据加载失败"
        description="请检查网络连接后重试"
      >
        <template #footer>
          <n-button type="primary" @click="loadIndexDetail">重试</n-button>
        </template>
      </n-result>

      <NTabs v-else v-model:value="activeTab" class="detail-tabs">
        <NTabPane name="overview" tab="概览">
          <!-- 基本信息 -->
          <NDescriptions
            label-placement="left"
            :column="2"
            bordered
            class="basic-info"
          >
            <NDescriptionsItem label="指数全称">
              {{ indexDetail?.fullname }}
            </NDescriptionsItem>
            <NDescriptionsItem label="市场">
              <NTag :bordered="false" type="info" size="small">
                {{ indexDetail?.market }}
              </NTag>
            </NDescriptionsItem>
            <NDescriptionsItem label="发布机构">
              {{ indexDetail?.publisher }}
            </NDescriptionsItem>
            <NDescriptionsItem label="分类">
              {{ indexDetail?.category }}
            </NDescriptionsItem>
            <NDescriptionsItem label="基日">
              {{ indexDetail?.base_date }}
            </NDescriptionsItem>
            <NDescriptionsItem label="基点">
              {{ indexDetail?.base_point }}
            </NDescriptionsItem>
            <NDescriptionsItem label="成分股数量">
              {{ indexDetail?.components_count }} 只
            </NDescriptionsItem>
          </NDescriptions>

          <!-- 行情数据 -->
          <NGrid :cols="4" :x-gap="16" class="market-data">
            <NGridItem>
              <NStatistic
                label="开盘"
                :value="indexDetail?.open"
                :precision="2"
                :value-style="getStatisticStyle(indexDetail?.open)"
              />
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="最高"
                :value="indexDetail?.high"
                :precision="2"
                :value-style="getStatisticStyle(indexDetail?.change)"
              />
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="最低"
                :value="indexDetail?.low"
                :precision="2"
                :value-style="getStatisticStyle(indexDetail?.change)"
              />
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="昨收"
                :value="indexDetail?.pre_close"
                :precision="2"
              />
            </NGridItem>
          </NGrid>

          <!-- 其他数据 -->
          <NGrid :cols="4" :x-gap="16" class="additional-data">
            <NGridItem>
              <NStatistic
                label="成交量(亿)"
                :value="
                  indexDetail?.volume ? indexDetail.volume / 100000000 : 0
                "
                :precision="2"
              />
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="成交额(亿)"
                :value="
                  indexDetail?.amount ? indexDetail.amount / 100000000 : 0
                "
                :precision="2"
              />
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="市盈率(PE)"
                :value="indexDetail?.pe"
                :precision="2"
              />
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="市净率(PB)"
                :value="indexDetail?.pb"
                :precision="2"
              />
            </NGridItem>
          </NGrid>
        </NTabPane>

        <NTabPane name="chart" tab="图表分析">
          <div class="chart-container">
            <!-- 图表展示区域 -->
            <div class="chart-placeholder">
              <NSpace vertical align="center">
                <NIcon size="48" color="#ccc">
                  <SmartIcon name="BarChart" />
                </NIcon>
                <div style="color: #999">指数图表展示区域</div>
              </NSpace>
            </div>
          </div>
        </NTabPane>

        <NTabPane name="components" tab="成分股">
          <div class="components-container">
            <!-- 成分股列表 -->
            <div class="components-placeholder">
              <div style="color: #999">成分股列表展示区域</div>
            </div>
          </div>
        </NTabPane>
      </NTabs>
    </NCard>
  </div>
</template>

<style scoped lang="scss">
@use "sass:map";
@use "@/styles/variables" as *;
@use "@/styles/mixins" as mixin;

.index-detail-page {
  @include mixin.content-with-base;
}

.detail-card {
  @include mixin.card-base;
  padding: map.get($spacers, 4);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: map.get($spacers, 3);
  border-bottom: $border-width solid var(--n-border-color);
  margin-bottom: map.get($spacers, 4);
}

.header-left {
  flex: 1;
}

.page-title {
  margin: 0;
  font-size: $font-size-base * 1.5;
  font-weight: 600;
  color: var(--n-text-color-base);

  .index-code {
    font-size: $font-size-base;
    color: var(--n-text-color-2);
    margin-left: map.get($spacers, 2);
  }
}

.price-display {
  text-align: right;
}

.current-price {
  display: block;
  font-size: $font-size-base * 2;
  font-weight: 700;
  color: var(--n-text-color-base);
  margin-bottom: map.get($spacers, 1);
}

.price-change {
  display: block;
  font-size: $font-size-base * 1.1;
  font-weight: 600;
}

// 标签页样式
.detail-tabs {
  :deep(.n-tabs-nav) {
    margin-bottom: map.get($spacers, 4);

    .n-tabs-tab {
      font-weight: 500;

      &.n-tabs-tab--active {
        .n-tabs-tab__label {
          color: var(--n-primary-color);
        }
      }
    }

    .n-tabs-bar {
      background: var(--n-primary-color);
    }
  }
}

.basic-info {
  margin-bottom: map.get($spacers, 5);
}

.market-data,
.additional-data {
  margin-top: map.get($spacers, 4);
}

.chart-container,
.components-container {
  margin-top: map.get($spacers, 3);
}

.chart-placeholder,
.components-placeholder {
  height: 400px;
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  display: flex;
  align-items: center;
  justify-content: center;
  border: $border-width dashed var(--n-border-color);
}

// 响应式调整
@include mixin.media-breakpoint-down(lg) {
  .page-header {
    flex-direction: column;
    gap: map.get($spacers, 3);
    text-align: center;
  }

  .price-display {
    text-align: center;
  }
}

@include mixin.media-breakpoint-down(md) {
  .current-price {
    font-size: $font-size-base * 1.5;
  }

  .price-change {
    font-size: $font-size-base;
  }
}
</style>
