<!--篮子详情-->
<script>
import { fetchBasketDetail } from '@/api/basket.js'
import { fetchStockRealTime } from '@/api/data.js'
import NetValueChart from '@/components/charts/NetValueChart'

export default {
  name: "BasketDetail",
  components: { NetValueChart },
  data() {
    return {
      basket: {
        id: '',
        name: '',
        description: '',
        items: []
      },
      realTimeData: {},
      loading: false,
      chartData: {
        dates: [],
        values: [],
        benchmark: []
      }
    }
  },
  created() {
    const basketId = this.$route.params.id
    if (basketId) {
      this.getBasketDetail(basketId)
    }
  },
  methods: {
    async getBasketDetail(basketId) {
      this.loading = true
      try {
        const response = await fetchBasketDetail(basketId)
        this.basket = response.data
        this.getRealTimeData()
        this.loadChartData()
      } catch (error) {
        console.error('获取篮子详情失败:', error)
        this.$message.error('获取数据失败')
      } finally {
        this.loading = false
      }
    },

    async getRealTimeData() {
      const codes = this.basket.items.map(item => item.ts_code)
      try {
        const data = await fetchStockRealTime(codes)
        this.realTimeData = data
      } catch (error) {
        console.error('获取实时行情失败:', error)
      }
    },

    async loadChartData() {
      // 实际项目中从API获取数据
      // 这里模拟数据
      this.chartData = {
        dates: ['2023-01', '2023-02', '2023-03', '2023-04'],
        values: [1.0, 1.05, 1.12, 1.08],
        benchmark: [1.0, 1.03, 1.10, 1.05]
      }
    },

    formatPercent(value) {
      return (value * 100).toFixed(2) + '%'
    },

    getStockColor(change) {
      return change > 0 ? 'color-up' : change < 0 ? 'color-down' : ''
    }
  }
}
</script>

<template>
  <div class="basket-detail">
    <div v-loading="loading">
      <el-page-header @back="$router.go(-1)" :content="basket.name" />

      <div class="header">
        <h2>{{ basket.name }}</h2>
        <p class="description">{{ basket.description }}</p>
      </div>

      <div class="chart-section">
        <h3>篮子净值走势</h3>
        <net-value-chart :chart-data="chartData" height="400px" />
      </div>

      <div class="stocks-section">
        <h3>成分股列表</h3>
        <el-table :data="basket.items" stripe>
          <el-table-column prop="ts_code" label="代码" width="100" />
          <el-table-column label="名称" min-width="150">
            <template slot-scope="scope">
              {{ scope.row.stock_info ? scope.row.stock_info.name : scope.row.ts_code }}
            </template>
          </el-table-column>
          <el-table-column label="当前价" width="120">
            <template slot-scope="scope">
              {{ realTimeData[scope.row.ts_code] ? realTimeData[scope.row.ts_code].price : '--' }}
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="120">
            <template slot-scope="scope">
              <span :class="getStockColor(realTimeData[scope.row.ts_code] ? realTimeData[scope.row.ts_code].change_percent : 0)">
                {{ realTimeData[scope.row.ts_code] ? realTimeData[scope.row.ts_code].change_percent + '%' : '--' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="权重" width="120">
            <template slot-scope="scope">
              {{ formatPercent(scope.row.weight) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template slot-scope="scope">
              <el-button
                type="text"
                @click="$router.push(`/market/detail/${scope.row.ts_code}`)">
                行情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.basket-detail {
  padding: 20px;
  background-color: #fff;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,.1);
}

.header {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}

.description {
  color: #666;
  margin-top: 5px;
}

.chart-section {
  margin-bottom: 30px;
}

.stocks-section {
  margin-top: 30px;
}

.color-up {
  color: #f56c6c;
}

.color-down {
  color: #67c23a;
}
</style>