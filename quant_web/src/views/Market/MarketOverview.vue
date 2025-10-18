<template>
  <div class="market-overview">
    <!-- 市场指数概览 -->
    <div class="index-overview">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-card class="index-card" shadow="hover">
            <div class="index-content">
              <div class="index-info">
                <div class="index-name">上证指数</div>
                <div class="index-code">000001.SH</div>
              </div>
              <div class="index-value">
                <div class="current-price">{{ indexData.shanghai.close.toFixed(2) }}</div>
                <div class="index-change" :class="getChangeClass(indexData.shanghai)">
                  {{ formatChange(indexData.shanghai.change) }}
                  ({{ formatPercent(indexData.shanghai.pct_chg) }})
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="index-card" shadow="hover">
            <div class="index-content">
              <div class="index-info">
                <div class="index-name">深证成指</div>
                <div class="index-code">399001.SZ</div>
              </div>
              <div class="index-value">
                <div class="current-price">{{ indexData.shenzhen.close.toFixed(2) }}</div>
                <div class="index-change" :class="getChangeClass(indexData.shenzhen)">
                  {{ formatChange(indexData.shenzhen.change) }}
                  ({{ formatPercent(indexData.shenzhen.pct_chg) }})
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="index-card" shadow="hover">
            <div class="index-content">
              <div class="index-info">
                <div class="index-name">创业板指</div>
                <div class="index-code">399006.SZ</div>
              </div>
              <div class="index-value">
                <div class="current-price">{{ indexData.chuangye.close.toFixed(2) }}</div>
                <div class="index-change" :class="getChangeClass(indexData.chuangye)">
                  {{ formatChange(indexData.chuangye.change) }}
                  ({{ formatPercent(indexData.chuangye.pct_chg) }})
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="index-card" shadow="hover">
            <div class="index-content">
              <div class="index-info">
                <div class="index-name">科创50</div>
                <div class="index-code">000688.SH</div>
              </div>
              <div class="index-value">
                <div class="current-price">{{ indexData.kechuang50.close.toFixed(2) }}</div>
                <div class="index-change" :class="getChangeClass(indexData.kechuang50)">
                  {{ formatChange(indexData.kechuang50.change) }}
                  ({{ formatPercent(indexData.kechuang50.pct_chg) }})
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 功能导航卡片 - 每行显示3个 -->
    <div class="function-nav">
      <el-row :gutter="16">
        <!-- 股票市场卡片 -->
        <el-col :span="8">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/market/stocks')">
            <div class="function-content">
              <div class="function-icon" style="color: #2196F3;">
                <Icon icon="mdi:chart-bar"/>
              </div>
              <div class="function-info">
                <h3>股票市场</h3>
                <p>A股全市场股票行情数据</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">上涨:</span>
                    <span class="stat-value up">{{ stockStats.riseCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">下跌:</span>
                    <span class="stat-value down">{{ stockStats.fallCount }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">平盘:</span>
                    <span class="stat-value">{{ stockStats.flatCount }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">更新: {{ stockStats.updateTime }}</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- ETF基金卡片 -->
        <el-col :span="8">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/market/etfs')">
            <div class="function-content">
              <div class="function-icon" style="color: #3FB950;">
                <Icon icon="mdi:finance"/>
              </div>
              <div class="function-info">
                <h3>ETF基金</h3>
                <p>交易所交易基金数据</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">股票ETF:</span>
                    <span class="stat-value">{{ etfStats.stockETF }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">债券ETF:</span>
                    <span class="stat-value">{{ etfStats.bondETF }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">商品ETF:</span>
                    <span class="stat-value">{{ etfStats.commodityETF }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">总规模: {{ etfStats.totalAmount }}亿</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 指数行情卡片 -->
        <el-col :span="8">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/market/indexes')">
            <div class="function-content">
              <div class="function-icon" style="color: #D29922;">
                <Icon icon="mdi:chart-timeline"/>
              </div>
              <div class="function-info">
                <h3>指数行情</h3>
                <p>主要市场指数表现</p>
                <div class="function-stats">
                  <div class="stat-item">
                    <span class="stat-label">宽基指数:</span>
                    <span class="stat-value">{{ indexStats.broadIndex }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">行业指数:</span>
                    <span class="stat-value">{{ indexStats.industryIndex }}</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-label">策略指数:</span>
                    <span class="stat-value">{{ indexStats.strategyIndex }}</span>
                  </div>
                </div>
                <div class="function-footer">
                  <span class="update-time">{{ indexStats.riseCount }}/{{ indexStats.totalCount }}上涨</span>
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-top: 16px;">
        <!-- 行业强弱卡片 -->
        <el-col :span="8">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/market/industry-strength')">
            <div class="function-content">
              <div class="function-icon" style="color: #8B949E;">
                <Icon icon="mdi:chart-tree"/>
              </div>
              <div class="function-info">
                <h3>行业强弱</h3>
                <p>行业强弱与趋势分析</p>
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
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 资金流向卡片 -->
        <el-col :span="8">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/market/money-flow')">
            <div class="function-content">
              <div class="function-icon" style="color: #8b5cf6;">
                <Icon icon="mdi:cash-multiple"/>
              </div>
              <div class="function-info">
                <h3>资金流向</h3>
                <p>主力资金流向分析</p>
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
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 涨跌停分析卡片 -->
        <el-col :span="8">
          <el-card class="function-card" shadow="hover" @click="navigateTo('/market/limit-analysis')">
            <div class="function-content">
              <div class="function-icon" style="color: #F85149;">
                <Icon icon="mdi:trending-up"/>
              </div>
              <div class="function-info">
                <h3>涨跌停分析</h3>
                <p>涨跌停股票统计分析</p>
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
                  <el-button type="primary" text size="small">查看详情</el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 市场热点与实时数据 -->
    <div class="market-hotspots">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-card class="hotspot-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="card-title">实时涨幅榜</span>
                <el-button type="text" @click="navigateTo('/market/stocks')">
                  查看更多
                </el-button>
              </div>
            </template>
            <div class="hotspot-list">
              <div
                  v-for="(stock, index) in topRisingStocks"
                  :key="stock.code"
                  class="hotspot-item"
                  @click="viewStockDetail(stock)"
              >
                <div class="hotspot-rank">{{ index + 1 }}</div>
                <div class="stock-info">
                  <div class="stock-name">{{ stock.name }}</div>
                  <div class="stock-code">{{ stock.code }}</div>
                </div>
                <div class="hotspot-change up">
                  +{{ stock.change.toFixed(2) }}%
                </div>
                <div class="hotspot-price">
                  ¥{{ stock.price.toFixed(2) }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="hotspot-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span class="card-title">资金流入榜</span>
                <el-button type="text" @click="navigateTo('/market/money-flow')">
                  查看更多
                </el-button>
              </div>
            </template>
            <div class="money-flow-list">
              <div
                  v-for="flow in topMoneyFlow"
                  :key="flow.code"
                  class="flow-item"
                  @click="viewStockDetail(flow)"
              >
                <div class="stock-info">
                  <div class="stock-name">{{ flow.name }}</div>
                  <div class="stock-code">{{ flow.code }}</div>
                </div>
                <div class="flow-bar">
                  <div
                      class="flow-progress inflow"
                      :style="{
                      width: Math.min(flow.percentage, 100) + '%',
                      backgroundColor: '#f56c6c'
                    }"
                  ></div>
                </div>
                <div class="flow-amount up">
                  +{{ formatAmount(flow.amount) }}
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import {onMounted, ref} from 'vue'
import {useRouter} from 'vue-router'
import {Icon} from '@iconify/vue'

const router = useRouter()

// 响应式数据
const indexData = ref({
  shanghai: {close: 3254.32, change: 12.45, pct_chg: 0.38},
  shenzhen: {close: 11982.15, change: -23.67, pct_chg: -0.20},
  chuangye: {close: 2572.89, change: 18.92, pct_chg: 0.74},
  kechuang50: {close: 1056.78, change: 8.34, pct_chg: 0.79}
})

// 股票市场统计数据
const stockStats = ref({
  totalCount: 4856,
  riseCount: 2345,
  fallCount: 1876,
  flatCount: 635,
  updateTime: '15:00'
})

// ETF基金统计数据
const etfStats = ref({
  stockETF: 456,
  bondETF: 89,
  commodityETF: 45,
  totalAmount: 15678.90
})

// 指数行情统计数据
const indexStats = ref({
  broadIndex: 45,
  industryIndex: 156,
  strategyIndex: 33,
  totalCount: 234,
  riseCount: 156
})

// 行业强弱统计数据
const industryStats = ref({
  topIndustry: {name: '计算机', change: 3.2},
  bottomIndustry: {name: '房地产', change: -2.1},
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
  {code: '300624', name: '万兴科技', change: 10.02, price: 156.78},
  {code: '002230', name: '科大讯飞', change: 9.98, price: 67.45},
  {code: '300059', name: '东方财富', change: 8.76, price: 23.89},
  {code: '600570', name: '恒生电子', change: 7.45, price: 45.67},
  {code: '000977', name: '浪潮信息', change: 6.89, price: 56.78}
])

// 资金流入榜数据
const topMoneyFlow = ref([
  {code: '300750', name: '宁德时代', amount: 125670, percentage: 85},
  {code: '000858', name: '五粮液', amount: 89234, percentage: 72},
  {code: '600519', name: '贵州茅台', amount: 78456, percentage: 68},
  {code: '002594', name: '比亚迪', amount: 67345, percentage: 65},
  {code: '601888', name: '中国中免', amount: 56789, percentage: 58}
])

// 方法
const navigateTo = (path) => {
  router.push(path)
}

const viewStockDetail = (stock) => {
  router.push(`/market/stock/${stock.code}`)
}

const getChangeClass = (data) => {
  if (data.change > 0) return 'price-up'
  if (data.change < 0) return 'price-down'
  return 'price-flat'
}

const getFlowClass = (value) => {
  return value >= 0 ? 'up' : 'down'
}

const formatChange = (change) => {
  if (change === null || change === undefined) return '-'
  const sign = change > 0 ? '+' : ''
  return sign + change.toFixed(2)
}

const formatPercent = (pct) => {
  if (pct === null || pct === undefined) return '-'
  const sign = pct > 0 ? '+' : ''
  return sign + pct.toFixed(2) + '%'
}

const formatAmount = (amount, showSign = false) => {
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

// 生命周期
onMounted(() => {
  // 可以在这里添加数据获取逻辑
})
</script>

<style lang="scss" scoped>
.market-overview {
  padding: var(--spacer-4);
  background: var(--primary-bg);
  min-height: 100%;

  .index-overview {
    margin-bottom: var(--spacer-4);

    .index-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);
      transition: all var(--transition-normal);

      &:hover {
        transform: var(--hover-transform);
        box-shadow: var(--hover-shadow);
        border-color: var(--accent-color);
      }

      .index-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--spacer-3);

        .index-info {
          .index-name {
            font-size: var(--font-size-base);
            font-weight: var(--font-weight-semibold);
            color: var(--text-primary);
            margin-bottom: var(--spacer-1);
          }

          .index-code {
            font-size: calc(var(--font-size-base) - 2px);
            color: var(--text-secondary);
          }
        }

        .index-value {
          text-align: right;

          .current-price {
            font-size: 1.5rem;
            font-weight: var(--font-weight-bold);
            color: var(--text-primary);
            margin-bottom: var(--spacer-1);
          }

          .index-change {
            font-size: calc(var(--font-size-base) - 2px);
            font-weight: var(--font-weight-semibold);

            &.price-up {
              color: #f56c6c;
            }

            &.price-down {
              color: #67c23a;
            }

            &.price-flat {
              color: var(--text-secondary);
            }
          }
        }
      }
    }
  }

  .function-nav {
    margin-bottom: var(--spacer-4);

    .function-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);
      cursor: pointer;
      transition: all var(--transition-normal);
      height: 100%;

      &:hover {
        transform: translateY(-4px);
        box-shadow: var(--hover-shadow);
        border-color: var(--accent-color);
      }

      .function-content {
        display: flex;
        align-items: flex-start;
        padding: var(--spacer-3);

        .function-icon {
          font-size: 2.5rem;
          margin-right: var(--spacer-3);
          opacity: 0.8;
          flex-shrink: 0;
        }

        .function-info {
          flex: 1;

          h3 {
            margin: 0 0 var(--spacer-2) 0;
            color: var(--text-primary);
            font-size: 1.125rem;
            font-weight: var(--font-weight-semibold);
          }

          p {
            margin: 0 0 var(--spacer-3) 0;
            color: var(--text-secondary);
            font-size: calc(var(--font-size-base) - 2px);
            line-height: var(--line-height-base);
          }

          .function-stats {
            display: flex;
            flex-direction: column;
            gap: var(--spacer-2);
            margin-bottom: var(--spacer-3);

            .stat-item {
              display: flex;
              justify-content: space-between;
              align-items: center;

              .stat-label {
                font-size: calc(var(--font-size-base) - 2px);
                color: var(--text-secondary);
              }

              .stat-value {
                font-size: calc(var(--font-size-base) - 1px);
                font-weight: var(--font-weight-semibold);
                color: var(--text-primary);

                &.up {
                  color: #f56c6c;
                }

                &.down {
                  color: #67c23a;
                }
              }
            }
          }

          .function-footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: var(--spacer-2);
            border-top: 1px solid var(--border-color);

            .update-time {
              font-size: calc(var(--font-size-base) - 4px);
              color: var(--text-secondary);
            }
          }
        }
      }
    }
  }

  .market-hotspots {
    .hotspot-card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: var(--border-radius);

      .card-header {
        margin: 0 0 var(--spacer-2) 0;
        color: var(--text-primary);
        font-size: 1.125rem;
        font-weight: var(--font-weight-semibold);
      }

      :deep(.el-card__header) {
        background: var(--secondary-bg);
        border-bottom: 1px solid var(--border-color);
        padding: var(--spacer-3);
      }

      :deep(.el-card__body) {
        padding: var(--spacer-3);
      }

      .hotspot-list, .money-flow-list {
        .hotspot-item, .flow-item {
          display: flex;
          align-items: center;
          padding: var(--spacer-2) 0;
          border-bottom: 1px solid var(--border-color);
          cursor: pointer;
          transition: background-color var(--transition-normal);

          &:hover {
            background-color: var(--hover-bg);
          }

          &:last-child {
            border-bottom: none;
          }

          .hotspot-rank {
            width: 30px;
            text-align: center;
            font-weight: var(--font-weight-semibold);
            color: var(--text-secondary);
          }

          .stock-info {
            flex: 1;
            margin: 0 var(--spacer-3);

            .stock-name {
              font-weight: var(--font-weight-medium);
              color: var(--text-primary);
              margin-bottom: 2px;
            }

            .stock-code {
              font-size: calc(var(--font-size-base) - 4px);
              color: var(--text-secondary);
            }
          }

          .hotspot-change {
            width: 80px;
            text-align: right;
            font-weight: var(--font-weight-semibold);
          }

          .hotspot-price {
            width: 80px;
            text-align: right;
            font-weight: var(--font-weight-medium);
            color: var(--text-primary);
          }

          .flow-bar {
            flex: 1;
            height: 8px;
            background: var(--border-color);
            border-radius: 4px;
            margin: 0 var(--spacer-3);
            overflow: hidden;

            .flow-progress {
              height: 100%;
              transition: width var(--transition-normal);
            }
          }

          .flow-amount {
            width: 100px;
            text-align: right;
            font-weight: var(--font-weight-semibold);
          }
        }
      }
    }
  }
}

// 响应式设计
@media (max-width: 1200px) {
  .function-nav .el-col {
    width: 50%;
  }
}

@media (max-width: 768px) {
  .market-overview {
    padding: var(--spacer-2);
  }

  .function-nav .el-col {
    width: 100%;
  }

  .function-card .function-content {
    flex-direction: column;
    text-align: center;

    .function-icon {
      margin-right: 0;
      margin-bottom: var(--spacer-2);
    }
  }

  .market-hotspots .el-col {
    width: 100%;
    margin-bottom: var(--spacer-3);
  }
}

// 修复指数卡片样式
.index-card {
  .index-content {
    min-height: 80px;
  }

  .current-price {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
  }

  .index-change {
    font-size: 0.875rem !important;
  }
}

// 确保颜色一致性
.price-up {
  color: #f56c6c !important;
}

.price-down {
  color: #67c23a !important;
}

.up {
  color: #f56c6c !important;
}

.down {
  color: #67c23a !important;
}
</style>