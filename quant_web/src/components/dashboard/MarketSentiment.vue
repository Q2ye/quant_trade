<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useMarketStore } from '@/store/modules/market'
import { useWebSocket } from '@/composables/useWebSocket'

const marketStore = useMarketStore()
const { subscribe, unsubscribe } = useWebSocket()

// 市场情绪数据
const sentimentData = ref({
  advanceDecline: { advance: 0, decline: 0, unchanged: 0 },
  marketStrength: 0,
  turnoverRate: 0,
  limitUpDown: { up: 0, down: 0 }
})

// 计算市场强度
const marketStrength = computed(() => {
  const { advance, decline } = sentimentData.value.advanceDecline
  return advance / (advance + decline) * 100
})

// 实时订阅市场情绪数据
onMounted(() => {
  subscribe('market_sentiment', (data) => {
    sentimentData.value = data
  })

  // 初始化加载数据
  marketStore.fetchMarketSentiment().then(data => {
    sentimentData.value = data
  })
})

onUnmounted(() => {
  unsubscribe('market_sentiment')
})
</script>

<template>
  <div class="market-sentiment">
    <div class="header">
      <h3>市场情绪看板</h3>
      <span class="time">{{ new Date().toLocaleTimeString() }}</span>
    </div>

    <div class="sentiment-grid">
      <!-- 涨跌家数 -->
      <div class="metric-card">
        <div class="metric-title">涨跌分布</div>
        <div class="advance-decline">
          <div class="advance">
            <span class="count">{{ sentimentData.advanceDecline.advance }}</span>
            <span class="label">上涨</span>
          </div>
          <div class="decline">
            <span class="count">{{ sentimentData.advanceDecline.decline }}</span>
            <span class="label">下跌</span>
          </div>
          <div class="unchanged">
            <span class="count">{{ sentimentData.advanceDecline.unchanged }}</span>
            <span class="label">平盘</span>
          </div>
        </div>
      </div>

      <!-- 市场强度 -->
      <div class="metric-card">
        <div class="metric-title">市场强度</div>
        <div class="strength-gauge">
          <div class="gauge-value">{{ marketStrength.toFixed(1) }}%</div>
          <div class="gauge-bar">
            <div
              class="gauge-fill"
              :style="{ width: marketStrength + '%' }"
              :class="{ strong: marketStrength > 60, weak: marketStrength < 40 }"
            ></div>
          </div>
        </div>
      </div>

      <!-- 涨停跌停 -->
      <div class="metric-card">
        <div class="metric-title">涨跌停统计</div>
        <div class="limit-stats">
          <div class="limit-up">
            <span class="icon">📈</span>
            <span class="count">{{ sentimentData.limitUpDown.up }}</span>
            <span class="label">涨停</span>
          </div>
          <div class="limit-down">
            <span class="icon">📉</span>
            <span class="count">{{ sentimentData.limitUpDown.down }}</span>
            <span class="label">跌停</span>
          </div>
        </div>
      </div>

      <!-- 换手率 -->
      <div class="metric-card">
        <div class="metric-title">平均换手率</div>
        <div class="turnover">
          <span class="value">{{ sentimentData.turnoverRate }}%</span>
          <div class="trend-indicator" :class="{ up: sentimentData.turnoverRate > 2 }">
            {{ sentimentData.turnoverRate > 2 ? '活跃' : '平淡' }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-sentiment {
  background: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h3 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 16px;
}

.time {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.sentiment-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.metric-card {
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 16px;
  text-align: center;
}

.metric-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.advance-decline {
  display: flex;
  justify-content: space-around;
}

.advance .count { color: #f56c6c; }
.decline .count { color: #67c23a; }
.unchanged .count { color: #909399; }

.count {
  font-size: 18px;
  font-weight: bold;
  display: block;
}

.label {
  font-size: 12px;
  display: block;
  margin-top: 4px;
}

.strength-gauge {
  padding: 8px 0;
}

.gauge-value {
  font-size: 20px;
  font-weight: bold;
  margin-bottom: 8px;
}

.gauge-bar {
  background: var(--el-border-color-light);
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
}

.gauge-fill {
  height: 100%;
  background: #67c23a;
  transition: width 0.3s ease;
}

.gauge-fill.strong { background: #67c23a; }
.gauge-fill.weak { background: #f56c6c; }

.limit-stats {
  display: flex;
  justify-content: space-around;
}

.limit-up .count { color: #f56c6c; }
.limit-down .count { color: #67c23a; }

.turnover .value {
  font-size: 20px;
  font-weight: bold;
  display: block;
}

.trend-indicator {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 3px;
  margin-top: 4px;
  display: inline-block;
}

.trend-indicator.up {
  background: #f0f9ff;
  color: #409eff;
}
</style>