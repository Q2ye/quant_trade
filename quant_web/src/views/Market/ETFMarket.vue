<!--ETF行情页-->
<template>
  <div class="etf-market">
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

    <div class="etf-grid">
      <div class="grid-card etf-trend-card">
        <h3>ETF资金流向</h3>
        <div class="trend-chart">
          <div id="fundFlowChart" class="chart"></div>
        </div>
      </div>

      <div class="grid-card etf-category-card">
        <h3>ETF分类分布</h3>
        <div class="category-chart">
          <div id="categoryChart" class="chart"></div>
        </div>
      </div>

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
    this.initFlowChart();
    this.initCategoryChart();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    if (this.flowChart) {
      this.flowChart.dispose();
    }
    if (this.categoryChart) {
      this.categoryChart.dispose();
    }
    window.removeEventListener('resize', this.handleResize);
  },
  methods: {
    refreshData() {
      console.log('刷新ETF数据...');
      // 模拟数据刷新
      this.topRisingETFs = [...this.topRisingETFs];
      this.allETFs = [...this.allETFs];
    },
    viewETFDetail(etf) {
      console.log('查看ETF详情:', etf.code);
      // 实际项目中这里会导航到ETF详情页
    },
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
    removeFavorite(etf) {
      const index = this.allETFs.findIndex(e => e.code === etf.code);
      if (index !== -1) {
        this.allETFs[index].isFavorite = false;
      }
      this.favoriteETFs = this.favoriteETFs.filter(f => f.code !== etf.code);
    },
    initFlowChart() {
      const chartDom = document.getElementById('fundFlowChart');
      this.flowChart = echarts.init(chartDom);

      const option = {
        backgroundColor: '#121a29',
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow'
          },
          backgroundColor: 'rgba(26,36,57,0.9)',
          borderColor: '#2a3a5a',
          textStyle: {
            color: '#e0e0e0'
          }
        },
        legend: {
          data: ['流入', '流出'],
          textStyle: {
            color: '#9da8b8'
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
              color: '#5d6c7b'
            }
          },
          axisLabel: {
            color: '#9da8b8'
          }
        },
        yAxis: {
          type: 'value',
          name: '亿元',
          axisLine: {
            lineStyle: {
              color: '#5d6c7b'
            }
          },
          splitLine: {
            lineStyle: {
              color: '#1e2a3e'
            }
          },
          axisLabel: {
            color: '#9da8b8'
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
              color: '#4caf50'
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
              color: '#f44336'
            }
          }
        ]
      };

      this.flowChart.setOption(option);
    },
    initCategoryChart() {
      const chartDom = document.getElementById('categoryChart');
      this.categoryChart = echarts.init(chartDom);

      const option = {
        backgroundColor: '#121a29',
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)',
          backgroundColor: 'rgba(26,36,57,0.9)',
          borderColor: '#2a3a5a',
          textStyle: {
            color: '#e0e0e0'
          }
        },
        legend: {
          orient: 'vertical',
          right: 10,
          top: 'center',
          textStyle: {
            color: '#9da8b8'
          }
        },
        series: [
          {
            name: 'ETF分类',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 10,
              borderColor: '#121a29',
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
                color: '#e0e0e0'
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
            ],
            color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de']
          }
        ]
      };

      this.categoryChart.setOption(option);
    },
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

<style scoped>
.etf-market {
  padding: 20px;
  background-color: #121a29;
  color: #e0e0e0;
  height: 100%;
  overflow-y: auto;
}

.etf-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #2a3a5a;
}

.etf-filters {
  display: flex;
  gap: 15px;
}

.etf-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

.grid-card {
  background: #1a2439;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.etf-trend-card {
  grid-column: 1;
}

.etf-category-card {
  grid-column: 2;
}

.etf-top-card {
  grid-column: 1;
}

.etf-favorite-card {
  grid-column: 2;
}

.chart {
  width: 100%;
  height: 300px;
}

.etf-list {
  background: #1a2439;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.etf-list h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #64b5f6;
  border-bottom: 1px solid #2a3a5a;
  padding-bottom: 10px;
}

.positive {
  color: #f44336;
}

.negative {
  color: #4caf50;
}

@media (max-width: 1200px) {
  .etf-grid {
    grid-template-columns: 1fr;
  }

  .etf-trend-card,
  .etf-category-card,
  .etf-top-card,
  .etf-favorite-card {
    grid-column: auto;
  }
}
</style>