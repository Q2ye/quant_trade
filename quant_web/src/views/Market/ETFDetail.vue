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
        backgroundColor: $primary-bg,
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
              color: $border-color
            }
          },
          axisLabel: {
            color: $text-secondary
          }
        },
        yAxis: {
          scale: true,
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
        series: [{
          type: 'line',
          data: [3.850, 3.855, 3.862, 3.868, 3.865, 3.870, 3.875, 3.872, 3.868, 3.875],
          smooth: true,
          lineStyle: {
            color: $accent-color,
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
                color: 'color-mix(in srgb, #{$accent-color} 30%, transparent)'
              }, {
                offset: 1,
                color: 'color-mix(in srgb, #{$accent-color} 10%, transparent)'
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
          backgroundColor: $secondary-bg,
          borderColor: $border-color,
          textStyle: {
            color: $text-primary
          }
        }
      };

      this.chart.setOption(option);
    },
    initIndustryChart() {
      const chartDom = document.getElementById('industryChart');
      this.industryChart = echarts.init(chartDom);

      const option = {
        backgroundColor: $primary-bg,
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
        series: [{
          name: '行业分布',
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
            { value: 28.5, name: '金融' },
            { value: 18.2, name: '信息技术' },
            { value: 15.8, name: '工业' },
            { value: 12.3, name: '主要消费' },
            { value: 8.7, name: '医药卫生' },
            { value: 7.2, name: '原材料' },
            { value: 4.5, name: '能源' },
            { value: 4.8, name: '其他' }
          ]
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

<style scoped lang="scss">
/* 引入全局主题变量和混入 */
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color';

.etf-detail {
  padding: $content-padding;
  background-color: $primary-bg;
  color: $text-primary;
  height: 100%;
  overflow-y: auto;

  /* 应用主题过渡动画 */
  @extend .theme-transition;
}

/* ETF头部信息区域 */
.etf-header {
  display: flex;
  align-items: center;
  padding-bottom: map.get($spacers, 4);
  border-bottom: $border-width solid $border-color;
  margin-bottom: map.get($spacers, 4);

  /* 应用卡片基础样式 */
  @include mixin.card-base(false);
  padding: map.get($spacers, 3);
}

.etf-info {
  flex: 1;
  padding: 0 map.get($spacers, 4);
}

/* 价格信息显示 */
.price-info {
  display: flex;
  align-items: center;
  margin-top: map.get($spacers, 2);
}

.current-price {
  font-size: 1.75rem;
  font-weight: $font-weight-bold;
  margin-right: map.get($spacers, 3);
  color: $text-primary;
}

.price-change {
  font-size: 1.125rem;
  font-weight: $font-weight-semibold;
}

/* 涨跌颜色定义 */
.positive {
  color: $stock-up-color;
}

.negative {
  color: $stock-down-color;
}

/* 主要内容区域布局 */
.etf-content {
  display: flex;
  gap: map.get($spacers, 4);

  /* 响应式调整 */
  @include mixin.media-breakpoint-down(lg) {
    flex-direction: column;
  }
}

/* 图表区域样式 */
.chart-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chart-container {
  /* 应用卡片基础样式 */
  @include mixin.card-base;
  border-radius: $border-radius-lg;
  overflow: hidden;
  margin-bottom: map.get($spacers, 4);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  padding: map.get($spacers, 2) map.get($spacers, 3);
  background: $card-header-bg;
  border-bottom: $border-width solid $border-color;
}

.chart-wrapper {
  height: $chart-height;
  padding: map.get($spacers, 2);
}

#etfChart {
  width: 100%;
  height: 100%;
}

/* 指标选择器 */
.indicator-selector {
  /* 应用卡片基础样式 */
  @include mixin.card-base;
  border-radius: $border-radius;
  padding: map.get($spacers, 3);
}

/* 信息区域样式 */
.info-section {
  width: 400px;

  /* 响应式调整 */
  @include mixin.media-breakpoint-down(lg) {
    width: 100%;
  }
}

.etf-tabs {
  /* 应用卡片基础样式 */
  @include mixin.card-base;
  border-radius: $border-radius-lg;
  overflow: hidden;
}

/* 基本信息样式 */
.basic-info {
  padding: map.get($spacers, 4);
}

.info-row {
  display: flex;
  margin-bottom: map.get($spacers, 3);
}

.info-item {
  flex: 1;
  padding: map.get($spacers, 2);
}

.info-label {
  display: block;
  color: $text-secondary;
  font-size: $font-size-base * 0.875;
  margin-bottom: map.get($spacers, 1);
}

.info-value {
  display: block;
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  color: $text-primary;
}

/* 盘口数据样式 */
.market-data {
  padding: 0 map.get($spacers, 4) map.get($spacers, 4);
}

.market-data h3 {
  margin-top: 0;
  padding-bottom: map.get($spacers, 2);
  border-bottom: $border-width solid $border-color;
  color: $text-primary;
  font-weight: $font-weight-semibold;
}

.quota-data {
  padding: map.get($spacers, 2) 0;
}

.quota-row {
  display: flex;
  margin-bottom: map.get($spacers, 3);
}

.quota-item {
  flex: 1;
  text-align: center;
  padding: map.get($spacers, 2);
  background: $secondary-bg;
  border-radius: $border-radius;
  margin: 0 map.get($spacers, 1);

  /* 应用主题过渡 */
  @extend .theme-transition;
}

.quota-label {
  display: block;
  color: $text-secondary;
  font-size: $font-size-base * 0.875;
  margin-bottom: map.get($spacers, 1);
}

.quota-value {
  display: block;
  font-size: $font-size-base;
  font-weight: $font-weight-semibold;
  color: $text-primary;
}

/* 成分股数据样式 */
.constituents-data {
  padding: map.get($spacers, 4);
}

/* 行业分布图表样式 */
.industry-chart {
  padding: map.get($spacers, 4);
}

/* 新闻列表样式 */
.news-list {
  padding: map.get($spacers, 2);
}

.news-item {
  padding: map.get($spacers, 3);
  border-bottom: $border-width solid $border-color;
  cursor: pointer;

  /* 应用主题过渡和悬停效果 */
  @extend .theme-transition;

  &:hover {
    background: $hover-bg;
  }

  &:last-child {
    border-bottom: none;
  }
}

.news-title {
  font-size: $font-size-base;
  margin-bottom: map.get($spacers, 2);
  color: $text-primary;
  font-weight: $font-weight-medium;
}

.news-meta {
  display: flex;
  font-size: $font-size-base * 0.875;
  color: $text-secondary;
}

.news-time {
  margin-right: map.get($spacers, 3);
}

/* 响应式设计优化 */
@include mixin.media-breakpoint-down(md) {
  .etf-header {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 3);
  }

  .etf-info {
    padding: 0;
    width: 100%;
  }

  .info-row {
    flex-direction: column;
    gap: map.get($spacers, 2);
  }

  .info-item {
    padding: map.get($spacers, 1);
  }

  .quota-row {
    flex-direction: column;
    gap: map.get($spacers, 2);
  }

  .quota-item {
    margin: 0;
  }

  .price-info {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 2);
  }
}

@include mixin.media-breakpoint-down(sm) {
  .etf-detail {
    padding: map.get($spacers, 2);
  }

  .chart-header {
    flex-direction: column;
    gap: map.get($spacers, 2);
  }

  .chart-wrapper {
    height: 300px;
  }
}
</style>