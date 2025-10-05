<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  BarChartOutlined
} from '@ant-design/icons-vue'

const route = useRoute()
const indexCode = ref(route.params.code as string)

interface IndexDetail {
  ts_code: string
  name: string
  fullname: string
  market: string
  publisher: string
  category: string
  base_date: string
  base_point: number
  list_date: string
  current_point: number
  change: number
  change_percent: number
  open: number
  high: number
  low: number
  pre_close: number
  volume: number
  amount: number
  pe: number
  pb: number
  components_count: number
}

const loading = ref(false)
const indexDetail = ref<IndexDetail | null>(null)
const activeTab = ref('overview')

const loadIndexDetail = async () => {
  loading.value = true
  try {
    const response = await fetch(`/api/market/indexes/${indexCode.value}`)
    indexDetail.value = await response.json()
  } catch (error) {
    console.error('加载指数详情失败:', error)
  } finally {
    loading.value = false
  }
}

const statisticValueStyle = computed(() => ({
  color: indexDetail.value && indexDetail.value.change_percent >= 0 ? '#f5222d' : '#52c41a'
}))

onMounted(() => {
  loadIndexDetail()
})
</script>

<template>
  <div class="index-detail-page">
    <a-card :loading="loading">
      <template #title>
        <div class="page-header">
          <h2 style="margin: 0;">
            {{ indexDetail?.name || '指数详情' }}
            <span style="font-size: 16px; color: #666; margin-left: 8px;">
              {{ indexDetail?.ts_code }}
            </span>
          </h2>
          <div v-if="indexDetail" class="price-display">
            <span class="current-price">{{ indexDetail.current_point?.toFixed(2) }}</span>
            <span class="price-change" :class="{ rise: indexDetail.change_percent && indexDetail.change_percent >= 0, fall: indexDetail.change_percent && indexDetail.change_percent < 0 }">
              {{ indexDetail.change >= 0 ? '+' : '' }}{{ indexDetail.change?.toFixed(2) }}
              ({{ indexDetail.change_percent && indexDetail.change_percent >= 0 ? '+' : '' }}{{ indexDetail.change_percent?.toFixed(2) }}%)
            </span>
          </div>
        </div>
      </template>

      <a-tabs v-model:activeKey="activeTab">
        <a-tab-pane key="overview" tab="概览">
          <a-descriptions title="基本信息" bordered :column="2">
            <a-descriptions-item label="指数全称">
              {{ indexDetail?.fullname }}
            </a-descriptions-item>
            <a-descriptions-item label="市场">
              <a-tag color="blue">{{ indexDetail?.market }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="发布机构">
              {{ indexDetail?.publisher }}
            </a-descriptions-item>
            <a-descriptions-item label="分类">
              {{ indexDetail?.category }}
            </a-descriptions-item>
            <a-descriptions-item label="基日">
              {{ indexDetail?.base_date }}
            </a-descriptions-item>
            <a-descriptions-item label="基点">
              {{ indexDetail?.base_point }}
            </a-descriptions-item>
            <a-descriptions-item label="成分股数量">
              {{ indexDetail?.components_count }} 只
            </a-descriptions-item>
          </a-descriptions>

          <a-row :gutter="16" style="margin-top: 24px;">
            <a-col :span="6">
              <a-statistic
                title="开盘"
                :value="indexDetail?.open"
                :precision="2"
                :value-style="statisticValueStyle"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="最高"
                :value="indexDetail?.high"
                :precision="2"
                :value-style="statisticValueStyle"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="最低"
                :value="indexDetail?.low"
                :precision="2"
                :value-style="statisticValueStyle"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="昨收"
                :value="indexDetail?.pre_close"
                :precision="2"
              />
            </a-col>
          </a-row>

          <a-row :gutter="16" style="margin-top: 24px;">
            <a-col :span="6">
              <a-statistic
                title="成交量(亿)"
                :value="indexDetail?.volume ? indexDetail.volume / 100000000 : 0"
                :precision="2"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="成交额(亿)"
                :value="indexDetail?.amount ? indexDetail.amount / 100000000 : 0"
                :precision="2"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="市盈率(PE)"
                :value="indexDetail?.pe"
                :precision="2"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                title="市净率(PB)"
                :value="indexDetail?.pb"
                :precision="2"
              />
            </a-col>
          </a-row>
        </a-tab-pane>

        <a-tab-pane key="chart" tab="图表分析">
          <div class="chart-container">
            <!-- 这里可以集成K线图组件 -->
            <div style="height: 500px; background: #f5f5f5; display: flex; align-items: center; justify-content: center;">
              <a-space direction="vertical" align="center">
                <BarChartOutlined style="font-size: 48px; color: #ccc;" />
                <div style="color: #999;">指数图表展示区域</div>
              </a-space>
            </div>
          </div>
        </a-tab-pane>

        <a-tab-pane key="components" tab="成分股">
          <div class="components-container">
            <!-- 成分股列表 -->
            <div style="height: 400px; background: #f5f5f5; display: flex; align-items: center; justify-content: center;">
              <div style="color: #999;">成分股列表展示区域</div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>
  </div>
</template>

<style scoped>
.index-detail-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.price-display {
  text-align: right;
}

.current-price {
  font-size: 28px;
  font-weight: bold;
  margin-right: 12px;
}

.price-change {
  font-size: 16px;
}

.price-change.rise {
  color: #f5222d;
}

.price-change.fall {
  color: #52c41a;
}

.chart-container {
  margin-top: 16px;
}

.components-container {
  margin-top: 16px;
}
</style>