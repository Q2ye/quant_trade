<template>
  <div class="industry-strength-page">
    <div class="page-header">
      <div class="header-content">
        <div class="header-left">
          <el-button
            class="back-btn"
            @click="handleBack"
            text
          >
            <Icon icon="mdi:arrow-left" />
            返回
          </el-button>
          <h1 class="page-title">
            <Icon icon="mdi:chart-tree" />
            行业强弱分析
          </h1>
        </div>
        <div class="header-actions">
          <el-button type="primary" @click="refreshData">
            <Icon icon="mdi:refresh" />
            刷新数据
          </el-button>
        </div>
      </div>
    </div>

    <el-card class="industry-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <Icon icon="mdi:trending-up" />
            行业强弱排名
          </span>
        </div>
      </template>

      <el-table :data="industries" height="400" v-loading="loading">
        <el-table-column prop="name" label="行业板块" width="120">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:office-building" />
              行业板块
            </span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌幅">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:chart-line" />
              涨跌幅
            </span>
          </template>
          <template #default="{ row }">
            <span :class="row.change >= 0 ? 'up' : 'down'">
              <Icon :icon="row.change >= 0 ? 'mdi:trending-up' : 'mdi:trending-down'" />
              {{ row.change >= 0 ? '+' : '' }}{{ row.change }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="强度指数">
          <template #header>
            <span class="table-header">
              <Icon icon="mdi:speedometer" />
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
              <Icon icon="mdi:cog" />
              操作
            </span>
          </template>
          <template #default="{ row }">
            <el-button type="primary" link @click="viewIndustryDetail(row)">
              <Icon icon="mdi:eye" />
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'

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
.industry-strength-page {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100vh;
}

.page-header {
  margin-bottom: var(--spacer-4);

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-left {
      display: flex;
      align-items: center;
      gap: var(--spacer-3);
    }

    .back-btn {
      display: flex;
      align-items: center;
      gap: var(--spacer-1);
      color: var(--text-secondary);
      border: 1px solid var(--border-color);
      background: var(--secondary-bg);
      transition: all var(--transition-fast);

      &:hover {
        color: var(--accent-color);
        border-color: var(--accent-color);
        background: var(--hover-bg);
      }
    }

    .page-title {
      display: flex;
      align-items: center;
      gap: var(--spacer-2);
      margin: 0;
      color: var(--text-primary);
      font-size: 1.5rem;
      font-weight: var(--font-weight-semibold);
    }

    .header-actions {
      display: flex;
      gap: var(--spacer-2);
    }
  }
}

.industry-card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius);
  box-shadow: var(--card-shadow);

  :deep(.el-card__header) {
    background: var(--secondary-bg);
    border-bottom: 1px solid var(--border-color);
    padding: var(--spacer-3);
  }

  :deep(.el-card__body) {
    padding: var(--spacer-3);
  }

  .card-header {
    .card-title {
      display: flex;
      align-items: center;
      gap: var(--spacer-2);
      color: var(--text-primary);
      font-weight: var(--font-weight-semibold);
    }
  }
}

.table-header {
  display: flex;
  align-items: center;
  gap: var(--spacer-1);
  font-weight: var(--font-weight-semibold);
}

.up {
  display: flex;
  align-items: center;
  gap: var(--spacer-1);
  color: var(--success-color);
  font-weight: var(--font-weight-semibold);
}

.down {
  display: flex;
  align-items: center;
  gap: var(--spacer-1);
  color: var(--danger-color);
  font-weight: var(--font-weight-semibold);
}

.strength-value {
  display: flex;
  justify-content: space-between;
  margin-top: 5px;
  font-size: 12px;
  color: var(--text-primary);
}

.strength-label {
  color: var(--text-secondary);
}

// 表格样式优化
:deep(.el-table) {
  background: var(--card-bg);
  color: var(--text-primary);

  .el-table__header {
    th {
      background: var(--secondary-bg);
      color: var(--text-primary);
      font-weight: var(--font-weight-semibold);
    }
  }

  .el-table__body {
    tr:hover > td {
      background: var(--hover-bg) !important;
    }
  }
}

// 按钮样式优化
:deep(.el-button) {
  display: flex;
  align-items: center;
  gap: var(--spacer-1);
}

// 进度条样式优化
:deep(.el-progress-bar) {
  padding-right: 0;
}

:deep(.el-progress-bar__outer) {
  background-color: var(--secondary-bg);
  border-radius: var(--border-radius-sm);
}

:deep(.el-progress-bar__inner) {
  border-radius: var(--border-radius-sm);
  transition: width var(--transition-normal);
}
</style>