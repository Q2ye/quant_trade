<!-- ETF行情页 - 基于主题系统优化 -->
<template>
  <div class="etf-market">
    <!-- 页面头部区域 -->
    <div class="etf-header">
      <h2>ETF行情</h2>
      <div class="etf-filters">
        <el-select v-model="selectedCategory" placeholder="选择分类">
          <el-option label="全部" value="all"></el-option>
          <el-option label="股票型" value="stock"></el-option>
          <el-option label="债券型" value="bond"></el-option>
          <el-option label="商品型" value="commodity"></el-option>
          <el-option label="货币型" value="currency"></el-option>
          <el-option label="跨境型" value="overseas"></el-option>
        </el-select>
        <el-input v-model="searchKeyword" placeholder="搜索ETF名称或代码" clearable>
          <template #prefix>
            <el-icon><search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" icon="el-icon-refresh" @click="refreshData">刷新</el-button>
      </div>
    </div>

    <!-- ETF数据网格布局 -->
    <div class="etf-grid">
      <!-- 资金流向图表卡片 -->
      <div class="grid-card etf-trend-card">
        <h3>ETF资金流向</h3>
        <div class="trend-chart">
          <div id="fundFlowChart" class="chart"></div>
        </div>
      </div>

      <!-- 分类分布图表卡片 -->
      <div class="grid-card etf-category-card">
        <h3>ETF分类分布</h3>
        <div class="category-chart">
          <div id="categoryChart" class="chart"></div>
        </div>
      </div>

      <!-- 涨幅榜卡片 -->
      <div class="grid-card etf-top-card">
        <h3>ETF涨幅榜</h3>
        <el-table :data="topRisingETFs" style="width: 100%">
          <el-table-column prop="code" label="代码" width="80"></el-table-column>
          <el-table-column prop="name" label="名称"></el-table-column>
          <el-table-column prop="price" label="最新价"></el-table-column>
          <el-table-column prop="change" label="涨跌幅">
            <template #default="scope">
              <span :class="scope.row.change > 0 ? 'positive' : 'negative'">
                {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="volume" label="成交量(万)"></el-table-column>
          <el-table-column label="操作">
            <template #default="scope">
              <el-button size="mini" @click="viewETFDetail(scope.row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 关注列表卡片 -->
      <div class="grid-card etf-favorite-card">
        <h3>我的ETF关注</h3>
        <el-table :data="favoriteETFs" style="width: 100%">
          <el-table-column prop="code" label="代码" width="80"></el-table-column>
          <el-table-column prop="name" label="名称"></el-table-column>
          <el-table-column prop="price" label="最新价"></el-table-column>
          <el-table-column prop="change" label="涨跌幅">
            <template #default="scope">
              <span :class="scope.row.change > 0 ? 'positive' : 'negative'">
                {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="scope">
              <el-button size="mini" type="danger" @click="removeFavorite(scope.row)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ETF完整列表 -->
    <div class="etf-list">
      <h3>ETF列表</h3>
      <el-table :data="filteredETFs" style="width: 100%">
        <el-table-column prop="code" label="代码" width="100"></el-table-column>
        <el-table-column prop="name" label="名称"></el-table-column>
        <el-table-column prop="category" label="类型" width="100"></el-table-column>
        <el-table-column prop="price" label="最新价" width="100"></el-table-column>
        <el-table-column prop="change" label="涨跌幅" width="120">
          <template #default="scope">
            <span :class="scope.row.change > 0 ? 'positive' : 'negative'">
              {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="volume" label="成交量(万)" width="120"></el-table-column>
        <el-table-column prop="amount" label="成交额(万)" width="120"></el-table-column>
        <el-table-column prop="index" label="跟踪指数" width="180"></el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button size="mini" @click="viewETFDetail(scope.row)">详情</el-button>
            <el-button size="mini" type="primary" @click="toggleFavorite(scope.row)">
              {{ scope.row.isFavorite ? '取消' : '关注' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'ETFMarket',
  data() {
    return {
      selectedCategory: 'all',
      searchKeyword: '',
      topRisingETFs: [
        { code: '515790', name: '光伏ETF', category: '股票型', price: '1.245', change: 3.75, volume: '12345', amount: '5432', index: '中证光伏产业指数' },
        { code: '159995', name: '芯片ETF', category: '股票型', price: '1.087', change: 2.94, volume: '23456', amount: '6543', index: '国证半导体芯片指数' },
        { code: '515030', name: '新能源车ETF', category: '股票型', price: '1.325', change: 2.32, volume: '34567', amount: '7654', index: '中证新能源汽车指数' },
        { code: '512480', name: '半导体ETF', category: '股票型', price: '0.985', change: 1.96, volume: '45678', amount: '8765', index: '中证全指半导体指数' },
        { code: '512000', name: '券商ETF', category: '股票型', price: '0.876', change: 1.85, volume: '56789', amount: '9876', index: '中证全指证券公司指数' }
      ],
      favoriteETFs: [
        { code: '510300', name: '沪深300ETF', category: '股票型', price: '3.875', change: 0.78, volume: '123456', amount: '12345', index: '沪深300指数', isFavorite: true },
        { code: '510050', name: '上证50ETF', category: '股票型', price: '2.765', change: 0.45, volume: '98765', amount: '8765', index: '上证50指数', isFavorite: true }
      ],
      allETFs: [
        { code: '510300', name: '沪深300ETF', category: '股票型', price: '3.875', change: 0.78, volume: '123456', amount: '12345', index: '沪深300指数', isFavorite: true },
        { code: '510050', name: '上证50ETF', category: '股票型', price: '2.765', change: 0.45, volume: '98765', amount: '8765', index: '上证50指数', isFavorite: true },
        { code: '159915', name: '创业板ETF', category: '股票型', price: '2.345', change: 1.25, volume: '87654', amount: '7654', index: '创业板指数', isFavorite: false },
        { code: '515790', name: '光伏ETF', category: '股票型', price: '1.245', change: 3.75, volume: '12345', amount: '5432', index: '中证光伏产业指数', isFavorite: false },
        { code: '159995', name: '芯片ETF', category: '股票型', price: '1.087', change: 2.94, volume: '23456', amount: '6543', index: '国证半导体芯片指数', isFavorite: false },
        { code: '511010', name: '国债ETF', category: '债券型', price: '130.456', change: 0.12, volume: '3456', amount: '4321', index: '上证5年期国债指数', isFavorite: false },
        { code: '518800', name: '黄金ETF', category: '商品型', price: '4.325', change: 0.45, volume: '4567', amount: '3210', index: '上海金现货合约', isFavorite: false },
        { code: '511990', name: '货币ETF', category: '货币型', price: '100.025', change: 0.01, volume: '5678', amount: '2109', index: '银行间市场利率', isFavorite: false },
        { code: '513500', name: '标普500ETF', category: '跨境型', price: '1.345', change: -0.25, volume: '6789', amount: '1098', index: '标普500指数', isFavorite: false }
      ],
      flowChart: null,
      categoryChart: null
    };
  },
  computed: {
    // 过滤ETF数据
    filteredETFs() {
      let result = this.allETFs;

      // 按类别筛选
      if (this.selectedCategory !== 'all') {
        result = result.filter(etf => etf.category === this.selectedCategory);
      }

      // 按关键词筛选
      if (this.searchKeyword) {
        const keyword = this.searchKeyword.toLowerCase();
        result = result.filter(etf =>
          etf.code.toLowerCase().includes(keyword) ||
          etf.name.toLowerCase().includes(keyword)
        );
      }

      return result;
    }
  },
  mounted() {
    // 初始化图表
    this.initFlowChart();
    this.initCategoryChart();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    // 清理图表实例
    if (this.flowChart) {
      this.flowChart.dispose();
    }
    if (this.categoryChart) {
      this.categoryChart.dispose();
    }
    window.removeEventListener('resize', this.handleResize);
  },
  methods: {
    // 刷新数据
    refreshData() {
      console.log('刷新ETF数据...');
      // 模拟数据刷新
      this.topRisingETFs = [...this.topRisingETFs];
      this.allETFs = [...this.allETFs];
    },
    // 查看ETF详情
    viewETFDetail(etf) {
      console.log('查看ETF详情:', etf.code);
      // 实际项目中这里会导航到ETF详情页
    },
    // 切换关注状态
    toggleFavorite(etf) {
      etf.isFavorite = !etf.isFavorite;
      if (etf.isFavorite) {
        // 添加到关注列表
        if (!this.favoriteETFs.some(f => f.code === etf.code)) {
          this.favoriteETFs.push({...etf});
        }
      } else {
        // 从关注列表移除
        this.favoriteETFs = this.favoriteETFs.filter(f => f.code !== etf.code);
      }
    },
    // 移除关注
    removeFavorite(etf) {
      const index = this.allETFs.findIndex(e => e.code === etf.code);
      if (index !== -1) {
        this.allETFs[index].isFavorite = false;
      }
      this.favoriteETFs = this.favoriteETFs.filter(f => f.code !== etf.code);
    },
    // 初始化资金流向图表
    initFlowChart() {
      const chartDom = document.getElementById('fundFlowChart');
      this.flowChart = echarts.init(chartDom);

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          },
          backgroundColor: $secondary-bg,
          borderColor: $border-color,
          textStyle: {
            color: $text-primary
          }
        },
        legend: {
          data: ['流入', '流出'],
          textStyle: {
            color: $text-secondary
          },
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
          data: ['周一', '周二', '周三', '周四', '周五'],
          axisLine: {
            lineStyle: {
              color: $border-color
            }
          },
          axisLabel: {
            color: $text-secondary
          }
        },
        yAxis: {
          type: 'value',
          name: '亿元',
          axisLine: {
            lineStyle: {
              color: $border-color
            }
          },
          splitLine: {
            lineStyle: {
              color: $secondary-bg
            }
          },
          axisLabel: {
            color: $text-secondary
          }
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
              color: $stock-up-color
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
              color: $stock-down-color
            }
          }
        ]
      };

      this.flowChart.setOption(option);
    },
    // 初始化分类分布图表
    initCategoryChart() {
      const chartDom = document.getElementById('categoryChart');
      this.categoryChart = echarts.init(chartDom);

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)',
          backgroundColor: $secondary-bg,
          borderColor: $border-color,
          textStyle: {
            color: $text-primary
          }
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center',
          textStyle: {
            color: $text-secondary
          }
        },
        series: [
          {
            name: 'ETF分类',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: $border-radius,
              borderColor: $primary-bg,
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
                fontWeight: 'bold',
                color: $text-primary
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
      };

      this.categoryChart.setOption(option);
    },
    // 处理窗口大小变化
    handleResize() {
      if (this.flowChart) {
        this.flowChart.resize();
      }
      if (this.categoryChart) {
        this.categoryChart.resize();
      }
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

.etf-market {
  padding: $content-padding;
  background-color: $primary-bg;
  color: $text-primary;
  height: 100%;
  overflow-y: auto;
}

.etf-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: map.get($spacers, 4);
  padding-bottom: map.get($spacers, 3);
  border-bottom: $border-width solid $border-color;

  h2 {
    font-size: $font-size-base * 1.5;
    font-weight: $font-weight-semibold;
    color: $text-primary;
    margin: 0;
  }
}

.etf-filters {
  display: flex;
  gap: map.get($spacers, 3);
  align-items: center;
}

.etf-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: map.get($spacers, 4);
  margin-bottom: map.get($spacers, 5);

  // 应用卡片网格布局混入
  @include mixin.card-grid-layout(2, (
    'lg': 1,
    'md': 1,
    'sm': 1
  ));
}

// 网格卡片通用样式
.grid-card {
  @include mixin.card-base;
  padding: map.get($spacers, 3);
  height: 100%;
  transition: all $transition-normal;

  h3 {
    font-size: $font-size-base * 1.1;
    font-weight: $font-weight-semibold;
    color: $text-primary;
    margin: 0 0 map.get($spacers, 3) 0;
    padding-bottom: map.get($spacers, 2);
    border-bottom: $border-width solid $border-color;
  }

  &:hover {
    transform: $hover-transform;
    box-shadow: $card-hover-shadow;
  }
}

// 图表容器样式
.chart {
  width: 100%;
  height: 300px;
}

// ETF列表样式
.etf-list {
  @include mixin.card-base;
  padding: map.get($spacers, 3);

  h3 {
    font-size: $font-size-base * 1.1;
    font-weight: $font-weight-semibold;
    color: $text-primary;
    margin: 0 0 map.get($spacers, 3) 0;
    padding-bottom: map.get($spacers, 2);
    border-bottom: $border-width solid $border-color;
  }
}

// 价格涨跌颜色样式
.positive {
  color: $stock-up-color;
  font-weight: $font-weight-medium;
}

.negative {
  color: $stock-down-color;
  font-weight: $font-weight-medium;
}

// 响应式设计
@include mixin.media-breakpoint-down(lg) {
  .etf-header {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 3);
  }

  .etf-filters {
    width: 100%;
    justify-content: flex-start;
  }
}

@include mixin.media-breakpoint-down(md) {
  .etf-market {
    padding: map.get($spacers, 3);
  }

  .etf-filters {
    flex-direction: column;
    align-items: stretch;
  }

  .chart {
    height: 250px;
  }
}

@include mixin.media-breakpoint-down(sm) {
  .etf-market {
    padding: map.get($spacers, 2);
  }

  .etf-grid {
    gap: map.get($spacers, 3);
  }

  .grid-card {
    padding: map.get($spacers, 2);
  }

  .chart {
    height: 200px;
  }
}
</style>