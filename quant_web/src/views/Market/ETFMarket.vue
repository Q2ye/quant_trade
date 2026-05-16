<!-- ETF行情页 - 基于 Naive UI 重构 -->
<template>
  <div class="etf-market bg-gradient-mesh bg-noise">
    <!-- 页面头部区域 -->
    <div class="etf-header">
      <h2>ETF行情</h2>
      <div class="etf-filters">
        <n-select
          v-model:value="selectedCategory"
          placeholder="选择分类"
          :options="categoryOptions"
        />
        <n-input
          v-model:value="searchKeyword"
          placeholder="搜索ETF名称或代码"
          clearable
        >
          <template #prefix>
            <n-icon><SearchIcon /></n-icon>
          </template>
        </n-input>
        <n-button type="primary" @click="refreshData">
          <template #icon>
            <n-icon><RefreshIcon /></n-icon>
          </template>
          刷新
        </n-button>
      </div>
    </div>

    <n-spin :show="loading">
      <n-result v-if="error" status="500" title="数据加载失败" description="请检查网络连接后重试">
        <template #footer>
          <n-button type="primary" @click="loadData">重试</n-button>
        </template>
      </n-result>

      <template v-else>
        <!-- ETF数据网格布局 -->
        <div class="etf-grid">
      <!-- 资金流向图表卡片 -->
      <n-card class="grid-card etf-trend-card" title="ETF资金流向">
        <div class="trend-chart">
          <div id="fundFlowChart" class="chart"></div>
        </div>
      </n-card>

      <!-- 分类分布图表卡片 -->
      <n-card class="grid-card etf-category-card" title="ETF分类分布">
        <div class="category-chart">
          <div id="categoryChart" class="chart"></div>
        </div>
      </n-card>

      <!-- 涨幅榜卡片 -->
      <n-card class="grid-card etf-top-card" title="ETF涨幅榜">
        <n-data-table
          :columns="topRisingColumns"
          :data="topRisingETFs"
          :bordered="false"
        />
      </n-card>

      <!-- 关注列表卡片 -->
      <n-card class="grid-card etf-favorite-card" title="我的ETF关注">
        <n-data-table
          :columns="favoriteColumns"
          :data="favoriteETFs"
          :bordered="false"
        />
      </n-card>
    </div>

    <!-- ETF完整列表 -->
    <n-card class="etf-list" title="ETF列表">
      <n-data-table
        :columns="etfListColumns"
        :data="filteredETFs"
        :bordered="false"
      />
    </n-card>
      </template>
    </n-spin>
  </div>
</template>

<script>
import { defineComponent, ref, computed, onMounted, onBeforeUnmount } from 'vue'
import {
  NCard,
  NSelect,
  NInput,
  NButton,
  NIcon,
  NDataTable,
  NSpin,
  NResult,
  useMessage
} from 'naive-ui'
import { Search as SearchIcon, Refresh as RefreshIcon } from '@vicons/ionicons5'
import * as echarts from 'echarts'

export default defineComponent({
  name: 'ETFMarket',
  components: {
    NCard,
    NSelect,
    NInput,
    NButton,
    NIcon,
    NDataTable,
    SearchIcon,
    RefreshIcon
  },
  setup() {
    const message = useMessage()
    const loading = ref(false)
    const error = ref(false)

    const selectedCategory = ref('all')
    const searchKeyword = ref('')

    const categoryOptions = [
      { label: '全部', value: 'all' },
      { label: '股票型', value: 'stock' },
      { label: '债券型', value: 'bond' },
      { label: '商品型', value: 'commodity' },
      { label: '货币型', value: 'currency' },
      { label: '跨境型', value: 'overseas' }
    ]

    // ETF数据
    const topRisingETFs = ref([
      { code: '515790', name: '光伏ETF', category: '股票型', price: '1.245', change: 3.75, volume: '12345', amount: '5432', index: '中证光伏产业指数' },
      { code: '159995', name: '芯片ETF', category: '股票型', price: '1.087', change: 2.94, volume: '23456', amount: '6543', index: '国证半导体芯片指数' },
      { code: '515030', name: '新能源车ETF', category: '股票型', price: '1.325', change: 2.32, volume: '34567', amount: '7654', index: '中证新能源汽车指数' },
      { code: '512480', name: '半导体ETF', category: '股票型', price: '0.985', change: 1.96, volume: '45678', amount: '8765', index: '中证全指半导体指数' },
      { code: '512000', name: '券商ETF', category: '股票型', price: '0.876', change: 1.85, volume: '56789', amount: '9876', index: '中证全指证券公司指数' }
    ])

    const favoriteETFs = ref([
      { code: '510300', name: '沪深300ETF', category: '股票型', price: '3.875', change: 0.78, volume: '123456', amount: '12345', index: '沪深300指数', isFavorite: true },
      { code: '510050', name: '上证50ETF', category: '股票型', price: '2.765', change: 0.45, volume: '98765', amount: '8765', index: '上证50指数', isFavorite: true }
    ])

    const allETFs = ref([
      { code: '510300', name: '沪深300ETF', category: '股票型', price: '3.875', change: 0.78, volume: '123456', amount: '12345', index: '沪深300指数', isFavorite: true },
      { code: '510050', name: '上证50ETF', category: '股票型', price: '2.765', change: 0.45, volume: '98765', amount: '8765', index: '上证50指数', isFavorite: true },
      { code: '159915', name: '创业板ETF', category: '股票型', price: '2.345', change: 1.25, volume: '87654', amount: '7654', index: '创业板指数', isFavorite: false },
      { code: '515790', name: '光伏ETF', category: '股票型', price: '1.245', change: 3.75, volume: '12345', amount: '5432', index: '中证光伏产业指数', isFavorite: false },
      { code: '159995', name: '芯片ETF', category: '股票型', price: '1.087', change: 2.94, volume: '23456', amount: '6543', index: '国证半导体芯片指数', isFavorite: false },
      { code: '511010', name: '国债ETF', category: '债券型', price: '130.456', change: 0.12, volume: '3456', amount: '4321', index: '上证5年期国债指数', isFavorite: false },
      { code: '518800', name: '黄金ETF', category: '商品型', price: '4.325', change: 0.45, volume: '4567', amount: '3210', index: '上海金现货合约', isFavorite: false },
      { code: '511990', name: '货币ETF', category: '货币型', price: '100.025', change: 0.01, volume: '5678', amount: '2109', index: '银行间市场利率', isFavorite: false },
      { code: '513500', name: '标普500ETF', category: '跨境型', price: '1.345', change: -0.25, volume: '6789', amount: '1098', index: '标普500指数', isFavorite: false }
    ])

    const flowChart = ref(null)
    const categoryChart = ref(null)

    // 表格列定义
    const createTopRisingColumns = () => [
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
      },
      {
        title: '操作',
        key: 'actions',
        render: (row) => h(NButton, {
          size: 'small',
          onClick: () => viewETFDetail(row)
        }, { default: () => '详情' })
      }
    ]

    const createFavoriteColumns = () => [
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
        render: (row) => h(NButton, {
          size: 'small',
          type: 'error',
          onClick: () => removeFavorite(row)
        }, { default: () => '移除' })
      }
    ]

    const createETFListColumns = () => [
      {
        title: '代码',
        key: 'code',
        width: 100
      },
      {
        title: '名称',
        key: 'name'
      },
      {
        title: '类型',
        key: 'category',
        width: 100
      },
      {
        title: '最新价',
        key: 'price',
        width: 100
      },
      {
        title: '涨跌幅',
        key: 'change',
        width: 120,
        render: (row) => {
          const isPositive = row.change > 0
          return h('span', {
            class: isPositive ? 'positive' : 'negative'
          }, `${isPositive ? '+' : ''}${row.change}%`)
        }
      },
      {
        title: '成交量(万)',
        key: 'volume',
        width: 120
      },
      {
        title: '成交额(万)',
        key: 'amount',
        width: 120
      },
      {
        title: '跟踪指数',
        key: 'index',
        width: 180
      },
      {
        title: '操作',
        key: 'actions',
        width: 150,
        render: (row) => h('div', { class: 'action-buttons' }, [
          h(NButton, {
            size: 'small',
            onClick: () => viewETFDetail(row)
          }, { default: () => '详情' }),
          h(NButton, {
            size: 'small',
            type: row.isFavorite ? 'error' : 'primary',
            onClick: () => toggleFavorite(row)
          }, { default: () => row.isFavorite ? '取消' : '关注' })
        ])
      }
    ]

    const topRisingColumns = createTopRisingColumns()
    const favoriteColumns = createFavoriteColumns()
    const etfListColumns = createETFListColumns()

    // 过滤ETF数据
    const filteredETFs = computed(() => {
      let result = allETFs.value

      // 按类别筛选
      if (selectedCategory.value !== 'all') {
        result = result.filter(etf => etf.category === selectedCategory.value)
      }

      // 按关键词筛选
      if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase()
        result = result.filter(etf =>
          etf.code.toLowerCase().includes(keyword) ||
          etf.name.toLowerCase().includes(keyword)
        )
      }

      return result
    })

    // 刷新数据
    const loadData = async () => {
      loading.value = true
      error.value = false
      try {
        await new Promise(r => setTimeout(r, 300))
        initFlowChart()
        initCategoryChart()
      } catch { error.value = true } finally { loading.value = false }
    }

    const refreshData = () => loadData().then(() => message.success('ETF数据已刷新'))

    // 查看ETF详情
    const viewETFDetail = (etf) => {
      console.log('查看ETF详情:', etf.code)
    }

    // 切换关注状态
    const toggleFavorite = (etf) => {
      etf.isFavorite = !etf.isFavorite
      if (etf.isFavorite) {
        // 添加到关注列表
        if (!favoriteETFs.value.some(f => f.code === etf.code)) {
          favoriteETFs.value.push({...etf})
        }
      } else {
        // 从关注列表移除
        favoriteETFs.value = favoriteETFs.value.filter(f => f.code !== etf.code)
      }
    }

    // 移除关注
    const removeFavorite = (etf) => {
      const index = allETFs.value.findIndex(e => e.code === etf.code)
      if (index !== -1) {
        allETFs.value[index].isFavorite = false
      }
      favoriteETFs.value = favoriteETFs.value.filter(f => f.code !== etf.code)
    }

    // 初始化资金流向图表
    const initFlowChart = () => {
      const chartDom = document.getElementById('fundFlowChart')
      if (!chartDom) return

      flowChart.value = echarts.init(chartDom)

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          }
        },
        legend: {
          data: ['流入', '流出'],
          right: 10,
          top: 10
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: ['周一', '周二', '周三', '周四', '周五']
        },
        yAxis: {
          type: 'value',
          name: '亿元'
        },
        series: [
          {
            name: '流入',
            type: 'bar',
            stack: 'total',
            emphasis: {
              focus: 'series'
            },
            data: [12.3, 15.2, 8.7, 17.8, 13.5],
            itemStyle: {
              color: '#67c23a'
            }
          },
          {
            name: '流出',
            type: 'bar',
            stack: 'total',
            emphasis: {
              focus: 'series'
            },
            data: [-8.5, -7.2, -6.8, -9.3, -7.9],
            itemStyle: {
              color: '#f56c6c'
            }
          }
        ]
      }

      flowChart.value.setOption(option)
    }

    // 初始化分类分布图表
    const initCategoryChart = () => {
      const chartDom = document.getElementById('categoryChart')
      if (!chartDom) return

      categoryChart.value = echarts.init(chartDom)

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center'
        },
        series: [
          {
            name: 'ETF分类',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 6,
              borderWidth: 2
            },
            label: {
              show: false,
              position: 'center'
            },
            emphasis: {
              label: {
                show: true,
                fontSize: '18',
                fontWeight: 'bold'
              }
            },
            labelLine: {
              show: false
            },
            data: [
              { value: 156, name: '股票型' },
              { value: 32, name: '债券型' },
              { value: 28, name: '商品型' },
              { value: 24, name: '货币型' },
              { value: 45, name: '跨境型' }
            ]
          }
        ]
      }

      categoryChart.value.setOption(option)
    }

    // 处理窗口大小变化
    const handleResize = () => {
      if (flowChart.value) {
        flowChart.value.resize()
      }
      if (categoryChart.value) {
        categoryChart.value.resize()
      }
    }

    onMounted(() => {
      loadData()
      window.addEventListener('resize', handleResize)
    })

    onBeforeUnmount(() => {
      // 清理图表实例
      if (flowChart.value) {
        flowChart.value.dispose()
      }
      if (categoryChart.value) {
        categoryChart.value.dispose()
      }
      window.removeEventListener('resize', handleResize)
    })

    return {
      loading,
      error,
      selectedCategory,
      searchKeyword,
      categoryOptions,
      topRisingETFs,
      favoriteETFs,
      filteredETFs,
      topRisingColumns,
      favoriteColumns,
      etfListColumns,
      refreshData,
      viewETFDetail,
      toggleFavorite,
      removeFavorite,
      loadData
    }
  }
})
</script>
<style scoped lang="scss">
@use '@/styles/naive-variables' as *;

.etf-market {
  padding: $content-padding;
  background-color: var(--n-body-color);
  color: var(--n-text-color-base);
  height: 100%;
  overflow-y: auto;
}

.etf-header {
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

.etf-filters {
  display: flex;
  gap: spacer(3);
  align-items: center;
}

.etf-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: spacer(4);
  margin-bottom: spacer(5);

  @include flexible-grid(2, (
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

.chart {
  width: 100%;
  height: 300px;
}

.etf-list {
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
  .etf-header {
    flex-direction: column;
    align-items: flex-start;
    gap: spacer(3);
  }

  .etf-filters {
    width: 100%;
    justify-content: flex-start;
  }
}

@include media-breakpoint-down(md) {
  .etf-market {
    padding: spacer(3);
  }

  .etf-filters {
    flex-direction: column;
    align-items: stretch;
  }

  .chart {
    height: 250px;
  }
}

@include media-breakpoint-down(sm) {
  .etf-market {
    padding: spacer(2);
  }

  .etf-grid {
    gap: spacer(3);
  }

  .grid-card {
    padding: spacer(2);
  }

  .chart {
    height: 200px;
  }
}
</style>