<!--ETF详情页-->
<template>
  <div class="etf-detail">
    <div class="etf-header">
      <el-button icon="el-icon-arrow-left" @click="goBack">返回</el-button>
      <div class="etf-info">
        <h2>{{ etf.name }} ({{ etf.code }})</h2>
        <div class="price-info">
          <span class="current-price">{{ etf.price }}</span>
          <span :class="['price-change', etf.change > 0 ? 'positive' : 'negative']">
            {{ etf.change > 0 ? '+' : '' }}{{ etf.change }} ({{ etf.change > 0 ? '+' : '' }}{{ etf.changePercent }}%)
          </span>
        </div>
      </div>
      <div class="etf-actions">
        <el-button :type="isFavorite ? 'danger' : 'primary'" @click="toggleFavorite">
          {{ isFavorite ? '取消关注' : '加入自选' }}
        </el-button>
      </div>
    </div>

    <div class="etf-content">
      <!-- 左侧图表区域 -->
      <div class="chart-section">
        <div class="chart-container">
          <div class="chart-header">
            <div class="time-filters">
              <el-radio-group v-model="timePeriod" size="small">
                <el-radio-button label="1D">1日</el-radio-button>
                <el-radio-button label="1W">1周</el-radio-button>
                <el-radio-button label="1M">1月</el-radio-button>
                <el-radio-button label="3M">3月</el-radio-button>
                <el-radio-button label="1Y">1年</el-radio-button>
              </el-radio-group>
            </div>
            <div class="chart-type">
              <el-radio-group v-model="chartType" size="small">
                <el-radio-button label="line">分时</el-radio-button>
                <el-radio-button label="candlestick">K线</el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <div class="chart-wrapper">
            <div id="etfChart" class="chart"></div>
          </div>
        </div>

        <div class="indicator-selector">
          <el-select v-model="selectedIndicator" placeholder="选择技术指标" size="small">
            <el-option label="成交量" value="volume"></el-option>
            <el-option label="MACD" value="macd"></el-option>
            <el-option label="RSI" value="rsi"></el-option>
            <el-option label="布林带" value="boll"></el-option>
          </el-select>
        </div>
      </div>

      <!-- 右侧信息区域 -->
      <div class="info-section">
        <el-tabs v-model="activeTab" class="etf-tabs">
          <el-tab-pane label="基本信息" name="basic">
            <div class="basic-info">
              <div class="info-row">
                <div class="info-item">
                  <span class="info-label">基金全称</span>
                  <span class="info-value">{{ etf.fullName }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">基金管理人</span>
                  <span class="info-value">{{ etf.mgrName }}</span>
                </div>
              </div>
              <div class="info-row">
                <div class="info-item">
                  <span class="info-label">跟踪指数</span>
                  <span class="info-value">{{ etf.indexName }} ({{ etf.indexCode }})</span>
                </div>
                <div class="info-item">
                  <span class="info-label">基金规模</span>
                  <span class="info-value">{{ etf.fundSize }}亿元</span>
                </div>
              </div>
              <div class="info-row">
                <div class="info-item">
                  <span class="info-label">管理费率</span>
                  <span class="info-value">{{ etf.expenseRatio }}%</span>
                </div>
                <div class="info-item">
                  <span class="info-label">托管费率</span>
                  <span class="info-value">{{ etf.custodyFee }}%</span>
                </div>
              </div>
              <div class="info-row">
                <div class="info-item">
                  <span class="info-label">成立日期</span>
                  <span class="info-value">{{ etf.setupDate }}</span>
                </div>
                <div class="info-item">
                  <span class="info-label">上市日期</span>
                  <span class="info-value">{{ etf.listDate }}</span>
                </div>
              </div>
            </div>

            <div class="market-data">
              <h3>盘口数据</h3>
              <div class="quota-data">
                <div class="quota-row">
                  <div class="quota-item">
                    <span class="quota-label">今开</span>
                    <span class="quota-value">{{ etf.open }}</span>
                  </div>
                  <div class="quota-item">
                    <span class="quota-label">最高</span>
                    <span class="quota-value">{{ etf.high }}</span>
                  </div>
                  <div class="quota-item">
                    <span class="quota-label">最低</span>
                    <span class="quota-value">{{ etf.low }}</span>
                  </div>
                </div>
                <div class="quota-row">
                  <div class="quota-item">
                    <span class="quota-label">昨收</span>
                    <span class="quota-value">{{ etf.preClose }}</span>
                  </div>
                  <div class="quota-item">
                    <span class="quota-label">成交量</span>
                    <span class="quota-value">{{ etf.volume }}万手</span>
                  </div>
                  <div class="quota-item">
                    <span class="quota-label">成交额</span>
                    <span class="quota-value">{{ etf.amount }}万元</span>
                  </div>
                </div>
                <div class="quota-row">
                  <div class="quota-item">
                    <span class="quota-label">净值</span>
                    <span class="quota-value">{{ etf.nav }}</span>
                  </div>
                  <div class="quota-item">
                    <span class="quota-label">溢价率</span>
                    <span :class="['quota-value', etf.premiumRate > 0 ? 'positive' : 'negative']">
                      {{ etf.premiumRate > 0 ? '+' : '' }}{{ etf.premiumRate }}%
                    </span>
                  </div>
                  <div class="quota-item">
                    <span class="quota-label">换手率</span>
                    <span class="quota-value">{{ etf.turnoverRate }}%</span>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="成分股" name="constituents">
            <div class="constituents-data">
              <el-table :data="constituents" style="width: 100%" height="400">
                <el-table-column prop="code" label="股票代码" width="120"></el-table-column>
                <el-table-column prop="name" label="股票名称" width="150"></el-table-column>
                <el-table-column prop="weight" label="权重" width="100">
                  <template #default="scope">
                    {{ (scope.row.weight * 100).toFixed(2) }}%
                  </template>
                </el-table-column>
                <el-table-column prop="industry" label="行业" width="120"></el-table-column>
                <el-table-column prop="close" label="最新价" width="100"></el-table-column>
                <el-table-column prop="change" label="涨跌幅" width="100">
                  <template #default="scope">
                    <span :class="scope.row.change > 0 ? 'positive' : 'negative'">
                      {{ scope.row.change > 0 ? '+' : '' }}{{ scope.row.change }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="100">
                  <template #default="scope">
                    <el-button type="text" @click="viewStockDetail(scope.row)">查看</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>

          <el-tab-pane label="行业分布" name="industry">
            <div class="industry-chart">
              <div id="industryChart" class="chart" style="height: 400px;"></div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="相关资讯" name="news">
            <div class="news-list">
              <div v-for="item in news" :key="item.id" class="news-item">
                <div class="news-title">{{ item.title }}</div>
                <div class="news-meta">
                  <span class="news-time">{{ item.time }}</span>
                  <span class="news-source">{{ item.source }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'ETFDetail',
  props: {
    code: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      etf: {
        code: '510300',
        name: '沪深300ETF',
        fullName: '华泰柏瑞沪深300交易型开放式指数证券投资基金',
        price: '3.875',
        change: 0.78,
        changePercent: 0.44,
        open: '3.850',
        high: '3.880',
        low: '3.845',
        preClose: '3.845',
        volume: '12345.67',
        amount: '47890.12',
        nav: '3.872',
        premiumRate: 0.08,
        turnoverRate: 12.34,
        mgrName: '华泰柏瑞基金',
        indexCode: '000300.SH',
        indexName: '沪深300指数',
        fundSize: '850.25',
        expenseRatio: 0.50,
        custodyFee: 0.10,
        setupDate: '2012-05-04',
        listDate: '2012-05-28'
      },
      isFavorite: false,
      timePeriod: '1D',
      chartType: 'line',
      selectedIndicator: 'volume',
      activeTab: 'basic',
      constituents: [
        { code: '600519', name: '贵州茅台', weight: 0.0523, industry: '食品饮料', close: '1785.45', change: 0.44 },
        { code: '300750', name: '宁德时代', weight: 0.0315, industry: '电力设备', close: '185.67', change: 1.23 },
        { code: '000858', name: '五粮液', weight: 0.0241, industry: '食品饮料', close: '152.34', change: -0.56 },
        { code: '601318', name: '中国平安', weight: 0.0218, industry: '非银金融', close: '45.67', change: 0.89 },
        { code: '600036', name: '招商银行', weight: 0.0195, industry: '银行', close: '32.45', change: 0.31 },
        { code: '000333', name: '美的集团', weight: 0.0156, industry: '家用电器', close: '56.78', change: -0.12 },
        { code: '601888', name: '中国中免', weight: 0.0142, industry: '商贸零售', close: '87.65', change: 2.34 },
        { code: '601012', name: '隆基绿能', weight: 0.0137, industry: '电力设备', close: '23.45', change: -1.23 }
      ],
      news: [
        { id: 1, title: '沪深300ETF规模突破850亿元，创历史新高', time: '2023-08-10 09:30', source: '证券时报' },
        { id: 2, title: '机构资金持续流入宽基ETF，市场信心逐步恢复', time: '2023-08-09 14:25', source: '财经网' },
        { id: 3, title: '沪深300指数成分股调整在即，多只个股将受益', time: '2023-08-08 18:40', source: '东方财富' },
        { id: 4, title: 'ETF互联互通扩容，外资加速配置A股核心资产', time: '2023-08-07 10:15', source: '中国证券报' }
      ],
      chart: null,
      industryChart: null
    };
  },
  mounted() {
    this.initChart();
    this.initIndustryChart();
    this.loadETFData();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    if (this.chart) {
      this.chart.dispose();
    }
    if (this.industryChart) {
      this.industryChart.dispose();
    }
    window.removeEventListener('resize', this.handleResize);
  },
  methods: {
    goBack() {
      this.$router.go(-1);
    },
    toggleFavorite() {
      this.isFavorite = !this.isFavorite;
      this.$message({
        message: this.isFavorite ? '已加入自选ETF' : '已移除自选ETF',
        type: 'success'
      });
    },
    viewStockDetail(stock) {
      this.$router.push(`/market/stock/${stock.code}`);
    },
    loadETFData() {
      // 实际项目中这里会调用API获取ETF数据
      console.log('加载ETF数据:', this.code);
    },
    initChart() {
      const chartDom = document.getElementById('etfChart');
      this.chart = echarts.init(chartDom);

      const option = {
        backgroundColor: '#121a29',
        grid: {
          left: '10%',
          right: '10%',
          bottom: '15%',
          top: '10%'
        },
        xAxis: {
          type: 'category',
          data: ['09:30', '10:00', '10:30', '11:00', '11:30', '13:00', '13:30', '14:00', '14:30', '15:00'],
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
          scale: true,
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
        series: [{
          type: 'line',
          data: [3.850, 3.855, 3.862, 3.868, 3.865, 3.870, 3.875, 3.872, 3.868, 3.875],
          smooth: true,
          lineStyle: {
            color: '#64b5f6',
            width: 2
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [{
                offset: 0,
                color: 'rgba(100, 181, 246, 0.3)'
              }, {
                offset: 1,
                color: 'rgba(100, 181, 246, 0.1)'
              }]
            }
          },
          symbol: 'none'
        }],
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross'
          },
          backgroundColor: 'rgba(26,36,57,0.9)',
          borderColor: '#2a3a5a',
          textStyle: {
            color: '#e0e0e0'
          }
        }
      };

      this.chart.setOption(option);
    },
    initIndustryChart() {
      const chartDom = document.getElementById('industryChart');
      this.industryChart = echarts.init(chartDom);

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
        series: [{
          name: '行业分布',
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
            { value: 28.5, name: '金融' },
            { value: 18.2, name: '信息技术' },
            { value: 15.8, name: '工业' },
            { value: 12.3, name: '主要消费' },
            { value: 8.7, name: '医药卫生' },
            { value: 7.2, name: '原材料' },
            { value: 4.5, name: '能源' },
            { value: 4.8, name: '其他' }
          ],
          color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4']
        }]
      };

      this.industryChart.setOption(option);
    },
    handleResize() {
      if (this.chart) {
        this.chart.resize();
      }
      if (this.industryChart) {
        this.industryChart.resize();
      }
    }
  }
};
</script>

<style scoped>
.etf-detail {
  padding: 20px;
  background-color: #121a29;
  color: #e0e0e0;
  height: 100%;
  overflow-y: auto;
}

.etf-header {
  display: flex;
  align-items: center;
  padding-bottom: 20px;
  border-bottom: 1px solid #2a3a5a;
  margin-bottom: 20px;
}

.etf-info {
  flex: 1;
  padding: 0 20px;
}

.price-info {
  display: flex;
  align-items: center;
  margin-top: 10px;
}

.current-price {
  font-size: 28px;
  font-weight: bold;
  margin-right: 15px;
}

.price-change {
  font-size: 18px;
  font-weight: bold;
}

.positive {
  color: #f44336;
}

.negative {
  color: #4caf50;
}

.etf-content {
  display: flex;
  gap: 20px;
}

.chart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart-container {
  background: #1a2439;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 20px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  padding: 10px 15px;
  background: #152136;
  border-bottom: 1px solid #2a3a5a;
}

.chart-wrapper {
  height: 400px;
  padding: 10px;
}

#etfChart {
  width: 100%;
  height: 100%;
}

.indicator-selector {
  background: #1a2439;
  border-radius: 8px;
  padding: 15px;
}

.info-section {
  width: 400px;
}

.etf-tabs {
  background: #1a2439;
  border-radius: 8px;
  overflow: hidden;
}

.basic-info {
  padding: 20px;
}

.info-row {
  display: flex;
  margin-bottom: 15px;
}

.info-item {
  flex: 1;
  padding: 10px;
}

.info-label {
  display: block;
  color: #9da8b8;
  font-size: 14px;
  margin-bottom: 5px;
}

.info-value {
  display: block;
  font-size: 16px;
  font-weight: bold;
}

.market-data {
  padding: 0 20px 20px;
}

.market-data h3 {
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #2a3a5a;
}

.quota-data {
  padding: 10px 0;
}

.quota-row {
  display: flex;
  margin-bottom: 15px;
}

.quota-item {
  flex: 1;
  text-align: center;
  padding: 10px;
  background: #152136;
  border-radius: 6px;
  margin: 0 5px;
}

.quota-label {
  display: block;
  color: #9da8b8;
  font-size: 14px;
  margin-bottom: 5px;
}

.quota-value {
  display: block;
  font-size: 16px;
  font-weight: bold;
}

.constituents-data {
  padding: 20px;
}

.industry-chart {
  padding: 20px;
}

.news-list {
  padding: 10px;
}

.news-item {
  padding: 15px;
  border-bottom: 1px solid #2a3a5a;
  cursor: pointer;
  transition: background 0.3s;
}

.news-item:hover {
  background: #152136;
}

.news-title {
  font-size: 15px;
  margin-bottom: 8px;
}

.news-meta {
  display: flex;
  font-size: 12px;
  color: #9da8b8;
}

.news-time {
  margin-right: 15px;
}

@media (max-width: 1200px) {
  .etf-content {
    flex-direction: column;
  }

  .info-section {
    width: 100%;
  }
}
</style>