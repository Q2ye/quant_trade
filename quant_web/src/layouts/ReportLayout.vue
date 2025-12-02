<template>
  <div class="report-layout">
    <!-- 回测报告头部 -->
    <div class="report-header">
      <div class="header-left">
        <h1>{{ reportTitle }}</h1>
        <div class="report-meta">
          <span class="meta-item">策略: {{ strategyName }}</span>
          <span class="meta-item">回测周期: {{ timeRange }}</span>
          <span class="meta-item">初始资金: {{ initialCapital }}元</span>
        </div>
      </div>

      <div class="header-actions">
        <n-button
          type="primary"
          @click="exportReport"
        >
          <template #icon>
            <smart-icon name="CloudDownload" />
          </template>
          导出报告
        </n-button>
        <n-button
          @click="goBack"
        >
          <template #icon>
            <smart-icon name="ArrowBack" />
          </template>
          返回策略
        </n-button>
      </div>
    </div>

    <!-- 报告内容区域 -->
    <div class="report-content">
      <slot />
    </div>

    <!-- 报告页脚 -->
    <div class="report-footer">
      <span>生成时间: {{ generateTime }}</span>
      <span>量化交易平台 v1.0</span>
    </div>
  </div>
</template>

<script>
import { defineComponent } from 'vue'
import { NButton, useMessage } from 'naive-ui'
import SmartIcon from '@/components/common/SmartIcon.vue'

export default defineComponent({
  name: "ReportLayout",
  components: {
    NButton,
    SmartIcon
  },
  props: {
    reportData: {
      type: Object,
      default: () => ({
        title: '回测报告',
        strategy: '双均线策略',
        startDate: '2023-01-01',
        endDate: '2023-08-01',
        capital: 1000000
      })
    }
  },
  setup() {
    const message = useMessage()

    return {
      message
    }
  },
  computed: {
    reportTitle() {
      return this.reportData.title || '策略回测报告';
    },
    strategyName() {
      return this.reportData.strategy || '未命名策略';
    },
    timeRange() {
      return `${this.reportData.startDate} 至 ${this.reportData.endDate}`;
    },
    initialCapital() {
      return (this.reportData.capital || 0).toLocaleString();
    },
    generateTime() {
      return new Date().toLocaleString();
    }
  },
  methods: {
    exportReport() {
      this.message.success('报告导出成功');
      // 实际项目中实现导出PDF功能
    },
    goBack() {
      this.$emit('go-back');
    }
  }
})
</script>

<style scoped>
.report-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #fff;
  color: #333;
  font-family: 'Helvetica Neue', Arial, sans-serif;
}

.report-header {
  padding: 20px 30px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h1 {
  margin: 0 0 10px 0;
  font-size: 24px;
  color: #1a1a1a;
}

.report-meta {
  display: flex;
  gap: 20px;
  font-size: 14px;
  color: #6c757d;
}

.meta-item {
  display: flex;
  align-items: center;
}

.meta-item:before {
  content: "•";
  margin-right: 5px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.report-content {
  flex: 1;
  overflow: auto;
  padding: 30px;
  background-color: #fff;
}

.report-footer {
  padding: 15px 30px;
  background: #f8f9fa;
  border-top: 1px solid #e9ecef;
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #6c757d;
}
</style>