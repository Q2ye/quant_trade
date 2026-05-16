<!-- 大盘指数看板 - 基于 Naive UI 重构 -->
<template>
  <n-card class="index-board" :bordered="false">
    <!-- 看板头部 -->
    <div class="board-header">
      <h3>大盘指数</h3>
      <div class="header-actions">
        <span class="update-time">更新: {{ formatTime(lastUpdate) }}</span>
        <n-button
          size="small"
          :loading="isRefreshing"
          @click="refreshData"
          :disabled="isRefreshing"
        >
          <template #icon>
            <n-icon><RefreshIcon /></n-icon>
          </template>
          {{ isRefreshing ? '更新中...' : '刷新' }}
        </n-button>
      </div>
    </div>

    <!-- 指数列表 -->
    <n-spin :show="loading">
      <n-result v-if="error" status="500" title="数据加载失败" description="请检查网络连接后重试">
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <div class="index-list">
      <div
        v-for="(index, idx) in indices"
        :key="idx"
        class="index-item"
        :class="{ 'selected': selectedIndex?.code === index.code }"
        @click="selectIndex(index)"
      >
        <div class="index-name">{{ index.name }}</div>
        <div class="index-value">{{ index.value.toLocaleString() }}</div>
        <div
          class="index-change"
          :class="index.change >= 0 ? 'positive' : 'negative'"
        >
          <span v-if="index.change >= 0">+</span>{{ index.change.toFixed(2) }}
          <span class="change-percent">({{ index.changePercent >= 0 ? '+' : '' }}{{ index.changePercent.toFixed(2) }}%)</span>
        </div>
      </div>
    </div>

    <!-- 指数详情面板 -->
    <div v-if="selectedIndex" class="index-detail">
      <div class="detail-header">
        <h4>{{ selectedIndex.name }} ({{ selectedIndex.code }})</h4>
      </div>
      <div class="detail-content">
        <div class="detail-item">
          <span class="label">最高:</span>
          <span class="value">{{ selectedIndex.high.toLocaleString() }}</span>
        </div>
        <div class="detail-item">
          <span class="label">最低:</span>
          <span class="value">{{ selectedIndex.low.toLocaleString() }}</span>
        </div>
        <div class="detail-item">
          <span class="label">成交量:</span>
          <span class="value">{{ selectedIndex.volume }}</span>
        </div>
        <div class="detail-item">
          <span class="label">成交额:</span>
          <span class="value">{{ selectedIndex.amount }}</span>
        </div>
      </div>
      </template>
    </n-spin>
  </n-card>
</template>

<script>
import { defineComponent, ref } from 'vue'
import { NCard, NButton, NIcon, NSpin, NResult } from 'naive-ui'
import { Refresh as RefreshIcon } from '@vicons/ionicons5'

export default defineComponent({
  name: "IndexBoard",
  components: {
    NCard,
    NButton,
    NIcon,
    RefreshIcon
  },
  setup() {
    // 指数数据
    const indices = ref([
      {
        code: "000001.SH",
        name: "上证指数",
        value: 3254.87,
        change: 0.56,
        changePercent: 0.017,
        high: 3268.45,
        low: 3245.21,
        volume: "3.42亿",
        amount: "4235.68亿"
      },
      {
        code: "399001.SZ",
        name: "深证成指",
        value: 12045.32,
        change: -0.23,
        changePercent: -0.002,
        high: 12120.45,
        low: 12010.78,
        volume: "2.87亿",
        amount: "3876.54亿"
      },
      {
        code: "399006.SZ",
        name: "创业板指",
        value: 2654.21,
        change: 1.24,
        changePercent: 0.047,
        high: 2678.32,
        low: 2645.78,
        volume: "1.23亿",
        amount: "1876.43亿"
      },
      {
        code: "000300.SH",
        name: "沪深300",
        value: 4156.78,
        change: 0.78,
        changePercent: 0.019,
        high: 4178.45,
        low: 4145.32,
        volume: "1.98亿",
        amount: "2876.54亿"
      },
      {
        code: "000688.SH",
        name: "科创50",
        value: 1124.56,
        change: 2.15,
        changePercent: 0.191,
        high: 1135.78,
        low: 1118.45,
        volume: "0.78亿",
        amount: "876.54亿"
      }
    ])

    const lastUpdate = ref(new Date())
    const selectedIndex = ref(null)
    const isRefreshing = ref(false)
    const loading = ref(false)
    const error = ref(false)

    // 刷新指数数据
    const loadData = async () => {
      loading.value = true
      error.value = false
      try { await new Promise(r => setTimeout(r, 300)) } catch { error.value = true } finally { loading.value = false }
    }

    const refreshData = () => {
      isRefreshing.value = true

      setTimeout(() => {
        indices.value = indices.value.map(index => {
          // 模拟价格波动
          const fluctuation = (Math.random() - 0.5) * 0.5
          const newValue = index.value * (1 + fluctuation)
          const change = newValue - index.value
          const changePercent = (change / index.value) * 100

          return {
            ...index,
            value: parseFloat(newValue.toFixed(2)),
            change: parseFloat(change.toFixed(2)),
            changePercent: parseFloat(changePercent.toFixed(2))
          }
        })

        lastUpdate.value = new Date()
        isRefreshing.value = false
      }, 1000)
    }

    // 选择指数
    const selectIndex = (index) => {
      selectedIndex.value = selectedIndex.value?.code === index.code ? null : index
    }

    // 格式化时间显示
    const formatTime = (date) => {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }

    return {
      indices,
      lastUpdate,
      selectedIndex,
      isRefreshing,
      loading,
      error,
      refreshData,
      selectIndex,
      formatTime,
      loadData
    }
  }
})
</script>
<style scoped lang="scss">
@use '@/styles/naive-variables' as *;

.index-board {
  padding: spacer(4);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  box-shadow: var(--n-box-shadow-1);
  transition: all $transition-normal;
  border: 1px solid var(--n-border-color);

  &:hover {
    box-shadow: var(--n-box-shadow-2);
  }
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: spacer(4);
  padding-bottom: spacer(3);
  border-bottom: 1px solid var(--n-border-color);

  h3 {
    margin: 0;
    font-size: $font-size-base * 1.2;
    font-weight: 600;
    color: var(--n-primary-color);
    letter-spacing: 0.5px;
  }
}

.header-actions {
  @include flex-center(row);
  gap: spacer(3);
}

.update-time {
  font-size: $font-size-base * 0.9;
  color: var(--n-text-color-2);
}

.index-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: spacer(3);
}

.index-item {
  @include card-base(false);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  padding: spacer(3);
  cursor: pointer;
  transition: all $transition-normal;
  border: 1px solid var(--n-border-color);
  position: relative;
  overflow: hidden;

  &:hover {
    background: var(--n-hover-color);
    transform: translateY(-2px);
    box-shadow: var(--n-box-shadow-2);
  }

  &.selected {
    background: rgba(var(--n-primary-color), 0.1);
    border-color: var(--n-primary-color);

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
      background: var(--n-primary-color);
    }
  }
}

.index-name {
  font-size: $font-size-base;
  color: var(--n-text-color-2);
  margin-bottom: spacer(2);
  font-weight: 500;
}

.index-value {
  font-size: $font-size-base * 1.4;
  font-weight: 600;
  color: var(--n-text-color-base);
  margin-bottom: spacer(1);
  letter-spacing: 0.5px;
}

.index-change {
  font-size: $font-size-base;
  font-weight: 600;
  @include flex-center(row);
}

.change-percent {
  margin-left: spacer(1);
  font-size: $font-size-base * 0.9;
}

.positive {
  color: $stock-up-color;
}

.negative {
  color: $stock-down-color;
}

.index-detail {
  margin-top: spacer(4);
  padding-top: spacer(3);
  border-top: 1px solid var(--n-border-color);
  @include fade-in;
}

.detail-header {
  margin-bottom: spacer(3);

  h4 {
    margin: 0;
    font-size: $font-size-base * 1.1;
    color: var(--n-primary-color);
    font-weight: 600;
  }
}

.detail-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: spacer(2);
}

.detail-item {
  @include flex-center(row);
  justify-content: space-between;
  padding: spacer(2) spacer(3);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  font-size: $font-size-base;
}

.label {
  color: var(--n-text-color-2);
  font-weight: 500;
}

.value {
  color: var(--n-text-color-base);
  font-weight: 500;
}

@include media-breakpoint-down(md) {
  .index-board {
    padding: spacer(3);
  }

  .index-list {
    grid-template-columns: repeat(2, 1fr);
  }

  .detail-content {
    grid-template-columns: 1fr;
  }
}

@include media-breakpoint-down(sm) {
  .board-header {
    flex-direction: column;
    align-items: flex-start;
    gap: spacer(2);
  }

  .header-actions {
    width: 100%;
    justify-content: space-between;
  }

  .index-list {
    grid-template-columns: 1fr;
  }

  .index-item {
    padding: spacer(2);
  }

  .index-value {
    font-size: $font-size-base * 1.2;
  }
}
</style>