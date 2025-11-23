<!-- IndustryStrength.vue - 修复后的行业强弱分析页面 -->
<template>
  <div class="industry-strength-page">
    <!-- 页面标题区域 -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">行业强弱分析</h1>
          <p class="page-description">深度分析各行业板块表现与相对强度</p>
        </div>
        <div class="header-actions">
          <button class="refresh-btn" @click="refreshData" :disabled="loading">
            <Icon icon="ant-design:reload-outlined" class="refresh-icon" :class="{ refreshing: loading }"/>
            <span class="btn-text">{{ loading ? '刷新中...' : '刷新数据' }}</span>
          </button>
          <button class="back-btn" @click="handleBack">
            <Icon icon="ant-design:arrow-left-outlined"/>
            <span class="btn-text">返回</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content-with-sidebar">
      <!-- 行业强弱排名卡片 -->
      <div class="industry-card card">
        <div class="card-header">
          <h3 class="card-title">
            <Icon icon="mdi:trending-up" class="card-title-icon"/>
            行业强弱排名
          </h3>
          <!-- 数据统计信息 -->
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
        </div>
        <div class="card-body">
          <!-- 错误状态显示 -->
          <div v-if="error" class="error-state">
            <Icon icon="mdi:alert-circle-outline" class="error-icon"/>
            <p class="error-message">{{ error }}</p>
            <button class="retry-btn" @click="loadIndustryData">
              <Icon icon="mdi:reload"/>
              重新加载
            </button>
          </div>

          <!-- 空状态显示 -->
          <div v-else-if="!loading && industries.length === 0" class="empty-state">
            <Icon icon="mdi:database-off-outline" class="empty-icon"/>
            <p class="empty-message">暂无行业数据</p>
            <button class="retry-btn" @click="loadIndustryData">
              <Icon icon="mdi:reload"/>
              重新加载
            </button>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>数据加载中...</p>
          </div>

          <!-- Naive UI 表格 - 确保在数据准备好时显示 -->
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
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// ============================================================================
// Vue和相关库导入
// ============================================================================
import {computed, h, ref, onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'
import {message} from 'ant-design-vue'

import type {DataTableColumns} from 'naive-ui'
// Naive UI 组件导入
import {NButton, NDataTable, NProgress, NTag, NText} from 'naive-ui'

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
      return h('div', { class: 'industry-name-cell' }, [
        h('span', { class: 'industry-name' }, row.name),
        h('span', { class: 'industry-code' }, row.code)
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
            h(Icon, {
              icon: row.change >= 0 ? 'mdi:trending-up' : 'mdi:trending-down',
              class: 'change-icon'
            }),
            h('span', { class: 'change-text' }, changeText)
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
      return h('div', { class: 'strength-cell' }, [
        h(NProgress, {
          type: 'line',
          percentage: row.strength,
          status: getProgressStatus(row.strength),
          height: 6,
          borderRadius: 3,
          class: 'strength-progress'
        }),
        h('div', { class: 'strength-info' }, [
          h(NText, { depth: 1, class: 'strength-value' }, { default: () => row.strength.toFixed(1) }),
          h(NText, { depth: 3, class: 'strength-label' }, { default: () => getStrengthLabel(row.strength) })
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
            h(Icon, { icon: 'mdi:eye', class: 'detail-icon' }),
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

    // 修复：移除随机错误模拟，确保数据能稳定加载
    // if (Math.random() < 0.1) {
    //   throw new Error('网络连接超时，请检查网络设置')
    // }

    // 确保测试数据正确赋值
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
  console.log('查看行业详情:', industry)
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
  min-height: 100vh;
  background: $primary-bg;

  .main-content-with-sidebar {
    @include mixin.content-with-sidebar;
    margin: 0 auto;
  }
}

/* 页面头部样式 */
.page-header {
  @include mixin.page-header-base;
  margin-bottom: map.get($spacers, 6);
}

/* 行业卡片样式 */
.industry-card {
  @include mixin.card-base;
  margin-bottom: map.get($spacers, 4);
  padding: map.get($spacers, 3);

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
        color: $text-secondary;
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