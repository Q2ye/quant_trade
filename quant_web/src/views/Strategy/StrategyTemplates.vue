<!-- views/Strategy/StrategyTemplates.vue -->
<template>
  <div class="strategy-templates">
    <div class="page-header">
      <h1>策略模板库</h1>
      <p>预置的策略模板，快速创建交易策略</p>
    </div>

    <el-row :gutter="16" class="filter-row">
      <el-col :span="6">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索策略模板..."
          clearable
          prefix-icon="Search"
        />
      </el-col>
      <el-col :span="4">
        <el-select v-model="filterCategory" placeholder="策略类别" clearable>
          <el-option label="趋势跟踪" value="trend" />
          <el-option label="均值回归" value="mean_reversion" />
          <el-option label="因子策略" value="factor" />
          <el-option label="机器学习" value="ml" />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-select v-model="filterComplexity" placeholder="复杂度" clearable>
          <el-option label="简单" value="simple" />
          <el-option label="中等" value="medium" />
          <el-option label="复杂" value="complex" />
        </el-select>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="templates-grid">
      <el-col
        v-for="template in filteredTemplates"
        :key="template.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <el-card class="template-card" shadow="hover">
          <template #header>
            <div class="template-header">
              <span class="template-name">{{ template.name }}</span>
              <el-tag :type="getComplexityTag(template.complexity)" size="small">
                {{ template.complexity }}
              </el-tag>
            </div>
          </template>

          <div class="template-content">
            <p class="template-desc">{{ template.description }}</p>

            <div class="template-meta">
              <div class="meta-item">
                <Icon icon="mdi:chart-line" />
                <span>年化收益: {{ template.performance.annualReturn }}%</span>
              </div>
              <div class="meta-item">
                <Icon icon="mdi:trending-down" />
                <span>最大回撤: {{ template.performance.maxDrawdown }}%</span>
              </div>
              <div class="meta-item">
                <Icon icon="mdi:shield" />
                <span>夏普比率: {{ template.performance.sharpeRatio }}</span>
              </div>
            </div>

            <div class="template-tags">
              <el-tag
                v-for="tag in template.tags"
                :key="tag"
                size="small"
                type="info"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>

          <template #footer>
            <div class="template-actions">
              <el-button type="primary" size="small" @click="useTemplate(template)">
                使用模板
              </el-button>
              <el-button size="small" @click="viewDetails(template)">
                查看详情
              </el-button>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 模板详情对话框 -->
    <el-dialog
      v-model="detailVisible"
      :title="selectedTemplate?.name"
      width="600px"
    >
      <TemplateDetail :template="selectedTemplate" />
      <template #footer>
        <el-button @click="detailVisible = false">取消</el-button>
        <el-button type="primary" @click="useTemplate(selectedTemplate!)">
          使用此模板
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import TemplateDetail from "@/components/strategy/TemplateDetail.vue";

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

const router = useRouter()

const searchKeyword = ref('')
const filterCategory = ref('')
const filterComplexity = ref('')
const detailVisible = ref(false)
const selectedTemplate = ref<StrategyTemplate>()

const templates = ref<StrategyTemplate[]>([
  {
    id: '1',
    name: '双均线策略',
    description: '基于快速均线和慢速均线的金叉死叉信号进行交易',
    category: 'trend',
    complexity: 'simple',
    performance: {
      annualReturn: 15.2,
      maxDrawdown: -12.5,
      sharpeRatio: 1.2
    },
    tags: ['趋势跟踪', '均线', '技术指标']
  },
  {
    id: '2',
    name: '布林带突破',
    description: '利用布林带上下轨的突破信号进行趋势交易',
    category: 'trend',
    complexity: 'simple',
    performance: {
      annualReturn: 18.7,
      maxDrawdown: -15.3,
      sharpeRatio: 1.4
    },
    tags: ['突破', '波动率', '技术指标']
  },
  // 更多模板...
])

const filteredTemplates = computed(() => {
  return templates.value.filter(template => {
    const matchesSearch = template.name.toLowerCase().includes(searchKeyword.value.toLowerCase()) ||
                         template.description.toLowerCase().includes(searchKeyword.value.toLowerCase())
    const matchesCategory = !filterCategory.value || template.category === filterCategory.value
    const matchesComplexity = !filterComplexity.value || template.complexity === filterComplexity.value

    return matchesSearch && matchesCategory && matchesComplexity
  })
})

const getComplexityTag = (complexity: string) => {
  const map: Record<string, string> = {
    simple: 'success',
    medium: 'warning',
    complex: 'danger'
  }
  return map[complexity] || 'info'
}

const useTemplate = (template: StrategyTemplate) => {
  ElMessage.success(`正在使用模板: ${template.name}`)
  router.push({
    path: '/strategies/create',
    query: { template: template.id }
  })
}

const viewDetails = (template: StrategyTemplate) => {
  selectedTemplate.value = template
  detailVisible.value = true
}
</script>

<style scoped>
.strategy-templates {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.filter-row {
  margin-bottom: 24px;
}

.templates-grid {
  margin-top: 16px;
}

.template-card {
  margin-bottom: 16px;
  height: 280px;
  display: flex;
  flex-direction: column;
}

.template-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.template-name {
  font-weight: 600;
  font-size: 16px;
}

.template-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.template-desc {
  color: #606266;
  font-size: 14px;
  line-height: 1.4;
  margin-bottom: 16px;
  flex: 1;
}

.template-meta {
  margin-bottom: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
  font-size: 12px;
  color: #909399;
}

.meta-item .iconify {
  margin-right: 4px;
}

.template-tags {
  margin-bottom: 12px;
}

.template-tags .el-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.template-actions {
  display: flex;
  justify-content: space-between;
}
</style>