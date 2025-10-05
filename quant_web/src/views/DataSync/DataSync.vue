<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { SyncOutlined, CloudDownloadOutlined } from '@ant-design/icons-vue'

interface SyncConfig {
  dataType: string[]
  symbolCodes: string
  dateRange: [string, string]
  syncMode: 'incremental' | 'full'
}

const syncConfig = reactive<SyncConfig>({
  dataType: ['daily'],
  symbolCodes: '',
  dateRange: ['', ''],
  syncMode: 'incremental'
})

const dataTypes = [
  { label: '股票列表', value: 'stock_basic' },
  { label: '交易日历', value: 'trade_calendar' },
  { label: '日线行情', value: 'daily' },
  { label: '分钟行情', value: 'minute' },
  { label: '财务数据', value: 'financial' },
  { label: '资金流向', value: 'moneyflow' },
  { label: 'ETF数据', value: 'etf' },
  { label: '复权因子', value: 'adj_factor' }
]

const isLoading = ref(false)

const handleSync = async () => {
  if (!syncConfig.dataType.length) {
    message.warning('请选择至少一种数据类型')
    return
  }

  isLoading.value = true
  try {
    // 调用后端同步接口
    const response = await fetch('/api/data-sync/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(syncConfig)
    })

    if (response.ok) {
      message.success('数据同步任务已启动')
    } else {
      throw new Error('同步任务启动失败')
    }
  } catch (error) {
    message.error('同步任务启动失败')
  } finally {
    isLoading.value = false
  }
}

const handleFullSync = () => {
  Modal.confirm({
    title: '确认全量同步',
    content: '全量同步将重新下载所有历史数据，耗时较长，确定继续吗？',
    onOk: async () => {
      syncConfig.syncMode = 'full'
      syncConfig.dateRange = ['', '']
      await handleSync()
    }
  })
}
</script>

<template>
  <div class="data-sync-page">
    <a-card title="数据同步配置" class="sync-card">
      <a-form layout="vertical">
        <a-form-item label="数据类型">
          <a-checkbox-group v-model:value="syncConfig.dataType" class="data-type-group">
            <a-row :gutter="[16, 16]">
              <a-col :span="8" v-for="type in dataTypes" :key="type.value">
                <a-checkbox :value="type.value">{{ type.label }}</a-checkbox>
              </a-col>
            </a-row>
          </a-checkbox-group>
        </a-form-item>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="标的代码">
              <a-textarea
                v-model:value="syncConfig.symbolCodes"
                placeholder="输入股票/ETF代码，多个用逗号分隔，留空则同步全市场"
                :rows="3"
              />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="时间范围">
              <a-range-picker
                v-model:value="syncConfig.dateRange"
                format="YYYY-MM-DD"
                style="width: 100%"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="同步模式">
          <a-radio-group v-model:value="syncConfig.syncMode">
            <a-radio value="incremental">增量同步（最近N天）</a-radio>
            <a-radio value="full">全量同步</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>

      <template #extra>
        <a-space>
          <a-button
            type="primary"
            :loading="isLoading"
            @click="handleSync"
          >
            <template #icon><CloudDownloadOutlined /></template>
            开始同步
          </a-button>
          <a-button
            danger
            @click="handleFullSync"
          >
            <template #icon><SyncOutlined /></template>
            全量同步
          </a-button>
        </a-space>
      </template>
    </a-card>

    <div class="sync-tips">
      <a-alert
        message="同步提示"
        description="数据同步任务将在后台执行，您可以在'同步任务监控'页面查看执行进度和结果"
        type="info"
        show-icon
      />
    </div>
  </div>
</template>

<style scoped>
.data-sync-page {
  padding: 24px;
}

.sync-card {
  margin-bottom: 24px;
}

.data-type-group {
  width: 100%;
}

.sync-tips {
  max-width: 800px;
}
</style>