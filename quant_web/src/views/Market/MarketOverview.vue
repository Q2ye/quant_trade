<!--MarketOverview.vue-->
<!--已完成Naive UI迁移的市场概览页面 - 基于交易系统主题实现-->
<template>
  <div class="market-overview-page">
    <!-- 页面标题和状态 -->
    <div class="common-page-header">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">市场概览</h1>
          <p class="page-description">实时监控市场指数、资金流向和热点板块，掌握市场动态</p>
        </div>
        <div class="header-actions">
          <n-button class="refresh-btn" @click="refreshData">
            <template #icon>
              <SmartIcon name="Refresh" />
            </template>
            <span class="btn-text">刷新数据</span>
          </n-button>
        </div>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 市场指数概览 -->
      <div class="index-overview">
        <h2 class="market-section-title">
          <SmartIcon name="TrendingUp" class="title-icon" />
          主要指数
        </h2>
        <div class="market-index-grid">
          <!-- 上证指数卡片 -->
          <n-card class="market-index-card" hoverable>
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">上证指数</div>
                <div class="index-code">000001</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.shanghai)">
                  <SmartIcon name="TrendingUp" />
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.shanghai.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.shanghai)">
                    <span class="change-value">{{ formatChange(indexData.shanghai.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.shanghai.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </n-card>

          <!-- 深证成指卡片 -->
          <n-card class="market-index-card" hoverable>
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">深证成指</div>
                <div class="index-code">399001</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.shenzhen)">
                  <SmartIcon name="BarChart" />
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.shenzhen.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.shenzhen)">
                    <span class="change-value">{{ formatChange(indexData.shenzhen.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.shenzhen.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </n-card>

          <!-- 创业板指卡片 -->
          <n-card class="market-index-card" hoverable>
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">创业板指</div>
                <div class="index-code">399006</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.chuangye)">
                  <SmartIcon name="Rocket" />
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.chuangye.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.chuangye)">
                    <span class="change-value">{{ formatChange(indexData.chuangye.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.chuangye.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </n-card>

          <!-- 科创50卡片 -->
          <n-card class="market-index-card" hoverable>
            <div class="index-content">
              <div class="index-header">
                <div class="index-name">科创50</div>
                <div class="index-code">000688</div>
              </div>
              <div class="status-content">
                <div class="status-icon" :class="getStatusClass(indexData.kechuang50)">
                  <SmartIcon name="Chip" />
                </div>
                <div class="status-info">
                  <div class="index-value">{{ indexData.kechuang50.close.toFixed(2) }}</div>
                  <div class="index-change" :class="getChangeClass(indexData.kechuang50)">
                    <span class="change-value">{{ formatChange(indexData.kechuang50.change) }}</span>
                    <span class="change-percent">({{ formatPercent(indexData.kechuang50.pct_chg) }})</span>
                  </div>
                </div>
              </div>
            </div>
          </n-card>
        </div>
      </div>

      <!-- 功能导航卡片 -->
      <div class="function-nav">
        <h2 class="market-section-title">
          <SmartIcon name="Apps" class="title-icon" />
          功能导航
        </h2>

        <div class="function-grid">
          <!-- 市场仪表盘 -->
          <n-card class="function-nav-card" hoverable @click="goToDashboard">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon accent">
                  <SmartIcon name="Dashboard" />
                </div>
                <h3 class="function-title">市场仪表盘</h3>
              </div>
              <div class="function-info">
                <p class="function-description">股票/ETF/指数一站式分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">股票:</span>
                    <span class="stat-value">{{ dashboardStats.stocks }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">ETF:</span>
                    <span class="stat-value">{{ dashboardStats.etfs }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">指数:</span>
                    <span class="stat-value">{{ dashboardStats.indexes }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">统一视图分析</span>
                </div>
              </div>
            </div>
          </n-card>

          <!-- 行业强弱 -->
          <n-card class="function-nav-card" hoverable @click="navigateTo('/market/industry-strength')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon purple">
                  <SmartIcon name="TreeChart" />
                </div>
                <h3 class="function-title">行业强弱</h3>
              </div>
              <div class="function-info">
                <p class="function-description">行业强弱与趋势分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">领涨行业:</span>
                    <span class="stat-value up">{{ industryStats.topIndustry.name }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">涨幅:</span>
                    <span class="stat-value up">{{ industryStats.topIndustry.change }}%</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">领跌行业:</span>
                    <span class="stat-value down">{{ industryStats.bottomIndustry.name }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">{{ industryStats.riseCount }}/{{ industryStats.totalCount }}行业上涨</span>
                </div>
              </div>
            </div>
          </n-card>

          <!-- 资金流向 -->
          <n-card class="function-nav-card" hoverable @click="navigateTo('/market/money-flow')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon info">
                  <SmartIcon name="CashMultiple" />
                </div>
                <h3 class="function-title">资金流向</h3>
              </div>
              <div class="function-info">
                <p class="function-description">主力资金流向分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">主力净流入:</span>
                    <span class="stat-value up">{{ formatAmount(moneyFlowStats.mainNetInflow) }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">北向资金:</span>
                    <span class="stat-value" :class="getFlowClass(moneyFlowStats.northbound)">
                      {{ formatAmount(moneyFlowStats.northbound, true) }}
                    </span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">成交额:</span>
                    <span class="stat-value">{{ formatAmount(moneyFlowStats.turnover) }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">更新: {{ moneyFlowStats.updateTime }}</span>
                </div>
              </div>
            </div>
          </n-card>

          <!-- 涨跌停分析 -->
          <n-card class="function-nav-card" hoverable @click="navigateTo('/market/limit-analysis')">
            <div class="function-content">
              <div class="function-header">
                <div class="function-icon danger">
                  <SmartIcon name="TrendingUp" />
                </div>
                <h3 class="function-title">涨跌停分析</h3>
              </div>
              <div class="function-info">
                <p class="function-description">涨跌停股票统计分析</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">涨停:</span>
                    <span class="stat-value up">{{ limitStats.upLimitCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">跌停:</span>
                    <span class="stat-value down">{{ limitStats.downLimitCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">炸板率:</span>
                    <span class="stat-value">{{ limitStats.explosionRate }}%</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">连板高度: {{ limitStats.maxConsecutive }}板</span>
                </div>
              </div>
            </div>
          </n-card>
        </div>
      </div>

      <!-- 市场热点与实时数据 -->
      <div class="market-hotspots">
        <h2 class="market-section-title">
          <SmartIcon name="Fire" class="title-icon" />
          市场热点
        </h2>
        <div class="hotspot-grid">
          <!-- 实时涨幅榜卡片 -->
          <n-card class="hotspot-card" :bordered="false">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <SmartIcon name="TrendingUp" class="card-title-icon" />
                  实时涨幅榜
                </div>
                <n-button text class="more-btn" @click="navigateTo('/market/stocks')">
                  查看更多
                  <template #icon>
                    <SmartIcon name="ArrowRight" />
                  </template>
                </n-button>
              </div>
            </template>
            <div class="hotspot-list">
              <div
                  v-for="stock in topRisingStocks"
                  :key="stock.code"
                  class="hotspot-item"
                  @click="viewStockDetail(stock)"
              >
                <div class="item-icon">
                  <SmartIcon name="TrendingUp" class="trend-icon up" />
                </div>
                <div class="stock-info">
                  <div class="stock-name">{{ stock.name }}</div>
                  <div class="stock-code">{{ stock.code }}</div>
                </div>
                <div class="hotspot-change up">
                  +{{ stock.change.toFixed(2) }}%
                </div>
                <div class="hotspot-price flat">
                  ¥{{ stock.price.toFixed(2) }}
                </div>
              </div>
            </div>
          </n-card>

          <!-- 资金流入榜卡片 -->
          <n-card class="hotspot-card" :bordered="false">
            <template #header>
              <div class="card-header">
                <div class="card-title">
                  <SmartIcon name="CashPlus" class="card-title-icon" />
                  资金流入榜
                </div>
                <n-button text class="more-btn" @click="navigateTo('/market/money-flow')">
                  查看更多
                  <template #icon>
                    <SmartIcon name="ArrowRight" />
                  </template>
                </n-button>
              </div>
            </template>
            <div class="money-flow-list">
              <div
                  v-for="flow in topMoneyFlow"
                  :key="flow.code"
                  class="flow-item"
                  @click="viewStockDetail(flow)"
              >
                <div class="item-icon">
                  <SmartIcon name="CashPlus" class="flow-icon up" />
                </div>
                <div class="stock-info">
                  <div class="stock-name">{{ flow.name }}</div>
                  <div class="stock-code">{{ flow.code }}</div>
                </div>
                <div class="flow-bar">
                  <n-progress
                      type="line"
                      :percentage="Math.min(flow.percentage, 100)"
                      :height="6"
                      :border-radius="3"
                      :show-indicator="false"
                      status="success"
                  />
                </div>
                <div class="flow-amount up">
                  +{{ formatAmount(flow.amount) }}
                </div>
              </div>
            </div>
          </n-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NProgress, useMessage } from 'naive-ui'
import SmartIcon from '@/components/common/SmartIcon.vue'

const router = useRouter()
const message = useMessage()

// 响应式数据
const indexData = ref({
  shanghai: { close: 3254.32, change: 12.45, pct_chg: 0.38 },
  shenzhen: { close: 11982.15, change: -23.67, pct_chg: -0.20 },
  chuangye: { close: 2572.89, change: 18.92, pct_chg: 0.74 },
  kechuang50: { close: 1056.78, change: 8.34, pct_chg: 0.79 }
})

// 行业强弱统计数据
const industryStats = ref({
  topIndustry: { name: '计算机', change: 3.2 },
  bottomIndustry: { name: '房地产', change: -2.1 },
  totalCount: 28,
  riseCount: 18
})

// 资金流向统计数据
const moneyFlowStats = ref({
  mainNetInflow: 1256700,
  northbound: 456700,
  turnover: 8456700,
  updateTime: '15:00'
})

// 涨跌停分析统计数据
const limitStats = ref({
  upLimitCount: 45,
  downLimitCount: 12,
  explosionRate: 23.4,
  maxConsecutive: 7
})

// 实时涨幅榜数据
const topRisingStocks = ref([
  { code: '300624', name: '万兴科技', change: 10.02, price: 156.78 },
  { code: '002230', name: '科大讯飞', change: 9.98, price: 67.45 },
  { code: '300059', name: '东方财富', change: 8.76, price: 23.89 },
  { code: '600570', name: '恒生电子', change: 7.45, price: 45.67 },
  { code: '000977', name: '浪潮信息', change: 6.89, price: 56.78 }
])

// 资金流入榜数据
const topMoneyFlow = ref([
  { code: '300750', name: '宁德时代', amount: 125670, percentage: 85 },
  { code: '000858', name: '五粮液', amount: 89234, percentage: 72 },
  { code: '600519', name: '贵州茅台', amount: 78456, percentage: 68 },
  { code: '002594', name: '比亚迪', amount: 67345, percentage: 65 },
  { code: '601888', name: '中国中免', amount: 56789, percentage: 58 }
])

// 仪表盘统计数据
const dashboardStats = ref({
  stocks: 4856,
  etfs: 589,
  indexes: 234
})

// 方法
const navigateTo = (path: string) => {
  router.push(path)
}

const goToDashboard = () => {
  router.push('/market/mkDashboard')
}

const viewStockDetail = (stock: any) => {
  router.push(`/market/stock/${stock.code}`)
}

const getChangeClass = (data: any) => {
  if (data.change > 0) return 'up'
  if (data.change < 0) return 'down'
  return 'flat'
}

const getStatusClass = (data: any) => {
  if (data.change > 0) return 'running'
  if (data.change < 0) return 'remaining'
  return 'time'
}

const getFlowClass = (value: number) => {
  return value >= 0 ? 'up' : 'down'
}

const formatChange = (change: number | null | undefined) => {
  if (change === null || change === undefined) return '-'
  const sign = change > 0 ? '+' : ''
  return sign + change.toFixed(2)
}

const formatPercent = (pct: number | null | undefined) => {
  if (pct === null || pct === undefined) return '-'
  const sign = pct > 0 ? '+' : ''
  return sign + pct.toFixed(2) + '%'
}

const formatAmount = (amount: number | null | undefined, showSign: boolean = false) => {
  if (amount === null || amount === undefined) return '-'
  const absAmount = Math.abs(amount)
  const sign = showSign ? (amount > 0 ? '+' : amount < 0 ? '-' : '') : ''

  if (absAmount >= 100000000) {
    return sign + (absAmount / 100000000).toFixed(2) + '亿'
  } else if (absAmount >= 10000) {
    return sign + (absAmount / 10000).toFixed(2) + '万'
  } else {
    return sign + absAmount.toFixed(2)
  }
}

// 刷新数据方法
const refreshData = () => {
  simulateDataUpdate()
  message.success('数据已刷新')
}

// 模拟数据更新
const simulateDataUpdate = () => {
  Object.keys(indexData.value).forEach(key => {
    const item = (indexData.value as any)[key]
    const change = (Math.random() - 0.45) * 5
    item.close = parseFloat((item.close + change).toFixed(2))
    item.change = parseFloat(change.toFixed(2))
    item.pct_chg = parseFloat(((change / item.close) * 100).toFixed(2))
  })

  const now = new Date()
  moneyFlowStats.value.updateTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
}

// 生命周期钩子
onMounted(() => {
  refreshData()
})
</script>

<style lang="scss" scoped>
// 引入变量和混入文件
@use '@/assets/scss/variables' as *;
@use '@/assets/scss/mixins' as *;

.market-overview-page {
  // 页面基础布局
  background-color: $body-color;
  min-height: calc(100vh - var(--header-height));
  padding: spacer(4);

  // 移动端适配
  @include media-breakpoint-down(sm) {
    padding: spacer(2);
  }

  .common-page-header {
    @include page-header-base;
  }

  .main-content {
    display: flex;
    flex-direction: column;
    gap: spacer(6);
  }

  // 市场指数概览
  .index-overview {
    @include content-area;

    .market-section-title {
      @include card-title-base;
      margin-bottom: spacer(4);

      .title-icon {
        font-size: 1.25rem;
        color: $primary-color;
      }
    }

    .market-index-grid {
      @include flexible-grid(4, (
        lg: 2,
        md: 2,
        sm: 1
      ));
      margin-bottom: spacer(6);

      .market-index-card {
        @include card-base;
        height: 100%;
        border: 1px solid $border-color;
        transition: all var(--transition-normal);
        cursor: pointer;

        &:hover {
          @include box-shadow('2');
          transform: translateY(-2px);
          border-color: $primary-color;
        }

        .index-content {
          padding: spacer(3);

          .index-header {
            @include flex-layout-between;
            margin-bottom: spacer(3);

            .index-name {
              font-size: 0.875rem;
              font-weight: 500;
              color: $text-color-1;
            }

            .index-code {
              font-size: 0.75rem;
              color: $text-color-3;
              background: $secondary-bg;
              padding: spacer(0.5) spacer(1.5);
              border-radius: $border-radius-small;
            }
          }

          .status-content {
            display: flex;
            align-items: center;
            gap: spacer(3);

            .status-icon {
              @include icon-container('md', 'primary');

              &.running {
                background: color-with-opacity($stock-up-color, 0.1);
                color: $stock-up-color;
              }

              &.remaining {
                background: color-with-opacity($stock-down-color, 0.1);
                color: $stock-down-color;
              }

              &.time {
                background: color-with-opacity($stock-flat-color, 0.1);
                color: $stock-flat-color;
              }

              :deep(svg) {
                width: 1.25rem;
                height: 1.25rem;
              }
            }

            .status-info {
              flex: 1;

              .index-value {
                font-size: 1.5rem;
                font-weight: 600;
                color: $text-color-1;
                margin-bottom: spacer(0.5);
              }

              .index-change {
                font-size: 0.875rem;
                font-weight: 500;

                &.up {
                  color: $stock-up-color;
                }

                &.down {
                  color: $stock-down-color;
                }

                &.flat {
                  color: $stock-flat-color;
                }

                .change-value {
                  margin-right: spacer(0.5);
                }

                .change-percent {
                  font-size: 0.8125rem;
                }
              }
            }
          }
        }
      }
    }
  }

  // 功能导航
  .function-nav {
    @include content-area;

    .market-section-title {
      @include card-title-base;
      margin-bottom: spacer(4);

      .title-icon {
        font-size: 1.25rem;
        color: $purple-color;
      }
    }

    .function-grid {
      @include card-grid;

      .function-nav-card {
        @include function-card;

        .function-content {
          .function-header {
            margin-bottom: spacer(3);

            .function-icon {
              @include icon-container('md', 'primary');

              &.accent {
                @include icon-container('md', 'primary');
              }

              &.purple {
                @include icon-container('md', 'purple');
              }

              &.info {
                @include icon-container('md', 'info');
              }

              &.danger {
                @include icon-container('md', 'error');
              }

              &.warning {
                @include icon-container('md', 'warning');
              }

              &.success {
                @include icon-container('md', 'success');
              }

              :deep(svg) {
                width: 1.25rem;
                height: 1.25rem;
              }
            }

            .function-title {
              font-size: 1rem;
              font-weight: 600;
              color: $text-color-1;
              margin: 0;
              margin-top: spacer(1);
            }
          }

          .function-info {
            .function-description {
              font-size: 0.875rem;
              color: $text-color-2;
              margin-bottom: spacer(3);
              line-height: 1.5;
            }

            .function-stats {
              margin-bottom: spacer(3);

              .stat-item {
                @include stat-item;

                .stat-label {
                  font-size: 0.8125rem;
                  color: $text-color-3;
                }

                .stat-value {
                  font-weight: 600;
                  color: $text-color-1;

                  &.up {
                    color: $stock-up-color;
                  }

                  &.down {
                    color: $stock-down-color;
                  }
                }
              }
            }

            .function-footer {
              font-size: 0.75rem;
              color: $text-color-3;
              padding-top: spacer(2);
              border-top: 1px solid $divider-color;

              .update-time {
                display: block;
              }
            }
          }
        }

        &:hover {
          .function-header {
            .function-icon {
              transform: scale(1.1);
            }
          }
        }
      }
    }
  }

  // 市场热点
  .market-hotspots {
    @include content-area;

    .market-section-title {
      @include card-title-base;
      margin-bottom: spacer(4);

      .title-icon {
        font-size: 1.25rem;
        color: $error-color;
      }
    }

    .hotspot-grid {
      @include grid-layout(2);

      @include media-breakpoint-down(lg) {
        grid-template-columns: 1fr;
        gap: spacer(4);
      }

      .hotspot-card {
        @include hotspot-card;

        .card-header {
          @include flex-layout-between;
          padding: 0;
          margin-bottom: spacer(3);

          .card-title {
            @include card-title-base;
            font-size: 1rem;

            .card-title-icon {
              font-size: 1rem;
              color: $primary-color;
            }
          }

          .more-btn {
            color: $text-color-2;
            font-size: 0.8125rem;

            &:hover {
              color: $primary-color;
            }
          }
        }

        .hotspot-list {
          .hotspot-item {
            @include hotspot-item;

            .item-icon {
              .trend-icon {
                font-size: 1rem;

                &.up {
                  color: $stock-up-color;
                }
              }
            }

            .stock-info {
              .stock-name {
                font-size: 0.875rem;
                font-weight: 500;
                color: $text-color-1;
                margin-bottom: spacer(0.5);
              }

              .stock-code {
                font-size: 0.75rem;
                color: $text-color-3;
              }
            }

            .hotspot-change {
              font-weight: 600;
              font-size: 0.875rem;

              &.up {
                color: $stock-up-color;
              }

              &.down {
                color: $stock-down-color;
              }

              &.flat {
                color: $stock-flat-color;
              }
            }

            .hotspot-price {
              font-weight: 500;
              font-size: 0.875rem;
              color: $text-color-1;
              margin-left: auto;
              min-width: 80px;
              text-align: right;
            }
          }
        }

        .money-flow-list {
          .flow-item {
            @include money-flow-item;

            .item-icon {
              .flow-icon {
                font-size: 1rem;

                &.up {
                  color: $stock-up-color;
                }

                &.down {
                  color: $stock-down-color;
                }
              }
            }

            .stock-info {
              .stock-name {
                font-size: 0.875rem;
                font-weight: 500;
                color: $text-color-1;
                margin-bottom: spacer(0.5);
              }

              .stock-code {
                font-size: 0.75rem;
                color: $text-color-3;
              }
            }

            .flow-bar {
              flex: 1;
              max-width: 120px;
            }

            .flow-amount {
              font-weight: 600;
              font-size: 0.875rem;
              min-width: 80px;
              text-align: right;

              &.up {
                color: $stock-up-color;
              }

              &.down {
                color: $stock-down-color;
              }
            }
          }
        }
      }
    }
  }

  // 响应式调整
  @include media-breakpoint-down(lg) {
    .market-index-grid {
      grid-template-columns: repeat(2, 1fr) !important;
    }

    .function-grid {
      grid-template-columns: repeat(2, 1fr) !important;
    }
  }

  @include media-breakpoint-down(md) {
    .market-index-grid {
      grid-template-columns: 1fr !important;
    }

    .function-grid {
      grid-template-columns: 1fr !important;
    }

    .common-page-header {
      .header-content {
        flex-direction: column;
        align-items: flex-start;
        gap: spacer(3);

        .header-actions {
          width: 100%;
          justify-content: flex-start;
        }
      }
    }
  }

  @include media-breakpoint-down(sm) {
    .market-index-card {
      .index-content {
        .status-content {
          flex-direction: column;
          align-items: flex-start;
          gap: spacer(2) !important;

          .status-info {
            width: 100%;
          }
        }
      }
    }
  }
}

// 状态颜色辅助类
.status-up { color: $stock-up-color !important; }
.status-down { color: $stock-down-color !important; }
.status-neutral { color: $stock-flat-color !important; }

.bg-up { background-color: color-with-opacity($stock-up-color, 0.1) !important; }
.bg-down { background-color: color-with-opacity($stock-down-color, 0.1) !important; }
.bg-neutral { background-color: color-with-opacity($stock-flat-color, 0.1) !important; }

// 动画效果
.fade-in {
  @include fade-in;
}

.spin {
  @include loading-spinner;
}

// 自定义滚动条
.market-overview-page {
  .hotspot-list,
  .money-flow-list {
    max-height: 300px;
    overflow-y: auto;
    @include custom-scrollbar;
  }
}

// Vue深度选择器（用于修改Naive UI组件内部样式）
:deep(.n-card) {
  &.market-index-card,
  &.function-nav-card,
  &.hotspot-card {
    .n-card__content {
      padding: 0;
    }
  }
}

:deep(.n-progress) {
  &.n-progress--line {
    .n-progress-content {
      .n-progress-graph {
        .n-progress-graph-line {
          .n-progress-graph-line-fill {
            transition: width var(--transition-normal);
          }
        }
      }
    }
  }
}

:deep(.n-button) {
  &.refresh-btn {
    .n-button__icon {
      margin-right: spacer(1);
    }
  }

  &.more-btn {
    .n-button__icon {
      margin-left: spacer(0.5);
    }
  }
}
</style>