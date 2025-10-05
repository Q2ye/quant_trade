<!--回测配置-->
<!--回测配置-->
<script>
export default {
  name: "BacktestConfig",
  data() {
    return {
      activeTab: 'basic',
      strategyOptions: [
        { id: 1, name: '双均线策略', type: '趋势跟踪', description: '基于短期和长期均线交叉进行交易' },
        { id: 2, name: 'RSI超买超卖', type: '反转策略', description: '在RSI指标超买超卖区域进行反向交易' },
        { id: 3, name: '布林带突破', type: '突破策略', description: '在价格突破布林带上下轨时进行交易' },
        { id: 4, name: 'MACD金叉死叉', type: '趋势跟踪', description: '基于MACD指标的金叉和死叉信号进行交易' }
      ],
      selectedStrategy: null,
      stockPool: [],
      stockOptions: [
        { code: '600519', name: '贵州茅台' },
        { code: '000858', name: '五粮液' },
        { code: '601318', name: '中国平安' },
        { code: '600036', name: '招商银行' },
        { code: '000333', name: '美的集团' },
        { code: '000651', name: '格力电器' },
        { code: '600276', name: '恒瑞医药' },
        { code: '300059', name: '东方财富' }
      ],
      backtestSettings: {
        capital: 1000000,
        startDate: '2020-01-01',
        endDate: '2023-08-01',
        commission: 0.0003,
        slippage: 0.001,
        benchmark: '000300.SH'
      },
      strategyParams: {
        // 双均线策略参数
        fastPeriod: 5,
        slowPeriod: 20,

        // RSI策略参数
        rsiPeriod: 14,
        overbought: 70,
        oversold: 30,

        // 布林带策略参数
        bbPeriod: 20,
        bbStdDev: 2,

        // MACD策略参数
        macdFast: 12,
        macdSlow: 26,
        macdSignal: 9
      },
      benchmarkOptions: [
        { code: '000001.SH', name: '上证指数' },
        { code: '399001.SZ', name: '深证成指' },
        { code: '000300.SH', name: '沪深300' },
        { code: '000905.SH', name: '中证500' },
        { code: '399006.SZ', name: '创业板指' }
      ],
      paramGroups: {
        trend: [
          { name: 'fastPeriod', label: '快线周期', min: 1, max: 20, step: 1 },
          { name: 'slowPeriod', label: '慢线周期', min: 10, max: 60, step: 1 }
        ],
        reversal: [
          { name: 'rsiPeriod', label: 'RSI周期', min: 5, max: 30, step: 1 },
          { name: 'overbought', label: '超买阈值', min: 60, max: 90, step: 1 },
          { name: 'oversold', label: '超卖阈值', min: 10, max: 40, step: 1 }
        ],
        breakout: [
          { name: 'bbPeriod', label: '布林带周期', min: 10, max: 30, step: 1 },
          { name: 'bbStdDev', label: '标准差倍数', min: 1.5, max: 3, step: 0.1 }
        ],
        macd: [
          { name: 'macdFast', label: '快线周期', min: 5, max: 20, step: 1 },
          { name: 'macdSlow', label: '慢线周期', min: 20, max: 50, step: 1 },
          { name: 'macdSignal', label: '信号周期', min: 5, max: 20, step: 1 }
        ]
      }
    };
  },
  computed: {
    currentParams() {
      if (!this.selectedStrategy) return [];

      switch (this.selectedStrategy.type) {
        case '趋势跟踪': return this.paramGroups.trend;
        case '反转策略': return this.paramGroups.reversal;
        case '突破策略': return this.paramGroups.breakout;
        case 'MACD策略': return this.paramGroups.macd;
        default: return [];
      }
    }
  },
  methods: {
    selectStrategy(strategy) {
      this.selectedStrategy = strategy;
    },
    runBacktest() {
      if (!this.selectedStrategy) {
        this.$message.warning('请选择一个策略');
        return;
      }

      if (this.stockPool.length === 0) {
        this.$message.warning('请添加至少一个股票到股票池');
        return;
      }

      this.$message.success('回测已启动，请查看回测报告');
      // 这里实际会调用API启动回测
    },
    optimizeParams() {
      this.$message.info('参数优化已启动，请稍后查看结果');
      // 这里实际会调用参数优化API
    }
  }
};
</script>

<template>
  <div class="backtest-config">
    <div class="config-header">
      <h2>策略回测配置</h2>
      <div class="header-actions">
        <el-button type="primary" icon="el-icon-video-play" @click="runBacktest">启动回测</el-button>
        <el-button type="success" icon="el-icon-magic-stick" @click="optimizeParams">参数优化</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="config-tabs">
      <!-- 基本配置标签页 -->
      <el-tab-pane label="基本配置" name="basic">
        <div class="config-section">
          <h3>策略选择</h3>
          <div class="strategy-grid">
            <div
              v-for="strategy in strategyOptions"
              :key="strategy.id"
              class="strategy-card"
              :class="{ 'selected': selectedStrategy?.id === strategy.id }"
              @click="selectStrategy(strategy)"
            >
              <div class="strategy-name">{{ strategy.name }}</div>
              <div class="strategy-type">{{ strategy.type }}</div>
              <div class="strategy-desc">{{ strategy.description }}</div>
            </div>
          </div>

          <div v-if="selectedStrategy" class="selected-strategy">
            <h4>已选策略: {{ selectedStrategy.name }}</h4>
            <p>{{ selectedStrategy.description }}</p>
          </div>
        </div>

        <div class="config-section">
          <h3>股票池</h3>
          <div class="stock-pool">
            <div class="stock-selector">
              <el-select
                v-model="stockPool"
                multiple
                filterable
                placeholder="添加股票到回测池"
                style="width: 100%"
              >
                <el-option
                  v-for="stock in stockOptions"
                  :key="stock.code"
                  :label="`${stock.name} (${stock.code})`"
                  :value="stock.code"
                >
                  <span style="float: left">{{ stock.name }}</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">{{ stock.code }}</span>
                </el-option>
              </el-select>
            </div>

            <div class="selected-stocks">
              <el-tag
                v-for="stockCode in stockPool"
                :key="stockCode"
                closable
                @close="stockPool = stockPool.filter(code => code !== stockCode)"
              >
                {{ stockOptions.find(s => s.code === stockCode)?.name }} ({{ stockCode }})
              </el-tag>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 参数配置标签页 -->
      <el-tab-pane label="参数配置" name="params">
        <div class="param-config" v-if="selectedStrategy">
          <h3>{{ selectedStrategy.name }} 参数配置</h3>
          <div class="param-grid">
            <div v-for="param in currentParams" :key="param.name" class="param-item">
              <div class="param-info">
                <div class="param-label">{{ param.label }}</div>
                <div class="param-value">{{ strategyParams[param.name] }}</div>
              </div>
              <div class="param-slider">
                <el-slider
                  v-model="strategyParams[param.name]"
                  :min="param.min"
                  :max="param.max"
                  :step="param.step"
                  show-input
                ></el-slider>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="no-strategy">
          <el-alert title="请先选择策略" type="warning" show-icon>
            请在"基本配置"标签页选择一个策略进行参数配置
          </el-alert>
        </div>
      </el-tab-pane>

      <!-- 回测设置标签页 -->
      <el-tab-pane label="回测设置" name="settings">
        <div class="settings-form">
          <el-form :model="backtestSettings" label-width="120px">
            <el-form-item label="初始资金">
              <el-input-number
                v-model="backtestSettings.capital"
                :min="10000"
                :max="10000000"
                :step="10000"
                controls-position="right"
              ></el-input-number>
              <span class="unit">元</span>
            </el-form-item>

            <el-form-item label="回测周期">
              <el-date-picker
                v-model="backtestSettings.startDate"
                type="date"
                placeholder="开始日期"
                value-format="yyyy-MM-dd"
              ></el-date-picker>
              <span class="date-separator">至</span>
              <el-date-picker
                v-model="backtestSettings.endDate"
                type="date"
                placeholder="结束日期"
                value-format="yyyy-MM-dd"
              ></el-date-picker>
            </el-form-item>

            <el-form-item label="佣金费率">
              <el-slider
                v-model="backtestSettings.commission"
                :min="0"
                :max="0.005"
                :step="0.0001"
                show-input
                input-size="small"
              ></el-slider>
              <span class="unit">%</span>
            </el-form-item>

            <el-form-item label="滑点设置">
              <el-slider
                v-model="backtestSettings.slippage"
                :min="0"
                :max="0.02"
                :step="0.0005"
                show-input
                input-size="small"
              ></el-slider>
              <span class="unit">%</span>
            </el-form-item>

            <el-form-item label="基准指数">
              <el-select v-model="backtestSettings.benchmark">
                <el-option
                  v-for="index in benchmarkOptions"
                  :key="index.code"
                  :label="index.name"
                  :value="index.code"
                >
                  {{ index.name }} ({{ index.code }})
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item label="交易限制">
              <el-checkbox-group v-model="tradeRestrictions">
                <el-checkbox label="禁止T+0" name="type"></el-checkbox>
                <el-checkbox label="禁止做空" name="type"></el-checkbox>
                <el-checkbox label="禁止交易ST股" name="type"></el-checkbox>
                <el-checkbox label="禁止交易涨停股" name="type"></el-checkbox>
              </el-checkbox-group>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.backtest-config {
  padding: 20px;
  background-color: #121a29;
  color: #e0e0e0;
  height: 100%;
  overflow-y: auto;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
  padding-bottom: 15px;
  border-bottom: 1px solid #2a3a5a;
}

.config-header h2 {
  margin: 0;
  color: #64b5f6;
}

.config-tabs {
  background: #1a2439;
  border-radius: 8px;
  overflow: hidden;
}

.config-section {
  background: #152136;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.config-section h3 {
  margin-top: 0;
  margin-bottom: 20px;
  color: #64b5f6;
}

.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.strategy-card {
  background: #1a2439;
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid #2a3a5a;
}

.strategy-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  border-color: #3a6bc5;
}

.strategy-card.selected {
  background: rgba(25, 55, 100, 0.7);
  border-color: #3a6bc5;
}

.strategy-name {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 5px;
  color: #e0e0e0;
}

.strategy-type {
  font-size: 14px;
  color: #ff9800;
  margin-bottom: 10px;
}

.strategy-desc {
  font-size: 13px;
  color: #9da8b8;
  line-height: 1.5;
}

.selected-strategy {
  background: rgba(25, 55, 100, 0.5);
  border-left: 4px solid #3a6bc5;
  padding: 15px;
  border-radius: 4px;
}

.selected-strategy h4 {
  margin-top: 0;
  color: #64b5f6;
}

.stock-pool {
  background: #1a2439;
  border-radius: 8px;
  padding: 20px;
}

.stock-selector {
  margin-bottom: 15px;
}

.selected-stocks {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  min-height: 40px;
}

.param-config {
  background: #152136;
  border-radius: 8px;
  padding: 20px;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.param-item {
  background: #1a2439;
  border-radius: 8px;
  padding: 15px;
}

.param-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.param-label {
  font-weight: bold;
}

.param-value {
  color: #ff9800;
  font-weight: bold;
}

.settings-form {
  background: #152136;
  border-radius: 8px;
  padding: 20px;
}

.unit {
  margin-left: 10px;
  color: #9da8b8;
}

.date-separator {
  margin: 0 15px;
  color: #9da8b8;
}

.no-strategy {
  background: #152136;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}

:deep(.el-tabs__item) {
  color: #9da8b8;
}

:deep(.el-tabs__item.is-active) {
  color: #64b5f6;
}

:deep(.el-tabs__active-bar) {
  background: #64b5f6;
}

:deep(.el-tabs__nav-wrap::after) {
  background: #2a3a5a;
}

:deep(.el-select-dropdown) {
  background: #1a2439;
  border: 1px solid #2a3a5a;
}

:deep(.el-select-dropdown__item) {
  color: #e0e0e0;
}

:deep(.el-select-dropdown__item.hover),
:deep(.el-select-dropdown__item:hover) {
  background: #2a3a5a;
}

:deep(.el-input__inner) {
  background: #1a2439;
  border: 1px solid #2a3a5a;
  color: #e0e0e0;
}

:deep(.el-input-number__decrease),
:deep(.el-input-number__increase) {
  background: #2a3a5a;
  color: #e0e0e0;
}

:deep(.el-slider__runway) {
  background: #2a3a5a;
}

:deep(.el-slider__bar) {
  background: #3a6bc5;
}

:deep(.el-slider__button) {
  border: 2px solid #3a6bc5;
}

:deep(.el-checkbox__label) {
  color: #e0e0e0;
}
</style>