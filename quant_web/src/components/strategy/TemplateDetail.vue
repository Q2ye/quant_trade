<!-- components/strategy/TemplateDetail.vue -->
<template>
  <div class="template-detail">
    <div class="detail-section">
      <h3>策略描述</h3>
      <p>{{ template.description }}</p>
    </div>

    <el-row :gutter="24" class="detail-section">
      <el-col :span="8">
        <div class="info-item">
          <div class="info-label">
            <Icon icon="mdi:chart-bell-curve" />
            <span>策略类别</span>
          </div>
          <div class="info-value">
            <el-tag :type="getCategoryTag(template.category)" size="small">
              {{ getCategoryLabel(template.category) }}
            </el-tag>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="info-item">
          <div class="info-label">
            <Icon icon="mdi:puzzle" />
            <span>复杂度</span>
          </div>
          <div class="info-value">
            <el-tag :type="getComplexityTag(template.complexity)" size="small">
              {{ getComplexityLabel(template.complexity) }}
            </el-tag>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="info-item">
          <div class="info-label">
            <Icon icon="mdi:identifier" />
            <span>模板ID</span>
          </div>
          <div class="info-value">{{ template.id }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="detail-section">
      <h3>性能指标</h3>
      <el-row :gutter="24">
        <el-col :span="6">
          <div class="metric-card">
            <div class="metric-icon positive">
              <Icon icon="mdi:chart-line" />
            </div>
            <div class="metric-content">
              <div class="metric-value">{{ template.performance.annualReturn }}%</div>
              <div class="metric-label">年化收益</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="metric-card">
            <div class="metric-icon negative">
              <Icon icon="mdi:trending-down" />
            </div>
            <div class="metric-content">
              <div class="metric-value">{{ template.performance.maxDrawdown }}%</div>
              <div class="metric-label">最大回撤</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="metric-card">
            <div class="metric-icon positive">
              <Icon icon="mdi:shield" />
            </div>
            <div class="metric-content">
              <div class="metric-value">{{ template.performance.sharpeRatio }}</div>
              <div class="metric-label">夏普比率</div>
            </div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="metric-card">
            <div class="metric-icon neutral">
              <Icon icon="mdi:calendar" />
            </div>
            <div class="metric-content">
              <div class="metric-value">3年</div>
              <div class="metric-label">回测周期</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="detail-section">
      <h3>标签</h3>
      <div class="tags-container">
        <el-tag
          v-for="tag in template.tags"
          :key="tag"
          type="info"
          size="medium"
          class="detail-tag"
        >
          {{ tag }}
        </el-tag>
      </div>
    </div>

    <div class="detail-section">
      <h3>策略特点</h3>
      <ul class="feature-list">
        <li v-for="feature in getTemplateFeatures(template)" :key="feature">
          <Icon icon="mdi:check-circle" class="feature-icon" />
          {{ feature }}
        </li>
      </ul>
    </div>

    <div class="detail-section">
      <h3>适用场景</h3>
      <div class="scenario-content">
        <div class="scenario-item">
          <Icon icon="mdi:chart-areaspline" />
          <span>{{ getScenarioDescription(template.category) }}</span>
        </div>
        <div class="scenario-item">
          <Icon icon="mdi:clock-outline" />
          <span>建议持仓周期: {{ getHoldingPeriod(template.category) }}</span>
        </div>
        <div class="scenario-item">
          <Icon icon="mdi:alert-circle" />
          <span>风险等级: {{ getRiskLevel(template.complexity) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface StrategyTemplate {
  id: string
  name: string
  description: string
  category: string
  complexity: string
  performance: {
    annualReturn: number
    maxDrawdown: number
    sharpeRatio: number
  }
  tags: string[]
}

interface Props {
  template: StrategyTemplate
}

defineProps<Props>()

const getCategoryTag = (category: string) => {
  const map: Record<string, string> = {
    trend: 'success',
    mean_reversion: 'warning',
    factor: 'primary',
    ml: 'danger'
  }
  return map[category] || 'info'
}

const getCategoryLabel = (category: string) => {
  const map: Record<string, string> = {
    trend: '趋势跟踪',
    mean_reversion: '均值回归',
    factor: '因子策略',
    ml: '机器学习'
  }
  return map[category] || category
}

const getComplexityTag = (complexity: string) => {
  const map: Record<string, string> = {
    simple: 'success',
    medium: 'warning',
    complex: 'danger'
  }
  return map[complexity] || 'info'
}

const getComplexityLabel = (complexity: string) => {
  const map: Record<string, string> = {
    simple: '简单',
    medium: '中等',
    complex: '复杂'
  }
  return map[complexity] || complexity
}

const getTemplateFeatures = (template: StrategyTemplate) => {
  const featureMap: Record<string, string[]> = {
    trend: [
      '捕捉市场趋势方向',
      '适合趋势明显的市场环境',
      '止损机制完善',
      '信号明确易于执行'
    ],
    mean_reversion: [
      '利用价格回归特性',
      '适合震荡市场环境',
      '高胜率策略',
      '需要严格风控'
    ],
    factor: [
      '多因子组合',
      '系统化投资',
      '风险分散',
      '适合机构投资者'
    ],
    ml: [
      '机器学习模型驱动',
      '自适应市场变化',
      '需要大量数据训练',
      '模型解释性要求高'
    ]
  }
  return featureMap[template.category] || ['策略逻辑清晰', '回测表现稳定']
}

const getScenarioDescription = (category: string) => {
  const map: Record<string, string> = {
    trend: '适用于有明显趋势的牛市或熊市行情',
    mean_reversion: '适用于震荡市或区间波动的市场环境',
    factor: '适用于多因子选股和系统化投资',
    ml: '适用于大数据分析和复杂模式识别场景'
  }
  return map[category] || '适用于多种市场环境'
}

const getHoldingPeriod = (category: string) => {
  const map: Record<string, string> = {
    trend: '中长线',
    mean_reversion: '短线',
    factor: '中长线',
    ml: '灵活调整'
  }
  return map[category] || '中线'
}

const getRiskLevel = (complexity: string) => {
  const map: Record<string, string> = {
    simple: '低风险',
    medium: '中风险',
    complex: '高风险'
  }
  return map[complexity] || '中风险'
}
</script>

<style scoped>
.template-detail {
  padding: 8px 0;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h3 {
  margin-bottom: 16px;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
  font-size: 14px;
}

.info-value {
  font-weight: 500;
  color: #303133;
}

.metric-card {
  display: flex;
  align-items: center;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  gap: 12px;
}

.metric-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.metric-icon.positive {
  background: #e8f5e8;
  color: #67c23a;
}

.metric-icon.negative {
  background: #fef0f0;
  color: #f56c6c;
}

.metric-icon.neutral {
  background: #f4f4f5;
  color: #909399;
}

.metric-content {
  flex: 1;
}

.metric-value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.metric-label {
  font-size: 12px;
  color: #909399;
}

.tags-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-tag {
  font-size: 13px;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.feature-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: #606266;
}

.feature-icon {
  color: #67c23a;
  font-size: 16px;
}

.scenario-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.scenario-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  color: #606266;
}

.scenario-item .iconify {
  color: #409eff;
  font-size: 16px;
}
</style>