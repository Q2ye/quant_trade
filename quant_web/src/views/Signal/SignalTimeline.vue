<template>
  <div class="signal-timeline">
    <div class="timeline-header">
      <h3>信号时间线</h3>
      <div class="filter-controls">
        <div class="filter-group">
          <label>信号类型:</label>
          <select v-model="filters.type" multiple>
            <option value="buy">买入</option>
            <option value="sell">卖出</option>
            <option value="hold">持有</option>
          </select>
        </div>

        <div class="filter-group">
          <label>时间范围:</label>
          <select v-model="filters.timeRange">
            <option value="1h">最近1小时</option>
            <option value="today">今天</option>
            <option value="week">本周</option>
            <option value="all">全部</option>
          </select>
        </div>

        <div class="filter-group">
          <label>股票代码:</label>
          <input
            v-model="filters.symbol"
            placeholder="输入股票代码"
            type="text"
          >
        </div>

        <button class="clear-btn" @click="clearFilters">清除筛选</button>
      </div>
    </div>

    <div class="timeline-content">
      <div v-if="filteredSignals.length === 0" class="empty-state">
        <i class="fas fa-inbox"></i>
        <p>暂无信号数据</p>
      </div>

      <div v-else class="signal-list">
        <div
          v-for="(signal, index) in filteredSignals"
          :key="index"
          class="signal-item"
          :class="signal.type"
        >
          <div class="signal-icon">
            <i
              v-if="signal.type === 'buy'"
              class="fas fa-arrow-up"
            ></i>
            <i
              v-else-if="signal.type === 'sell'"
              class="fas fa-arrow-down"
            ></i>
            <i
              v-else
              class="fas fa-pause"
            ></i>
          </div>

          <div class="signal-content">
            <div class="signal-header">
              <div class="signal-title">
                <span class="signal-symbol">{{ signal.symbol }}</span>
                <span class="signal-type-tag">
                  {{ signal.type === 'buy' ? '买入' : signal.type === 'sell' ? '卖出' : '持有' }}
                </span>
              </div>
              <div class="signal-time">{{ formatTime(signal.time) }}</div>
            </div>

            <div class="signal-details">
              <div class="signal-detail" v-if="signal.price">
                <i class="fas fa-tag"></i>
                <span>价格: {{ signal.price }}元</span>
              </div>

              <div class="signal-detail" v-if="signal.volume">
                <i class="fas fa-chart-bar"></i>
                <span>数量: {{ signal.volume }}股</span>
              </div>

              <div class="signal-detail" v-if="signal.strength">
                <i class="fas fa-battery-three-quarters"></i>
                <span>强度: {{ (signal.strength * 100).toFixed(1) }}%</span>
              </div>
            </div>

            <div class="signal-reason" v-if="signal.reason">
              <i class="fas fa-comment"></i> {{ signal.reason }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "SignalTimeline",
  props: {
    signals: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      filters: {
        type: [],
        timeRange: 'today',
        symbol: ''
      }
    }
  },
  computed: {
    filteredSignals() {
      let result = [...this.signals];

      // 按信号类型筛选
      if (this.filters.type.length > 0) {
        result = result.filter(signal =>
          this.filters.type.includes(signal.type)
        );
      }

      // 按股票代码筛选
      if (this.filters.symbol) {
        const symbol = this.filters.symbol.toUpperCase();
        result = result.filter(signal =>
          signal.symbol.includes(symbol)
        );
      }

      // 按时间范围筛选
      const now = new Date();
      switch (this.filters.timeRange) {
        case '1h':
          const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
          result = result.filter(signal => new Date(signal.time) >= oneHourAgo);
          break;
        case 'today':
          const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          result = result.filter(signal => new Date(signal.time) >= todayStart);
          break;
        case 'week':
          const weekStart = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          result = result.filter(signal => new Date(signal.time) >= weekStart);
          break;
      }

      // 按时间倒序排列（最新的在前）
      return result.sort((a, b) => new Date(b.time) - new Date(a.time));
    }
  },
  methods: {
    formatTime(time) {
      return new Date(time).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    },
    clearFilters() {
      this.filters = {
        type: [],
        timeRange: 'today',
        symbol: ''
      };
    }
  }
}
</script>

<style scoped>
.signal-timeline {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background-color: #fff;
}

.timeline-header {
  padding: 12px 15px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
}

.timeline-header h3 {
  margin: 0 0 10px 0;
  color: #303133;
  font-size: 16px;
}

.filter-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  align-items: center;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-group label {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.filter-group select,
.filter-group input {
  padding: 5px 8px;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  font-size: 12px;
}

.filter-group select[multiple] {
  height: 60px;
}

.clear-btn {
  padding: 5px 10px;
  background-color: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  color: #606266;
}

.clear-btn:hover {
  background-color: #ebeef5;
}

.timeline-content {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.empty-state i {
  font-size: 40px;
  margin-bottom: 10px;
  opacity: 0.5;
}

.empty-state p {
  margin: 0;
  font-size: 14px;
}

.signal-list {
  display: flex;
  flex-direction: column;
}

.signal-item {
  display: flex;
  margin-bottom: 15px;
  position: relative;
  padding-left: 30px;
}

.signal-item::before {
  content: '';
  position: absolute;
  left: 15px;
  top: 25px;
  bottom: -15px;
  width: 2px;
  background-color: #ebeef5;
}

.signal-item:last-child::before {
  display: none;
}

.signal-icon {
  position: absolute;
  left: 0;
  top: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

.signal-item.buy .signal-icon {
  background-color: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.signal-item.sell .signal-icon {
  background-color: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}

.signal-item.hold .signal-icon {
  background-color: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.signal-content {
  flex: 1;
  background-color: #f8f8f8;
  border-radius: 4px;
  padding: 10px 12px;
  border-left: 3px solid transparent;
}

.signal-item.buy .signal-content {
  border-left-color: #67c23a;
}

.signal-item.sell .signal-content {
  border-left-color: #f56c6c;
}

.signal-item.hold .signal-content {
  border-left-color: #e6a23c;
}

.signal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.signal-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.signal-symbol {
  font-weight: bold;
  color: #303133;
}

.signal-type-tag {
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: bold;
}

.signal-item.buy .signal-type-tag {
  background-color: rgba(103, 194, 58, 0.2);
  color: #67c23a;
}

.signal-item.sell .signal-type-tag {
  background-color: rgba(245, 108, 108, 0.2);
  color: #f56c6c;
}

.signal-item.hold .signal-type-tag {
  background-color: rgba(230, 162, 60, 0.2);
  color: #e6a23c;
}

.signal-time {
  font-size: 11px;
  color: #909399;
}

.signal-details {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 8px;
}

.signal-detail {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #606266;
}

.signal-detail i {
  color: #909399;
}

.signal-reason {
  padding: 6px 8px;
  background-color: rgba(0, 0, 0, 0.05);
  border-radius: 3px;
  font-size: 12px;
  color: #606266;
}

.signal-reason i {
  margin-right: 4px;
  color: #909399;
}

@media (max-width: 768px) {
  .filter-controls {
    flex-direction: column;
    align-items: flex-start;
  }

  .filter-group {
    width: 100%;
  }

  .signal-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .signal-time {
    margin-top: 4px;
  }
}
</style>