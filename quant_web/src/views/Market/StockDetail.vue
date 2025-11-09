<!--个股详情页-->
<template>
  <div class="stock-detail">
    <div class="stock-header">
      <el-button icon="el-icon-arrow-left" @click="goBack">返回</el-button>
      <div class="stock-info">
        <h2>{{ stock.name }} ({{ stock.code }})</h2>
        <div class="price-info">
          <span class="current-price">{{ stock.price }}</span>
          <span :class="['price-change', stock.change > 0 ? 'positive' : 'negative']">
            {{ stock.change > 0 ? '+' : '' }}{{ stock.change }} ({{ stock.change > 0 ? '+' : '' }}{{ stock.changePercent }}%)
          </span>
        </div>
      </div>
      <div class="stock-actions">
        <el-button :type="isFavorite ? 'danger' : 'primary'" @click="toggleFavorite">
          {{ isFavorite ? '取消关注' : '加入自选' }}
        </el-button>
      </div>
    </div>

    <div class="stock-content">
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
                <el-radio-button label="candlestick">K线</el-radio-button>
                <el-radio-button label="line">分时</el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <div class="chart-wrapper">
            <div id="stockChart" class="chart"></div>
          </div>
        </div>

        <div class="indicator-selector">
          <el-select v-model="selectedIndicator" placeholder="选择技术指标" size="small">
            <el-option label="MACD" value="macd"></el-option>
            <el-option label="KDJ" value="kdj"></el-option>
            <el-option label="RSI" value="rsi"></el-option>
            <el-option label="BOLL" value="boll"></el-option>
            <el-option label="成交量" value="volume"></el-option>
          </el-select>
        </div>
      </div>

      <!-- 右侧信息区域 -->
      <div class="info-section">
        <el-tabs v-model="activeTab" class="stock-tabs">
          <el-tab-pane label="盘口数据" name="quota">
            <div class="quota-data">
              <div class="quota-row">
                <div class="quota-item">
                  <span class="quota-label">今开</span>
                  <span class="quota-value">{{ stock.open }}</span>
                </div>
                <div class="quota-item">
                  <span class="quota-label">最高</span>
                  <span class="quota-value">{{ stock.high }}</span>
                </div>
                <div class="quota-item">
                  <span class="quota-label">最低</span>
                  <span class="quota-value">{{ stock.low }}</span>
                </div>
              </div>
              <div class="quota-row">
                <div class="quota-item">
                  <span class="quota-label">昨收</span>
                  <span class="quota-value">{{ stock.preClose }}</span>
                </div>
                <div class="quota-item">
                  <span class="quota-label">成交量</span>
                  <span class="quota-value">{{ stock.volume }}手</span>
                </div>
                <div class="quota-item">
                  <span class="quota-label">成交额</span>
                  <span class="quota-value">{{ stock.amount }}万</span>
                </div>
              </div>
              <div class="quota-row">
                <div class="quota-item">
                  <span class="quota-label">市盈率</span>
                  <span class="quota-value">{{ stock.pe }}</span>
                </div>
                <div class="quota-item">
                  <span class="quota-label">市净率</span>
                  <span class="quota-value">{{ stock.pb }}</span>
                </div>
                <div class="quota-item">
                  <span class="quota-label">总市值</span>
                  <span class="quota-value">{{ stock.marketCap }}亿</span>
                </div>
              </div>
            </div>

            <div class="order-book">
              <h3>买卖五档</h3>
              <div class="order-table">
                <div class="order-row" v-for="(bid, index) in bids" :key="'bid'+index">
                  <div class="order-type buy">买{{ index+1 }}</div>
                  <div class="order-price">{{ bid.price }}</div>
                  <div class="order-volume">{{ bid.volume }}</div>
                </div>
                <div class="divider"></div>
                <div class="order-row" v-for="(ask, index) in asks" :key="'ask'+index">
                  <div class="order-type sell">卖{{ index+1 }}</div>
                  <div class="order-price">{{ ask.price }}</div>
                  <div class="order-volume">{{ ask.volume }}</div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="财务数据" name="financial">
            <div class="financial-data">
              <el-table :data="financialData" style="width: 100%">
                <el-table-column prop="item" label="项目"></el-table-column>
                <el-table-column prop="value" label="数值"></el-table-column>
                <el-table-column prop="change" label="同比变化"></el-table-column>
              </el-table>
            </div>
          </el-tab-pane>

          <el-tab-pane label="公司资讯" name="news">
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
  name: 'StockDetail',
  data() {
    return {
      stock: {
        code: '600519',
        name: '贵州茅台',
        price: '1785.45',
        change: 7.89,
        changePercent: 0.44,
        open: '1770.00',
        high: '1790.50',
        low: '1765.80',
        preClose: '1777.56',
        volume: '54321',
        amount: '968.42',
        pe: '38.45',
        pb: '12.78',
        marketCap: '22400'
      },
      isFavorite: true,
      timePeriod: '1D',
      chartType: 'candlestick',
      selectedIndicator: 'volume',
      activeTab: 'quota',
      bids: [
        { price: '1785.44', volume: '15' },
        { price: '1785.43', volume: '32' },
        { price: '1785.42', volume: '28' },
        { price: '1785.41', volume: '45' },
        { price: '1785.40', volume: '36' }
      ],
      asks: [
        { price: '1785.45', volume: '42' },
        { price: '1785.46', volume: '31' },
        { price: '1785.47', volume: '25' },
        { price: '1785.48', volume: '38' },
        { price: '1785.49', volume: '29' }
      ],
      financialData: [
        { item: '营业收入', value: '1275.54亿', change: '+16.53%' },
        { item: '净利润', value: '627.16亿', change: '+19.42%' },
        { item: '每股收益', value: '49.93元', change: '+19.42%' },
        { item: '毛利率', value: '91.62%', change: '+0.85%' },
        { item: '净资产收益率', value: '31.41%', change: '+1.26%' }
      ],
      news: [
        { id: 1, title: '贵州茅台2023年净利润同比增长19.42%，超市场预期', time: '2023-08-10 09:30', source: '证券时报' },
        { id: 2, title: '茅台集团与华为达成战略合作，共建智慧酒业', time: '2023-08-09 14:25', source: '财经网' },
        { id: 3, title: '北向资金连续5日增持贵州茅台，累计净买入超20亿元', time: '2023-08-08 18:40', source: '东方财富' },
        { id: 4, title: '贵州茅台拟10派192.93元，分红总额超240亿元', time: '2023-08-07 10:15', source: '中国证券报' }
      ],
      chart: null
    };
  },
  mounted() {
    this.initChart();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    if (this.chart) {
      this.chart.dispose();
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
        message: this.isFavorite ? '已加入自选股' : '已移除自选股',
        type: 'success'
      });
    },
    initChart() {
      const chartDom = document.getElementById('stockChart');
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
          type: 'candlestick',
          data: [
            [1770, 1780, 1765, 1775],
            [1775, 1785, 1772, 1782],
            [1782, 1788, 1778, 1785],
            [1785, 1790, 1782, 1783],
            [1783, 1786, 1778, 1780],
            [1780, 1788, 1775, 1785],
            [1785, 1790, 1780, 1788],
            [1788, 1792, 1785, 1787],
            [1787, 1789, 1780, 1782],
            [1782, 1785, 1778, 1785]
          ],
          itemStyle: {
            color: $stock-up-color,
            color0: $stock-down-color,
            borderColor: $stock-up-color,
            borderColor0: $stock-down-color
          }
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
    handleResize() {
      if (this.chart) {
        this.chart.resize();
      }
    }
  }
};
</script>

<style scoped lang="scss">
/* 引入全局主题变量和混入 */
@use '@/assets/scss/mixins' as mixin;
@use 'sass:map';
@use 'sass:color';

.stock-detail {
  padding: $content-padding;
  background-color: $primary-bg;
  color: $text-primary;
  height: 100%;
  overflow-y: auto;

  /* 应用主题过渡动画 */
  @extend .theme-transition;
}

/* 股票头部信息区域 */
.stock-header {
  display: flex;
  align-items: center;
  padding-bottom: map.get($spacers, 4);
  border-bottom: $border-width solid $border-color;
  margin-bottom: map.get($spacers, 4);

  /* 应用卡片基础样式 */
  @include mixin.card-base(false);
  padding: map.get($spacers, 3);
}

.stock-info {
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
.stock-content {
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

#stockChart {
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

.stock-tabs {
  /* 应用卡片基础样式 */
  @include mixin.card-base;
  border-radius: $border-radius-lg;
  overflow: hidden;
}

/* 盘口数据样式 */
.quota-data {
  padding: map.get($spacers, 4);
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

/* 买卖五档样式 */
.order-book {
  padding: 0 map.get($spacers, 4) map.get($spacers, 4);
}

.order-book h3 {
  margin-top: 0;
  padding-bottom: map.get($spacers, 2);
  border-bottom: $border-width solid $border-color;
  color: $text-primary;
  font-weight: $font-weight-semibold;
}

.order-table {
  display: flex;
  flex-direction: column;
}

.order-row {
  display: flex;
  padding: map.get($spacers, 2) 0;

  /* 应用主题过渡 */
  @extend .theme-transition;
}

.order-type {
  width: 50px;
  text-align: center;
  font-weight: $font-weight-semibold;
}

/* 买卖类型颜色 */
.buy {
  color: $stock-up-color;
}

.sell {
  color: $stock-down-color;
}

.order-price {
  flex: 1;
  text-align: right;
  padding-right: map.get($spacers, 3);
  color: $text-primary;
}

.order-volume {
  width: 80px;
  text-align: right;
  color: $text-secondary;
}

.divider {
  height: $border-width;
  background: $border-color;
  margin: map.get($spacers, 2) 0;
}

/* 财务数据样式 */
.financial-data {
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
  .stock-header {
    flex-direction: column;
    align-items: flex-start;
    gap: map.get($spacers, 3);
  }

  .stock-info {
    padding: 0;
    width: 100%;
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
  .stock-detail {
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