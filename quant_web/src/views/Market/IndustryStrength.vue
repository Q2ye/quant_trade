<!-- IndustryStrength.vue - 行业强弱分析页面 - Naive UI 实现 -->
<template>
  <n-layout class="industry-strength-page">
    <!-- 页面标题区域 -->
    <n-layout-header class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">行业强弱分析</h1>
          <p class="page-description">深度分析各行业板块表现与相对强度</p>
        </div>
        <div class="header-actions">
          <n-button
              :loading="loading"
              @click="refreshData"
              class="refresh-btn"
          >
            <template #icon>
              <n-icon>
                <RefreshIcon/>
              </n-icon>
            </template>
            {{ loading ? '刷新中...' : '刷新数据' }}
          </n-button>
          <n-button @click="handleBack" class="back-btn">
            <template #icon>
              <n-icon>
                <ArrowBackIcon/>
              </n-icon>
            </template>
            返回
          </n-button>
        </div>
      </div>
    </n-layout-header>

    <!-- 主要内容区域 -->
    <n-layout-content class="main-content">
      <!-- 行业强弱排名卡片 -->
      <n-card class="industry-card" title="行业强弱排名">
        <template #header-extra>
          <div class="card-stats" v-if="!loading && industries.length > 0">
            <span class="stat-item">
              共 <strong>{{ industries.length }}</strong> 个行业
            </span>
            <span class="stat-item">
              强势行业: <strong class="up">{{ strongIndustriesCount }}</strong>
            </span>
            <span class="stat-item">
              弱势行业: <strong class="down">{{ weakIndustriesCount }}</strong>
            </span>
          </div>
        </template>

        <!-- 错误状态显示 -->
        <div v-if="error" class="error-state">
          <n-icon class="error-icon" :component="AlertCircleOutlineIcon"/>
          <p class="error-message">{{ error }}</p>
          <n-button type="primary" @click="loadIndustryData" class="retry-btn">
            <template #icon>
              <n-icon>
                <RefreshIcon/>
              </n-icon>
            </template>
            重新加载
          </n-button>
        </div>

        <!-- 空状态显示 -->
        <div v-else-if="!loading && industries.length === 0" class="empty-state">
          <n-icon class="empty-icon" :component="DatabaseOffOutlineIcon"/>
          <p class="empty-message">暂无行业数据</p>
          <n-button type="primary" @click="loadIndustryData" class="retry-btn">
            <template #icon>
              <n-icon>
                <RefreshIcon/>
              </n-icon>
            </template>
            重新加载
          </n-button>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <n-spin size="large"/>
          <p>数据加载中...</p>
        </div>

        <!-- Naive UI 表格 -->
        <n-data-table
            v-else
            class="naive-industry-table"
            :columns="naiveColumns"
            :data="industries"
            :bordered="false"
            :max-height="600"
            :scroll-x="800"
            size="small"
            striped
            flex-height
        />
      </n-card>
    </n-layout-content>
  </n-layout>
</template>

<script setup lang="ts">
// ============================================================================
// Vue和相关库导入
// ============================================================================
import {computed, h, onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
// Naive UI 组件导入
import {
  type DataTableColumns,
  NButton,
  NCard,
  NDataTable,
  NIcon,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NProgress,
  NSpin,
  NTag,
  NText,
  useMessage
} from 'naive-ui'

// Material Icons 导入
import {
  AccountCircleFilled as AlertCircleOutlineIcon,
  ArrowBackFilled as ArrowBackIcon,
  DataExplorationFilled as DatabaseOffOutlineIcon,
  RefreshRound as RefreshIcon,
  TrendingDownFilled as TrendingDownIcon,
  TrendingUpFilled as TrendingUpIcon,
  VisibilityFilled as VisibilityIcon
} from '@vicons/material'

// ============================================================================
// 类型定义
// ============================================================================

interface Industry {
  code: string
  name: string
  change: number
  strength: number
  category?: string
  volume?: number
  amount?: number
}

// ============================================================================
// 路由和响应式数据
// ============================================================================
const router = useRouter()
const message = useMessage()

const loading = ref(false)
const error = ref<string | null>(null)
const industries = ref<Industry[]>([])

// ============================================================================
// 计算属性
// ============================================================================

const strongIndustriesCount = computed(() => {
  return industries.value.filter(industry => industry.strength > 70).length
})

const weakIndustriesCount = computed(() => {
  return industries.value.filter(industry => industry.strength < 50).length
})

// ============================================================================
// Naive UI 表格列配置
// ============================================================================

const getChangeTagType = (change: number): 'success' | 'error' | 'warning' | 'default' => {
  if (change > 0) return 'success'
  if (change < 0) return 'error'
  return 'default'
}

const getProgressStatus = (strength: number): 'success' | 'error' | 'warning' | 'default' => {
  if (strength > 85) return 'success'
  if (strength > 70) return 'warning'
  if (strength > 50) return 'default'
  return 'error'
}

const getStrengthLabel = (strength: number): string => {
  if (strength > 85) return '过热'
  if (strength > 70) return '强势'
  if (strength > 50) return '正常'
  return '弱势'
}

const naiveColumns: DataTableColumns<Industry> = [
  {
    title: '行业板块',
    key: 'name',
    width: 150,
    fixed: 'left',
    align: 'center',
    render: (row) => {
      return h('div', {class: 'industry-name-cell'}, [
        h('span', {class: 'industry-name'}, row.name),
        h('span', {class: 'industry-code'}, row.code)
      ])
    }
  },
  {
    title: '涨跌幅',
    key: 'change',
    width: 120,
    align: 'center',
    render: (row) => {
      const changeText = `${row.change >= 0 ? '+' : ''}${row.change.toFixed(2)}%`
      return h(
          NTag,
          {
            type: getChangeTagType(row.change),
            size: 'small',
            class: 'change-tag'
          },
          {
            default: () => [
              h(NIcon, {
                component: row.change >= 0 ? TrendingUpIcon : TrendingDownIcon,
                class: 'change-icon'
              }),
              h('span', {class: 'change-text'}, changeText)
            ]
          }
      )
    }
  },
  {
    title: '强度指数',
    key: 'strength',
    width: 180,
    align: 'center',
    render: (row) => {
      return h('div', {class: 'strength-cell'}, [
        h(NProgress, {
          type: 'line',
          percentage: row.strength,
          status: getProgressStatus(row.strength),
          height: 6,
          borderRadius: 3,
          class: 'strength-progress'
        }),
        h('div', {class: 'strength-info'}, [
          h(NText, {depth: 1, class: 'strength-value'}, {default: () => row.strength.toFixed(1)}),
          h(NText, {depth: 3, class: 'strength-label'}, {default: () => getStrengthLabel(row.strength)})
        ])
      ])
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    fixed: 'right',
    align: 'center',
    render: (row) => {
      return h(
          NButton,
          {
            type: 'primary',
            size: 'small',
            class: 'detail-btn',
            onClick: () => viewIndustryDetail(row)
          },
          {
            default: () => [
              h(NIcon, {component: VisibilityIcon, class: 'detail-icon'}),
              '详情'
            ]
          }
      )
    }
  }
]

// ============================================================================
// 业务逻辑函数
// ============================================================================

const handleBack = (): void => {
  if (window.history.length > 1) {
    router.go(-1)
  } else {
    router.push('/')
  }
}

const loadIndustryData = async (): Promise<void> => {
  loading.value = true
  error.value = null

  try {
    await new Promise(resolve => setTimeout(resolve, 1500))

    // 测试数据
    industries.value = [
      {code: '801010', name: '计算机', change: 3.2, strength: 85, category: '信息技术'},
      {code: '801020', name: '电子', change: 2.1, strength: 78, category: '信息技术'},
      {code: '801030', name: '医药生物', change: 1.8, strength: 72, category: '医疗保健'},
      {code: '801040', name: '通信', change: 1.5, strength: 68, category: '信息技术'},
      {code: '801050', name: '传媒', change: -1.2, strength: 45, category: '可选消费'},
      {code: '801060', name: '房地产', change: -2.1, strength: 35, category: '金融地产'},
      {code: '801070', name: '银行', change: 0.5, strength: 55, category: '金融地产'},
      {code: '801080', name: '证券', change: 1.2, strength: 62, category: '金融地产'},
      {code: '801090', name: '保险', change: -0.8, strength: 48, category: '金融地产'},
      {code: '801100', name: '白酒', change: 2.5, strength: 82, category: '主要消费'}
    ]
    message.success('行业数据加载成功')

  } catch (err) {
    console.error('加载行业数据失败:', err)
    error.value = err instanceof Error ? err.message : '加载行业数据失败，请稍后重试'
    message.error(error.value)
    industries.value = []
  } finally {
    loading.value = false
  }
}

const refreshData = async (): Promise<void> => {
  await loadIndustryData()
}

const viewIndustryDetail = (industry: Industry): void => {
  message.info(`查看行业详情: ${industry.name}`)
}

// 组件挂载时自动加载数据
onMounted(() => {
  loadIndustryData()
})
</script>

<style scoped lang="scss">
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';

/* 页面容器样式 */
.industry-strength-page {
  @include mixin.content-with-base;

  .main-content {
    @include mixin.content-with-sidebar; // 应用带侧边栏的内容区域混入
    margin: 0 auto; // 水平居中
  }
}

// ============================================================================
// 页面头部样式 - 使用混入统一管理
// ============================================================================
.page-header {
  @include mixin.page-header-base;
}


/* 行业卡片样式 */
.industry-card {
  @include mixin.card-base;
  margin-bottom: map.get($spacers, 4);
  padding: map.get($spacers, 3);
  margin-top: map.get($spacers, 5); // 顶部外边距：使用spacers映射中的第6个值

  .card-header {
    @include mixin.card-header-base;
    padding-bottom: map.get($spacers, 2);
    margin-bottom: map.get($spacers, 2);
    border-bottom: $border-width solid $border-color;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: map.get($spacers, 2);

    .card-title {
      font-size: $font-size-base * 1.1;
      font-weight: $font-weight-semibold;
      color: $text-primary;
      margin: 0;
      display: flex;
      align-items: center;
      gap: map.get($spacers, 2);

      .card-title-icon {
        color: $accent-color;
      }
    }

    .card-stats {
      display: flex;
      align-items: center;
      gap: map.get($spacers, 3);
      font-size: $font-size-base - 1px;
      color: $text-secondary;

      .stat-item {
        strong {
          &.up {
            color: $stock-up-color;
          }

          &.down {
            color: $stock-down-color;
          }
        }
      }
    }
  }

  .card-body {
    color: $text-primary;
    position: relative;
    min-height: 200px;
    // 确保内容区域不会被其他元素覆盖
    z-index: 1;
  }
}

/* Naive UI表格样式 - 重点修复显示问题 */
.naive-industry-table {
  width: 100%;
  margin: 0 auto;
  z-index: 2;
  position: relative;

  :deep(.n-data-table) {
    background: $card-bg;
    border-radius: $border-radius;
    color: $text-primary;
    width: 100%;

    .n-data-table-thead {
      .n-data-table-th {
        background: $secondary-bg !important;
        color: $text-primary !important;
        font-weight: $font-weight-semibold;
        border-bottom: 2px solid $border-color;
        padding: map.get($spacers, 2);
        text-align: center;

        .n-data-table-th__content {
          color: $text-primary;
          font-size: $font-size-base;
        }
      }
    }

    .n-data-table-tbody {
      .n-data-table-tr {
        background: $card-bg;
        transition: background-color $transition-fast;
        color: $text-primary;

        &:hover {
          background: $hover-bg !important;
        }

        &:nth-child(even) {
          background: rgba($secondary-bg, 0.3);

          &:hover {
            background: $hover-bg !important;
          }
        }

        .n-data-table-td {
          border-bottom: 1px solid $border-color;
          color: $text-primary !important;
          padding: map.get($spacers, 2);
          text-align: center;
        }
      }
    }

    // 确保表格内容可见，修复可能的背景色覆盖问题
    .n-data-table-base-table-body {
      background: $card-bg;

      .n-data-table-td {
        color: $text-primary !important;
        background: transparent !important;
      }
    }

    // 固定列样式修复
    .n-data-table-base-table-header--fixed-left,
    .n-data-table-base-table-header--fixed-right,
    .n-data-table-base-table-body--fixed-left,
    .n-data-table-base-table-body--fixed-right {
      background: $card-bg;

      .n-data-table-th,
      .n-data-table-td {
        background: $card-bg;
        color: $text-primary !important;
      }
    }
  }

  // 单元格具体样式
  .industry-name-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;

    .industry-name {
      font-weight: $font-weight-semibold;
      color: $text-primary;
      font-size: $font-size-base;
    }

    .industry-code {
      font-size: $font-size-base - 2px;
      color: $text-secondary;
    }
  }

  .change-tag {
    display: flex;
    align-items: center;
    gap: map.get($spacers, 1);
    font-weight: $font-weight-semibold;

    .change-icon {
      font-size: $font-size-base * 1.1;
    }

    .change-text {
      font-size: $font-size-base - 1px;
    }
  }

  .strength-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: map.get($spacers, 1);

    .strength-progress {
      width: 100%;

      :deep(.n-progress-content) {
        .n-progress-graph {
          .n-progress-graph-line {
            border-radius: $border-radius-sm;
          }
        }
      }
    }

    .strength-info {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      font-size: $font-size-base - 2px;

      .strength-value {
        font-weight: $font-weight-semibold;
        color: $text-primary;
      }

      .strength-label {
        color: #6b7280;
      }
    }
  }

  .detail-btn {
    @include mixin.button-base($accent-color, white);
    padding: map.get($spacers, 1) map.get($spacers, 2);
    font-size: $font-size-base - 2px;
    display: flex;
    align-items: center;
    gap: map.get($spacers, 1);

    &:hover {
      background: darken($accent-color, 10%);
      transform: translateY(-1px);
    }

    .detail-icon {
      font-size: $font-size-base - 1px;
    }
  }
}

/* 加载状态样式 */
.loading-state {
  @include mixin.flex-center(column);
  padding: map.get($spacers, 5);
  color: $text-secondary;

  .loading-spinner {
    @include mixin.loading-spinner(2em);
    margin-bottom: map.get($spacers, 2);
    color: $accent-color;
  }
}

/* 错误状态样式 */
.error-state {
  @include mixin.flex-center(column);
  padding: map.get($spacers, 5);
  color: $error-color;
  text-align: center;
  gap: 16px;

  .error-icon {
    font-size: 3em;
    margin-bottom: map.get($spacers, 3);
    opacity: 0.7;
  }

  .error-message {
    margin-bottom: map.get($spacers, 3);
    font-size: $font-size-base;
  }
}

/* 空状态样式 */
.empty-state {
  @include mixin.flex-center(column);
  padding: map.get($spacers, 5);
  color: $text-secondary;
  text-align: center;

  .empty-icon {
    font-size: 3em;
    margin-bottom: map.get($spacers, 3);
    opacity: 0.5;
  }

  .empty-message {
    margin-bottom: map.get($spacers, 3);
    font-size: $font-size-base;
  }
}

/* 重试按钮样式 */
.retry-btn {
  @include mixin.button-base($accent-color, white);
  display: flex;
  align-items: center;
  gap: map.get($spacers, 1);
  padding: map.get($spacers, 2) map.get($spacers, 3);

  &:hover {
    background: darken($accent-color, 10%);
  }
}
</style>