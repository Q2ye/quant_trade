<template>
  <div class="industry-strength-page">
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">行业强弱分析</h1>
          <p class="page-description">深度分析各行业板块表现与相对强度</p>
        </div>
        <div class="header-actions-right">
          <a-button type="primary" @click="refreshData" :loading="loading" class="action-btn">
            <template #icon>
              <ReloadOutlined/>
            </template>
            刷新数据
          </a-button>
          <a-button class="back-btn" @click="handleBack">
            <template #icon>
              <ArrowLeftOutlined/>
            </template>
            返回
          </a-button>
        </div>
      </div>
    </div>
    <el-card class="industry-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <Icon icon="mdi:trending-up"/>
            行业强弱排名
          </span>
        </div>
      </template>

      <el-table :data="industries" height="400" v-loading="loading">
        <el-table-column prop="name" label="行业板块" width="120">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:office-building"/>
              行业板块
            </span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:chart-line"/>
              涨跌幅
            </span>
          </template>
          <template #default="{ row }">
            <span :class="row.change >= 0 ? 'up' : 'down'">
              <Icon :icon="row.change >= 0 ? 'mdi:trending-up' : 'mdi:trending-down'"/>
              {{ row.change >= 0 ? '+' : '' }}{{ row.change }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="强度指数">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:speedometer"/>
              强度指数
            </span>
          </template>
          <template #default="{ row }">
            <el-progress
                :percentage="row.strength"
                :color="getStrengthColor(row.strength)"
                :show-text="false"></el-progress>
            <div class="strength-value">
              <span>{{ row.strength }}</span>
              <span class="strength-label">{{ getStrengthLabel(row.strength) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:cog"/>
              操作
            </span>
          </template>
          <template #default="{ row }">
            <el-button type="primary" link @click="viewIndustryDetail(row)">
              <Icon icon="mdi:eye"/>
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {ref} from 'vue';
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'
import {ArrowLeftOutlined, ReloadOutlined} from '@ant-design/icons-vue'

const router = useRouter()
const loading = ref(false)

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

// 强度颜色计算
const getStrengthColor = (strength: number) => {
  if (strength > 85) return 'var(--success-color)';
  if (strength > 70) return 'var(--warning-color)';
  if (strength > 50) return 'var(--accent-color)';
  return 'var(--text-secondary)';
};

const getStrengthLabel = (strength: number) => {
  if (strength > 85) return '过热';
  if (strength > 70) return '强势';
  if (strength > 50) return '正常';
  return '弱势';
};

// 示例数据
const industries = ref([
  {name: '计算机', change: 3.2, strength: 85},
  {name: '电子', change: 2.1, strength: 78},
  {name: '医药生物', change: 1.8, strength: 72},
  {name: '通信', change: 1.5, strength: 68},
  {name: '传媒', change: -1.2, strength: 45},
  {name: '房地产', change: -2.1, strength: 35},
  {name: '银行', change: 0.5, strength: 55},
  {name: '证券', change: 1.2, strength: 62},
  {name: '保险', change: -0.8, strength: 48},
  {name: '白酒', change: 2.5, strength: 82}
])
</script>

<style scoped lang="scss">
@use '@/assets/scss/mixins';

.industry-strength-page {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100vh;
}

.page-header {
  background: var(--page-header-bg, linear-gradient(135deg, var(--accent-color) 0%, color-mix(in srgb, var(--accent-color) 60%, #6f42c1) 100%));
  color: white;
  padding: 20px 0;
  margin-bottom: 20px;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 var(--spacer-4);
    position: relative;

    .header-actions-right {
      display: flex;
      align-items: center;
      gap: 8px; /* 减小间距，使按钮更紧凑 */
      flex-shrink: 0;
    }
  }

  .title-section {
    flex: 1;

    .page-title {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
      color: white;
    }

    .page-description {
      margin: 6px 0 0 0;
      opacity: 0.9;
      font-size: 13px;
    }
  }
}

// 操作按钮样式
.action-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  border-radius: var(--border-radius, 6px);
  font-weight: 500;
  transition: all var(--transition-fast, 0.3s);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  height: 32px;
  display: flex;
  align-items: center;
  gap: 6px;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }
}

// 返回按钮样式 - 与StockList保持一致
.back-btn {
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  border-radius: var(--border-radius, 6px);
  font-weight: 500;
  transition: all var(--transition-fast, 0.3s);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  height: 32px;
  display: flex;
  align-items: center;
  gap: 6px;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
    border-color: rgba(255, 255, 255, 0.5);
    color: white;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  }

  &:active {
    transform: translateY(0);
  }
}

.industry-card {
  @include mixins.unified-card;

  :deep(.el-table) {
    @include mixins.unified-table;

    // 行业强度表格特定样式
    .strength-value {
      display: flex;
      justify-content: space-between;
      margin-top: 5px;
      font-size: 12px;
      color: var(--text-primary);
    }

    .strength-label {
      color: var(--text-secondary);
      font-size: 11px;
    }

    // 进度条样式优化
    .el-progress {
      margin-top: 4px;

      .el-progress-bar__outer {
        background-color: var(--secondary-bg);
        border-radius: var(--border-radius-sm);
      }

      .el-progress-bar__inner {
        border-radius: var(--border-radius-sm);
        transition: width var(--transition-normal);
      }
    }
  }
}

// 涨跌样式
.up {
  color: var(--success-color);
  font-weight: var(--font-weight-semibold);
}

.down {
  color: var(--danger-color);
  font-weight: var(--font-weight-semibold);
}

// 表格头部图标
.table-header {
  display: flex;
  align-items: center;
  gap: var(--spacer-1);
  font-weight: var(--font-weight-semibold);
}
</style>