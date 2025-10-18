<template>
  <div class="stock-detail-panel" v-loading="loading">
    <!-- 股票基本信息 -->
    <div class="stock-basic-info">
      <div class="stock-header">
        <h3 class="stock-name">{{ stockName }}</h3>
        <span class="stock-code">{{ stockCode }}</span>
      </div>
      <div class="stock-price">
        <div class="current-price">¥{{ currentPrice?.toFixed(2) }}</div>
        <div class="price-change" :class="changeClass">
          {{ priceChange > 0 ? '+' : '' }}{{ priceChange?.toFixed(2) }}
          ({{ priceChangePercent?.toFixed(2) }}%)
        </div>
      </div>
    </div>

    <!-- 涨跌停信息 -->
    <el-row :gutter="16" class="limit-info">
      <el-col :span="8">
        <div class="limit-card up">
          <div class="limit-label">涨停价</div>
          <div class="limit-value">¥{{ upLimit?.toFixed(2) }}</div>
          <div class="limit-space">
            空间: {{ upSpace?.toFixed(2) }}%
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="limit-card current">
          <div class="limit-label">当前价</div>
          <div class="limit-value">¥{{ currentPrice?.toFixed(2) }}</div>
          <div class="limit-space">
            振幅: {{ amplitude?.toFixed(2) }}%
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="limit-card down">
          <div class="limit-label">跌停价</div>
          <div class="limit-value">¥{{ downLimit?.toFixed(2) }}</div>
          <div class="limit-space">
            空间: {{ downSpace?.toFixed(2) }}%
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 连续涨停信息 -->
    <el-card class="consecutive-info" v-if="consecutiveDays > 0">
      <template #header>
        <div class="card-header">
          <span>连续涨停信息</span>
          <el-tag type="success">{{ consecutiveDays }}天</el-tag>
        </div>
      </template>
      <div class="consecutive-content">
        <div class="consecutive-item">
          <span class="label">开始日期:</span>
          <span class="value">{{ consecutiveStartDate }}</span>
        </div>
        <div class="consecutive-item">
          <span class="label">累计涨幅:</span>
          <span class="value positive">{{ totalGain?.toFixed(2) }}%</span>
        </div>
        <div class="consecutive-item">
          <span class="label">成交金额:</span>
          <span class="value">{{ totalAmount?.toFixed(0) }}万</span>
        </div>
      </div>
    </el-card>

    <!-- 历史涨跌停统计 -->
    <el-card class="history-stats">
      <template #header>
        <span>历史涨跌停统计</span>
      </template>
      <div class="stats-grid">
        <div class="stat-item">
          <div class="stat-value">{{ historyUpLimitCount }}</div>
          <div class="stat-label">历史涨停次数</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ historyDownLimitCount }}</div>
          <div class="stat-label">历史跌停次数</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ maxConsecutiveDays }}</div>
          <div class="stat-label">最多连续涨停</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ upLimitRatio?.toFixed(1) }}%</div>
          <div class="stat-label">涨停成功率</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

interface Props {
  stockCode: string
  stockName: string
}

const props = defineProps<Props>()

// 响应式数据
const loading = ref(false)
const currentPrice = ref(12.45)
const priceChange = ref(0.25)
const priceChangePercent = ref(2.05)
const upLimit = ref(13.70)
const downLimit = ref(11.21)
const consecutiveDays = ref(3)
const consecutiveStartDate = ref('2024-01-08')
const totalGain = ref(32.5)
const totalAmount = ref(45800)
const historyUpLimitCount = ref(24)
const historyDownLimitCount = ref(8)
const maxConsecutiveDays = ref(5)
const upLimitRatio = ref(68.2)

// 计算属性
const changeClass = computed(() => {
  return priceChange.value > 0 ? 'positive' : priceChange.value < 0 ? 'negative' : 'neutral'
})

const upSpace = computed(() => {
  return ((upLimit.value - currentPrice.value) / currentPrice.value * 100)
})

const downSpace = computed(() => {
  return ((currentPrice.value - downLimit.value) / currentPrice.value * 100)
})

const amplitude = computed(() => {
  // 模拟计算振幅
  return 6.8
})

onMounted(() => {
  // 加载股票详情数据
  loadStockDetail()
})

const loadStockDetail = async () => {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
  } catch (error) {
    console.error('加载股票详情失败:', error)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.stock-detail-panel {
  padding: var(--spacer-3);
}

.stock-basic-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacer-4);
  padding-bottom: var(--spacer-3);
  border-bottom: 1px solid var(--border-color);

  .stock-header {
    .stock-name {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 var(--spacer-1) 0;
    }

    .stock-code {
      font-size: 0.875rem;
      color: var(--text-secondary);
    }
  }

  .stock-price {
    text-align: right;

    .current-price {
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: var(--spacer-1);
    }

    .price-change {
      font-size: 0.875rem;
      font-weight: 500;

      &.positive {
        color: var(--success-color);
      }

      &.negative {
        color: var(--danger-color);
      }

      &.neutral {
        color: var(--text-secondary);
      }
    }
  }
}

.limit-info {
  margin-bottom: var(--spacer-4);

  .limit-card {
    padding: var(--spacer-3);
    border-radius: var(--border-radius);
    text-align: center;
    border: 1px solid var(--border-color);

    &.up {
      background: rgba(76, 175, 80, 0.05);
      border-color: rgba(76, 175, 80, 0.2);
    }

    &.down {
      background: rgba(244, 67, 54, 0.05);
      border-color: rgba(244, 67, 54, 0.2);
    }

    &.current {
      background: rgba(33, 150, 243, 0.05);
      border-color: rgba(33, 150, 243, 0.2);
    }

    .limit-label {
      font-size: 0.875rem;
      color: var(--text-secondary);
      margin-bottom: var(--spacer-2);
    }

    .limit-value {
      font-size: 1.25rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: var(--spacer-2);
    }

    .limit-space {
      font-size: 0.75rem;
      color: var(--text-secondary);
    }
  }
}

.consecutive-info {
  margin-bottom: var(--spacer-4);

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .consecutive-content {
    display: flex;
    flex-direction: column;
    gap: var(--spacer-2);

    .consecutive-item {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .label {
        font-size: 0.875rem;
        color: var(--text-secondary);
      }

      .value {
        font-weight: 500;
        color: var(--text-primary);

        &.positive {
          color: var(--success-color);
        }
      }
    }
  }
}

.history-stats {
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--spacer-3);

    .stat-item {
      text-align: center;
      padding: var(--spacer-2);

      .stat-value {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: var(--spacer-1);
      }

      .stat-label {
        font-size: 0.75rem;
        color: var(--text-secondary);
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .stock-basic-info {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacer-2);

    .stock-price {
      text-align: left;
    }
  }

  .limit-info .el-col {
    margin-bottom: var(--spacer-2);
  }

  .history-stats .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>