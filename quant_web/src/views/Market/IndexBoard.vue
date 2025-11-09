<!-- 大盘指数看板 - 基于主题系统优化 -->
<template>
  <div class="index-board">
    <!-- 看板头部 -->
    <div class="board-header">
      <h3>大盘指数</h3>
      <div class="header-actions">
        <span class="update-time">更新: {{ formatTime(lastUpdate) }}</span>
        <el-button
          size="small"
          :icon="isRefreshing ? 'el-icon-loading' : 'el-icon-refresh'"
          @click="refreshData"
          :disabled="isRefreshing"
        >
          {{ isRefreshing ? '更新中...' : '刷新' }}
        </el-button>
      </div>
    </div>

    <!-- 指数列表 -->
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
    </div>
  </div>
</template>

<script>
export default {
  name: "IndexBoard",
  data() {
    return {
      // 指数数据
      indices: [
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
      ],
      lastUpdate: new Date(),
      selectedIndex: null,
      isRefreshing: false
    };
  },
  methods: {
    // 刷新指数数据
    refreshData() {
      this.isRefreshing = true;

      // 模拟数据刷新
      setTimeout(() => {
        this.indices = this.indices.map(index => {
          // 模拟价格波动
          const fluctuation = (Math.random() - 0.5) * 0.5;
          const newValue = index.value * (1 + fluctuation);
          const change = newValue - index.value;
          const changePercent = (change / index.value) * 100;

          return {
            ...index,
            value: parseFloat(newValue.toFixed(2)),
            change: parseFloat(change.toFixed(2)),
            changePercent: parseFloat(changePercent.toFixed(2))
          };
        });

        this.lastUpdate = new Date();
        this.isRefreshing = false;
      }, 1000);
    },
    // 选择指数
    selectIndex(index) {
      this.selectedIndex = this.selectedIndex?.code === index.code ? null : index;
    },
    // 格式化时间显示
    formatTime(date) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
  }
};
</script>

<style scoped lang="scss">
// 导入主题变量和混入
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color';

.index-board {
  @include mixin.card-base;
  padding: map.get($spacers, 4);
  background: $card-gradient-bg;
  border-radius: $border-radius-lg;
  box-shadow: $card-shadow;
  transition: all $transition-normal;
  border: $border-width solid $border-color;

  &:hover {
    box-shadow: $card-hover-shadow;
  }
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: map.get($spacers, 4);
  padding-bottom: map.get($spacers, 3);
  border-bottom: $border-width solid $border-color;

  h3 {
    margin: 0;
    font-size: $font-size-base * 1.2;
    font-weight: $font-weight-semibold;
    color: $accent-color;
    letter-spacing: 0.5px;
  }
}

.header-actions {
  @include mixin.flex-center(row);
  gap: map.get($spacers, 3);
}

.update-time {
  font-size: $font-size-base * 0.9;
  color: $text-secondary;
}

.index-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: map.get($spacers, 3);
}

.index-item {
  @include mixin.card-base(false);
  background: rgba($secondary-bg, 0.6);
  border-radius: $border-radius;
  padding: map.get($spacers, 3);
  cursor: pointer;
  transition: all $transition-normal;
  border: $border-width solid $border-color;
  position: relative;
  overflow: hidden;

  &:hover {
    background: rgba($hover-bg, 0.7);
    transform: translateY(-2px);
    box-shadow: $hover-shadow;
  }

  &.selected {
    background: rgba($active-bg, 0.1);
    border-color: $accent-color;

    &::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 4px;
      height: 100%;
      background: $accent-color;
    }
  }
}

.index-name {
  font-size: $font-size-base;
  color: $text-secondary;
  margin-bottom: map.get($spacers, 2);
  font-weight: $font-weight-medium;
}

.index-value {
  font-size: $font-size-base * 1.4;
  font-weight: $font-weight-bold;
  color: $text-primary;
  margin-bottom: map.get($spacers, 1);
  letter-spacing: 0.5px;
}

.index-change {
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  @include mixin.flex-center(row);
}

.change-percent {
  margin-left: map.get($spacers, 1);
  font-size: $font-size-base * 0.9;
}

// 价格涨跌颜色样式
.positive {
  color: $stock-up-color;
}

.negative {
  color: $stock-down-color;
}

.index-detail {
  margin-top: map.get($spacers, 4);
  padding-top: map.get($spacers, 3);
  border-top: $border-width solid $border-color;
  @include mixin.fade-in;
}

.detail-header {
  margin-bottom: map.get($spacers, 3);

  h4 {
    margin: 0;
    font-size: $font-size-base * 1.1;
    color: $accent-color;
    font-weight: $font-weight-semibold;
  }
}

.detail-content {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: map.get($spacers, 2);
}

.detail-item {
  @include mixin.flex-center(row);
  justify-content: space-between;
  padding: map.get($spacers, 2) map.get($spacers, 3);
  background: rgba($secondary-bg, 0.5);
  border-radius: $border-radius-sm;
  font-size: $font-size-base;
}

.label {
  color: $text-secondary;
  font-weight: $font-weight-medium;
}

.value {
  color: $text-primary;
  font-weight: $font-weight-medium;
}

// 响应式设计
@include mixin.media-breakpoint-down(md) {
  .index-board {
    padding: map.get($spacers, 3);
  }

  .index-list {
    grid-template-columns: repeat(2, 1fr);
  }

  .detail-content {
    grid-template-columns: 1fr;
  }
}

@include mixin.media-breakpoint-down(sm) {
  .board-header {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 2);
  }

  .header-actions {
    width: 100%;
    justify-content: space-between;
  }

  .index-list {
    grid-template-columns: 1fr;
  }

  .index-item {
    padding: map.get($spacers, 2);
  }

  .index-value {
    font-size: $font-size-base * 1.2;
  }
}
</style>