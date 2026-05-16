<!--策略模板选择器-->
<script>
export default {
  name: "StrategyTemplate",
  props: {
    category: {
      type: String,
      default: "all",
    },
  },
  data() {
    return {
      templates: [
        {
          id: "ma_cross",
          name: "双均线交叉",
          category: "趋势跟踪",
          description: "基于短期和长期均线的交叉信号进行交易",
          params: {
            fast_period: { min: 5, max: 20, default: 10, step: 1 },
            slow_period: { min: 20, max: 100, default: 30, step: 1 },
          },
        },
        {
          id: "rsi_divergence",
          name: "RSI背离策略",
          category: "反转",
          description: "利用RSI指标与价格走势的背离捕捉反转机会",
          params: {
            rsi_period: { min: 5, max: 30, default: 14, step: 1 },
            overbought: { min: 70, max: 90, default: 80, step: 1 },
            oversold: { min: 10, max: 30, default: 20, step: 1 },
          },
        },
        {
          id: "bollinger_breakout",
          name: "布林带突破",
          category: "突破",
          description: "价格突破布林带上下轨时产生交易信号",
          params: {
            period: { min: 10, max: 50, default: 20, step: 1 },
            std_dev: { min: 1, max: 3, default: 2, step: 0.1 },
          },
        },
        {
          id: "macd_crossover",
          name: "MACD交叉",
          category: "趋势跟踪",
          description: "基于MACD指标的快慢线交叉信号进行交易",
          params: {
            fast_period: { min: 5, max: 20, default: 12, step: 1 },
            slow_period: { min: 20, max: 50, default: 26, step: 1 },
            signal_period: { min: 5, max: 20, default: 9, step: 1 },
          },
        },
        {
          id: "mean_reversion",
          name: "均值回归",
          category: "反转",
          description: "价格偏离均值一定幅度后反向交易",
          params: {
            period: { min: 10, max: 100, default: 30, step: 1 },
            deviation: { min: 1, max: 5, default: 2, step: 0.1 },
          },
        },
        {
          id: "volume_spike",
          name: "成交量突增",
          category: "量价分析",
          description: "检测异常成交量并跟随趋势",
          params: {
            volume_multiplier: { min: 1.5, max: 5, default: 2, step: 0.1 },
            min_price_change: {
              min: 0.01,
              max: 0.1,
              default: 0.03,
              step: 0.01,
            },
          },
        },
      ],
      categories: [
        { id: "all", name: "全部策略" },
        { id: "trend", name: "趋势跟踪" },
        { id: "reversal", name: "反转" },
        { id: "breakout", name: "突破" },
        { id: "volatility", name: "波动率" },
        { id: "volume", name: "量价分析" },
      ],
      selectedCategory: this.category,
    };
  },
  computed: {
    filteredTemplates() {
      if (this.selectedCategory === "all") return this.templates;
      return this.templates.filter((t) => t.category === this.selectedCategory);
    },
  },
  methods: {
    selectTemplate(template) {
      this.$emit("select", template);
    },
  },
};
</script>

<template>
  <div class="strategy-template">
    <div class="category-filter">
      <div
        v-for="cat in categories"
        :key="cat.id"
        class="category-item"
        :class="{ active: selectedCategory === cat.id }"
        @click="selectedCategory = cat.id"
      >
        {{ cat.name }}
      </div>
    </div>

    <div class="template-list">
      <div
        v-for="template in filteredTemplates"
        :key="template.id"
        class="template-card"
        @click="selectTemplate(template)"
      >
        <div class="template-header">
          <h4>{{ template.name }}</h4>
          <span class="category-tag">{{ template.category }}</span>
        </div>
        <div class="template-description">
          {{ template.description }}
        </div>
        <div class="template-params">
          <div
            v-for="(param, name) in template.params"
            :key="name"
            class="param-item"
          >
            <span class="param-name">{{ name }}:</span>
            <span class="param-value">{{ param.default }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.strategy-template {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.category-filter {
  display: flex;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 15px;
  overflow-x: auto;
}

.category-item {
  padding: 5px 15px;
  margin-right: 10px;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  border: 1px solid #dcdfe6;
  background-color: #f5f7fa;
}

.category-item.active {
  background-color: #409eff;
  color: #fff;
  border-color: #409eff;
}

.template-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 10px;
}

.template-card {
  padding: 15px;
  margin-bottom: 15px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  background-color: #fff;
  cursor: pointer;
  transition: all 0.3s;
}

.template-card:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.template-header h4 {
  margin: 0;
  font-size: 16px;
}

.category-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background-color: #ecf5ff;
  color: #409eff;
  border: 1px solid #d9ecff;
}

.template-description {
  color: #606266;
  font-size: 13px;
  margin-bottom: 10px;
  line-height: 1.5;
}

.template-params {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
}

.param-item {
  padding: 3px 8px;
  background-color: #f5f7fa;
  border-radius: 3px;
  display: flex;
  align-items: center;
}

.param-name {
  color: #909399;
  margin-right: 5px;
}

.param-value {
  font-weight: 500;
}
</style>
