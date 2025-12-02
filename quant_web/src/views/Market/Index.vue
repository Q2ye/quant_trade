<!-- 行情首页 - 基于 Naive UI 重构 -->
<template>
  <div class="market-index">
    <!-- 页面头部区域 -->
    <div class="market-header">
      <h2>市场概览</h2>
      <div class="market-filters">
        <n-select
          v-model:value="selectedMarket"
          placeholder="选择市场"
          :options="marketOptions"
        />
        <n-select
          v-model:value="selectedIndustry"
          placeholder="选择行业"
          :options="industryOptions"
        />
        <n-button type="primary" @click="refreshData">
          <template #icon>
            <n-icon><RefreshIcon /></n-icon>
          </template>
          刷新
        </n-button>
      </div>
    </div>

    <!-- 市场数据网格布局 -->
    <div class="market-grid">
      <!-- 大盘指数卡片 -->
      <n-card class="grid-card index-card" title="大盘指数">
        <div class="index-list">
          <div v-for="index in marketIndices" :key="index.code" class="index-item">
            <div class="index-name">{{ index.name }}</div>
            <div class="index-value">{{ index.value }}</div>
            <div :class="['index-change', index.change > 0 ? 'positive' : 'negative']">
              {{ index.change > 0 ? '+' : '' }}{{ index.change }}%
            </div>
          </div>
        </div>
      </n-card>

      <!-- 涨跌分布卡片 -->
      <n-card class="grid-card distribution-card" title="涨跌分布">
        <div class="distribution-chart">
          <div class="distribution-item rise">
            <div class="distribution-label">上涨</div>
            <div class="distribution-bar">
              <div class="bar-fill" :style="{ width: risePercentage + '%' }"></div>
            </div>
            <div class="distribution-value">{{ riseCount }}</div>
          </div>
          <div class="distribution-item fall">
            <div class="distribution-label">下跌</div>
            <div class="distribution-bar">
              <div class="bar-fill" :style="{ width: fallPercentage + '%' }"></div>
            </div>
            <div class="distribution-value">{{ fallCount }}</div>
          </div>
          <div class="distribution-item flat">
            <div class="distribution-label">平盘</div>
            <div class="distribution-bar">
              <div class="bar-fill" :style="{ width: flatPercentage + '%' }"></div>
            </div>
            <div class="distribution-value">{{ flatCount }}</div>
          </div>
        </div>
      </n-card>

      <!-- 热门板块卡片 -->
      <n-card class="grid-card hot-industry-card" title="热门板块">
        <div class="industry-list">
          <div v-for="industry in hotIndustries" :key="industry.name" class="industry-item">
            <div class="industry-name">{{ industry.name }}</div>
            <div class="industry-change">{{ industry.change }}%</div>
            <div class="industry-stocks">{{ industry.stockCount }}只股票</div>
          </div>
        </div>
      </n-card>

      <!-- 股票排行榜卡片 -->
      <n-card class="grid-card stock-rank-card" title="股票涨幅榜">
        <n-data-table
          :columns="stockRankColumns"
          :data="topRisingStocks"
          :bordered="false"
        />
      </n-card>
    </div>

    <!-- 自选股列表 -->
    <n-card class="favorite-stocks" title="自选股">
      <n-data-table
        :columns="favoriteColumns"
        :data="favoriteStocks"
        :bordered="false"
      />
    </n-card>
  </div>
</template>

<script>
import { defineComponent, ref, computed, h } from 'vue'
import {
  NCard,
  NSelect,
  NButton,
  NIcon,
  NDataTable
} from 'naive-ui'
import { Refresh as RefreshIcon } from '@vicons/ionicons5'

export default defineComponent({
  name: 'MarketIndex',
  components: {
    NCard,
    NSelect,
    NButton,
    NIcon,
    NDataTable,
    RefreshIcon
  },
  setup() {
    const selectedMarket = ref('A')
    const selectedIndustry = ref('')

    const marketOptions = [
      { label: '沪深A股', value: 'A' },
      { label: '科创板', value: 'K' },
      { label: '创业板', value: 'C' },
      { label: '北交所', value: 'B' }
    ]

    const industries = [
      '信息技术', '医药生物', '新能源', '消费', '金融',
      '房地产', '工业', '材料', '能源', '公用事业'
    ]

    const industryOptions = industries.map(industry => ({ label: industry, value: industry }))

    const marketIndices = ref([
      { name: '上证指数', code: '000001.SH', value: '3254.87', change: 0.56 },
      { name: '深证成指', code: '399001.SZ', value: '12045.32', change: -0.23 },
      { name: '创业板指', code: '399006.SZ', value: '2654.21', change: 1.24 },
      { name: '沪深300', code: '000300.SH', value: '4156.78', change: 0.78 },
      { name: '科创50', code: '000688.SH', value: '1124.56', change: 2.15 }
    ])

    const riseCount = ref(2456)
    const fallCount = ref(1234)
    const flatCount = ref(210)

    const hotIndustries = ref([
      { name: '人工智能', change: 4.56, stockCount: 42 },
      { name: '半导体', change: 3.78, stockCount: 35 },
      { name: '新能源汽车', change: 3.21, stockCount: 28 },
      { name: '光伏', change: 2.89, stockCount: 31 },
      { name: '医疗器械', change: 2.45, stockCount: 27 }
    ])

    const topRisingStocks = ref([
      { code: '603019', name: '中科曙光', price: '45.32', change: 10.01, volume: '125.4' },
      { code: '002230', name: '科大讯飞', price: '67.89', change: 9.98, volume: '98.7' },
      { code: '300750', name: '宁德时代', price: '425.12', change: 8.76, volume: '86.3' },
      { code: '600519', name: '贵州茅台', price: '1785.45', change: 7.89, volume: '45.2' },
      { code: '000858', name: '五粮液', price: '215.67', change: 6.54, volume: '67.8' }
    ])

    const favoriteStocks = ref([
      { code: '600519', name: '贵州茅台', price: '1785.45', change: 7.89 },
      { code: '000858', name: '五粮液', price: '215.67', change: 6.54 },
      { code: '601318', name: '中国平安', price: '48.32', change: -0.56 },
      { code: '600036', name: '招商银行', price: '36.78', change: 1.23 },
      { code: '300059', name: '东方财富', price: '24.56', change: 3.45 }
    ])

    // 表格列定义
    const stockRankColumns = [
      {
        title: '代码',
        key: 'code',
        width: 80
      },
      {
        title: '名称',
        key: 'name'
      },
      {
        title: '最新价',
        key: 'price'
      },
      {
        title: '涨跌幅',
        key: 'change',
        render: (row) => {
          const isPositive = row.change > 0
          return h('span', {
            class: isPositive ? 'positive' : 'negative'
          }, `${isPositive ? '+' : ''}${row.change}%`)
        }
      },
      {
        title: '成交量(万)',
        key: 'volume'
      }
    ]

    const favoriteColumns = [
      {
        title: '代码',
        key: 'code',
        width: 80
      },
      {
        title: '名称',
        key: 'name'
      },
      {
        title: '最新价',
        key: 'price'
      },
      {
        title: '涨跌幅',
        key: 'change',
        render: (row) => {
          const isPositive = row.change > 0
          return h('span', {
            class: isPositive ? 'positive' : 'negative'
          }, `${isPositive ? '+' : ''}${row.change}%`)
        }
      },
      {
        title: '操作',
        key: 'actions',
        render: (row) => h('div', { class: 'action-buttons' }, [
          h(NButton, {
            size: 'small',
            onClick: () => viewStockDetail(row)
          }, { default: () => '详情' }),
          h(NButton, {
            size: 'small',
            type: 'error',
            onClick: () => removeFavorite(row)
          }, { default: () => '删除' })
        ])
      }
    ]

    // 计算属性
    const totalStocks = computed(() => {
      return riseCount.value + fallCount.value + flatCount.value
    })

    const risePercentage = computed(() => {
      return (riseCount.value / totalStocks.value * 100).toFixed(1)
    })

    const fallPercentage = computed(() => {
      return (fallCount.value / totalStocks.value * 100).toFixed(1)
    })

    const flatPercentage = computed(() => {
      return (flatCount.value / totalStocks.value * 100).toFixed(1)
    })

    // 方法
    const refreshData = () => {
      console.log('刷新市场数据...')
      // 模拟数据刷新
      topRisingStocks.value = [...topRisingStocks.value]
      favoriteStocks.value = [...favoriteStocks.value]
    }

    const viewStockDetail = (stock) => {
      console.log('查看股票详情:', stock.code)
      // 实际项目中这里会导航到股票详情页
    }

    const removeFavorite = (stock) => {
      favoriteStocks.value = favoriteStocks.value.filter(s => s.code !== stock.code)
    }

    return {
      selectedMarket,
      selectedIndustry,
      marketOptions,
      industryOptions,
      marketIndices,
      riseCount,
      fallCount,
      flatCount,
      hotIndustries,
      topRisingStocks,
      favoriteStocks,
      stockRankColumns,
      favoriteColumns,
      totalStocks,
      risePercentage,
      fallPercentage,
      flatPercentage,
      refreshData,
      viewStockDetail,
      removeFavorite
    }
  }
})
</script>
<style scoped lang="scss">
@use '@/assets/scss/naive-variables' as *;

.market-index {
  padding: $content-padding;
  background-color: var(--n-body-color);
  color: var(--n-text-color-base);
  height: 100%;
  overflow-y: auto;
}

.market-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: spacer(4);
  padding-bottom: spacer(3);
  border-bottom: 1px solid var(--n-border-color);

  h2 {
    font-size: $font-size-base * 1.5;
    font-weight: 600;
    color: var(--n-text-color-base);
    margin: 0;
  }
}

.market-filters {
  display: flex;
  gap: spacer(3);
  align-items: center;
}

.market-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: spacer(4);
  margin-bottom: spacer(5);

  @include card-grid-layout(2, (
    'lg': 1,
    'md': 1,
    'sm': 1
  ));
}

.grid-card {
  height: 100%;
  transition: all $transition-normal;

  &:hover {
    transform: $hover-transform;
    box-shadow: var(--n-box-shadow-2);
  }
}

.index-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: spacer(3);
}

.index-item {
  @include flex-center(row);
  justify-content: space-between;
  padding: spacer(2);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  transition: background-color $transition-fast;

  &:hover {
    background: var(--n-hover-color);
  }
}

.index-name {
  font-weight: 500;
  color: var(--n-text-color-base);
}

.index-value {
  color: var(--n-text-color-base);
  font-weight: 500;
}

.index-change {
  font-weight: 600;
}

.distribution-chart {
  display: flex;
  flex-direction: column;
  gap: spacer(3);
}

.distribution-item {
  @include flex-center(row);
  gap: spacer(3);
}

.distribution-label {
  width: 60px;
  font-weight: 500;
  color: var(--n-text-color-base);
}

.distribution-bar {
  flex: 1;
  height: 20px;
  background: var(--n-card-color);
  border-radius: 10px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  transition: width $transition-normal;
}

.rise .bar-fill {
  background: $stock-up-color;
}

.fall .bar-fill {
  background: $stock-down-color;
}

.flat .bar-fill {
  background: $stock-flat-color;
}

.distribution-value {
  width: 50px;
  text-align: right;
  font-weight: 500;
  color: var(--n-text-color-base);
}

.industry-list {
  display: flex;
  flex-direction: column;
  gap: spacer(2);
}

.industry-item {
  @include flex-center(row);
  justify-content: space-between;
  padding: spacer(2) spacer(3);
  background: var(--n-card-color);
  border-radius: var(--n-border-radius);
  transition: background-color $transition-fast;

  &:hover {
    background: var(--n-hover-color);
  }
}

.industry-name {
  flex: 1;
  font-weight: 500;
  color: var(--n-text-color-base);
}

.industry-change {
  width: 60px;
  text-align: right;
  font-weight: 600;
  color: $stock-up-color;
}

.industry-stocks {
  width: 100px;
  text-align: right;
  color: var(--n-text-color-2);
  font-size: $font-size-base * 0.9;
}

.favorite-stocks {
  margin-top: spacer(4);
}

.action-buttons {
  display: flex;
  gap: spacer(2);
}

.positive {
  color: $stock-up-color;
  font-weight: 500;
}

.negative {
  color: $stock-down-color;
  font-weight: 500;
}

@include media-breakpoint-down(lg) {
  .market-header {
    flex-direction: column;
    align-items: flex-start;
    gap: spacer(3);
  }

  .market-filters {
    width: 100%;
    justify-content: flex-start;
  }

  .index-list {
    grid-template-columns: 1fr;
  }
}

@include media-breakpoint-down(md) {
  .market-index {
    padding: spacer(3);
  }

  .market-filters {
    flex-direction: column;
    align-items: stretch;
  }
}

@include media-breakpoint-down(sm) {
  .market-index {
    padding: spacer(2);
  }

  .market-grid {
    gap: spacer(3);
  }

  .industry-item {
    flex-direction: column;
    align-items: flex-start;
    gap: spacer(1);
  }

  .industry-change,
  .industry-stocks {
    width: auto;
    text-align: left;
  }
}
</style>