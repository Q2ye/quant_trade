<template>
  <div class="strategy-editor">
    <div class="editor-header">
      <select
        v-model="selectedTemplate"
        class="template-select"
      >
        <option
          v-for="template in templates"
          :key="template.id"
          :value="template"
        >
          {{ template.name }}
        </option>
      </select>
      <button
        class="btn apply-btn"
        @click="applyTemplate"
      >
        应用模板
      </button>
      <button
        class="btn format-btn"
        @click="formatCode"
      >
        格式化
      </button>
      <button
        class="btn run-btn"
        @click="runBacktest"
      >
        运行回测
      </button>
    </div>

    <div class="editor-container">
      <textarea
        v-model="strategyCode"
        class="code-editor"
        placeholder="编写您的量化策略..."
        spellcheck="false"
      />
    </div>

    <div class="editor-footer">
      <div class="status-indicator">
        <span :class="{'status-error': hasErrors, 'status-ok': !hasErrors}">
          {{ hasErrors ? '语法错误' : '语法正确' }}
        </span>
      </div>
      <div class="line-counter">
        行数: {{ lineCount }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "StrategyEditor",
  data() {
    return {
      strategyCode: `# 双均线策略示例
def initialize(context):
    # 设置标的
    context.security = '000001.SZ'
    # 设置参数
    context.short_window = 10
    context.long_window = 30

def handle_data(context, data):
    # 获取历史数据
    prices = data.history(context.security, 'close',
                          context.long_window + 1, '1d')

    # 计算均线
    short_ma = prices[-context.short_window:].mean()
    long_ma = prices.mean()

    # 获取当前持仓
    current_position = context.portfolio.positions[context.security].amount

    # 交易逻辑
    if short_ma > long_ma and current_position == 0:
        # 金叉且无持仓，买入
        order_value(context.security, context.portfolio.cash)
    elif short_ma < long_ma and current_position > 0:
        # 死叉且有持仓，卖出
        order_target(context.security, 0)`,
      selectedTemplate: null,
      hasErrors: false,
      templates: [
        { id: 1, name: '双均线策略', content: '双均线策略模板内容...' },
        { id: 2, name: '动量反转策略', content: '动量反转策略模板内容...' },
        { id: 3, name: '均值回归策略', content: '均值回归策略模板内容...' }
      ]
    }
  },
  computed: {
    lineCount() {
      return this.strategyCode.split('\n').length;
    }
  },
  methods: {
    applyTemplate() {
      if (this.selectedTemplate) {
        this.strategyCode = this.selectedTemplate.content;
      }
    },
    formatCode() {
      // 这里简化处理，实际项目中应使用代码格式化工具
      alert('代码格式化功能');
    },
    runBacktest() {
      this.$emit('run-backtest', this.strategyCode);
    }
  }
}
</script>

<style scoped>
.strategy-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.editor-header {
  padding: 8px 10px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  gap: 10px;
}

.template-select {
  flex: 1;
  padding: 5px;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
}

.btn {
  padding: 5px 12px;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}

.apply-btn {
  background-color: #409eff;
  color: white;
}

.format-btn {
  background-color: #e6a23c;
  color: white;
}

.run-btn {
  background-color: #67c23a;
  color: white;
  font-weight: bold;
}

.editor-container {
  flex: 1;
  overflow: hidden;
}

.code-editor {
  width: 100%;
  height: 100%;
  padding: 10px;
  font-family: 'Consolas', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.5;
  border: none;
  resize: none;
  outline: none;
  background-color: #f8f8f8;
  white-space: pre;
}

.editor-footer {
  padding: 5px 10px;
  background-color: #f5f7fa;
  border-top: 1px solid #dcdfe6;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #606266;
}

.status-error {
  color: #f56c6c;
  font-weight: bold;
}

.status-ok {
  color: #67c23a;
}
</style>