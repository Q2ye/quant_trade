<!-- IndustryStrength.vue - 行业强弱分析页面 -->
<!-- 基于全局主题样式系统重构，统一使用主题变量和混入 -->
<template>
  <div class="industry-strength-page">
    <!-- 页面标题区域 - 使用全局页面头部样式 -->
    <div class="page-header-with-sidebar">
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
        </div>
        <div class="card-body">
          <!-- 行业数据表格 -->
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="table-header">
                    <Icon icon="mdi:office-building"/>
                    行业板块
                  </th>
                  <th class="table-header">
                    <Icon icon="mdi:chart-line"/>
                    涨跌幅
                  </th>
                  <th class="table-header">
                    <Icon icon="mdi:speedometer"/>
                    强度指数
                  </th>
                  <th class="table-header">
                    <Icon icon="mdi:cog"/>
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="industry in industries" :key="industry.name" class="table-row">
                  <td class="industry-name">{{ industry.name }}</td>
                  <td class="change-cell">
                    <span :class="getChangeClass(industry.change)">
                      <Icon :icon="getChangeIcon(industry.change)"/>
                      {{ industry.change >= 0 ? '+' : '' }}{{ industry.change }}%
                    </span>
                  </td>
                  <td class="strength-cell">
                    <div class="strength-progress">
                      <div
                        class="progress-bar"
                        :style="{ width: `${industry.strength}%`, backgroundColor: getStrengthColor(industry.strength) }"
                      ></div>
                    </div>
                    <div class="strength-info">
                      <span class="strength-value">{{ industry.strength }}</span>
                      <span class="strength-label">{{ getStrengthLabel(industry.strength) }}</span>
                    </div>
                  </td>
                  <td class="action-cell">
                    <button class="detail-btn" @click="viewIndustryDetail(industry)">
                      <Icon icon="mdi:eye"/>
                      详情
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>数据加载中...</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

const router = useRouter()
const loading = ref(false)

// 颜色常量定义 - 修复SCSS变量在JS中的使用问题
const COLORS = {
  SUCCESS: '#67c23a',      // $success-color
  WARNING: '#D29922',      // $warning-color
  ACCENT: '#2196F3',       // $accent-color
  TEXT_SECONDARY: '#8B949E' // $text-secondary
}

// 返回按钮处理
const handleBack = () => {
  router.go(-1)
}

// 刷新数据
const refreshData = async () => {
  loading.value = true
  try {
    // 模拟数据刷新
    await new Promise(resolve => setTimeout(resolve, 1000))
  } finally {
    loading.value = false
  }
}

// 查看行业详情
const viewIndustryDetail = (industry: any) => {
  console.log('查看行业详情:', industry)
  // 这里可以跳转到行业详情页面或打开详情对话框
}

// 涨跌幅样式类
const getChangeClass = (change: number) => {
  if (change > 0) return 'up'
  if (change < 0) return 'down'
  return 'flat'
}

// 涨跌幅图标
const getChangeIcon = (change: number) => {
  return change >= 0 ? 'mdi:trending-up' : 'mdi:trending-down'
}

// 强度颜色计算 - 修复：使用JS常量而不是SCSS变量
const getStrengthColor = (strength: number) => {
  if (strength > 85) return COLORS.SUCCESS
  if (strength > 70) return COLORS.WARNING
  if (strength > 50) return COLORS.ACCENT
  return COLORS.TEXT_SECONDARY
}

// 强度标签
const getStrengthLabel = (strength: number) => {
  if (strength > 85) return '过热'
  if (strength > 70) return '强势'
  if (strength > 50) return '正常'
  return '弱势'
}

// 示例数据
const industries = ref([
  { name: '计算机', change: 3.2, strength: 85 },
  { name: '电子', change: 2.1, strength: 78 },
  { name: '医药生物', change: 1.8, strength: 72 },
  { name: '通信', change: 1.5, strength: 68 },
  { name: '传媒', change: -1.2, strength: 45 },
  { name: '房地产', change: -2.1, strength: 35 },
  { name: '银行', change: 0.5, strength: 55 },
  { name: '证券', change: 1.2, strength: 62 },
  { name: '保险', change: -0.8, strength: 48 },
  { name: '白酒', change: 2.5, strength: 82 }
])
</script>

<style scoped lang="scss">
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color' as scssColor;

.industry-strength-page {
  min-height: 100vh;
  background: $primary-bg;
}

// 使用全局表格样式
.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: $card-bg;

  th, td {
    padding: map.get($spacers, 3);
    text-align: left;
    border-bottom: 1px solid $border-color;
  }

  th {
    background: $card-header-bg;
    font-weight: $font-weight-semibold;
    color: $text-primary;
  }

  td {
    color: $text-primary;
  }
}

.table-header {
  display: flex;
  align-items: center;
  gap: map.get($spacers, 2);
  font-weight: $font-weight-semibold;
}

.table-row {
  transition: background-color $transition-fast;

  &:hover {
    background: $hover-bg;
  }
}

// 行业名称列
.industry-name {
  font-weight: $font-weight-medium;
  color: $text-primary;
}

// 涨跌幅单元格
.change-cell {
  .up {
    color: $success-color;
    font-weight: $font-weight-semibold;
  }

  .down {
    color: $danger-color;
    font-weight: $font-weight-semibold;
  }

  .flat {
    color: $text-secondary;
  }
}

// 强度指数单元格
.strength-cell {
  display: flex;
  flex-direction: column;
  gap: map.get($spacers, 2);
}

.strength-progress {
  width: 100%;
  height: 6px;
  background: $secondary-bg;
  border-radius: $border-radius-sm;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: $border-radius-sm;
  transition: width $transition-normal;
}

.strength-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: $font-size-base - 2px;
}

.strength-value {
  font-weight: $font-weight-semibold;
  color: $text-primary;
}

.strength-label {
  color: $text-secondary;
}

// 操作按钮
.action-cell {
  .detail-btn {
    @include mixin.button-base($accent-color, white);
    padding: map.get($spacers, 1) map.get($spacers, 2);
    font-size: $font-size-base - 2px;

    &:hover {
      background: scssColor.adjust($accent-color, $lightness: -10%);
    }
  }
}

// 响应式调整
@include mixin.media-breakpoint-down(md) {
  .data-table {
    font-size: $font-size-base - 2px;

    th, td {
      padding: map.get($spacers, 2);
    }
  }

  .strength-info {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 1);
  }
}

@include mixin.media-breakpoint-down(sm) {
  .table-header {
    flex-direction: column;
    gap: map.get($spacers, 1);
  }

  .action-cell .detail-btn {
    padding: map.get($spacers, 1);
    font-size: $font-size-base - 4px;

    .btn-text {
      display: none;
    }
  }
}
</style>