// 数据同步逻辑
import { ref, computed } from 'vue'
import { useStore } from '@/store'
import { useApi } from '@/api/data'

export function useDataSync() {
  const store = useStore()
  const api = useApi()

  const syncStatus = ref<'idle' | 'syncing' | 'error'>('idle')
  const syncProgress = ref(0)
  const lastSyncTime = ref<Date | null>(null)
  const errorMessage = ref<string>('')

  // 同步市场数据
  const syncMarketData = async (dataType: 'daily' | 'minute' | 'financial', options?: any) => {
    syncStatus.value = 'syncing'
    syncProgress.value = 0
    errorMessage.value = ''

    try {
      const response = await api.syncMarketData(dataType, {
        ...options,
        onProgress: (progress: number) => {
          syncProgress.value = progress
        }
      })

      syncStatus.value = 'idle'
      syncProgress.value = 100
      lastSyncTime.value = new Date()

      // 更新本地数据状态
      store.commit('data/UPDATE_SYNC_STATUS', {
        dataType,
        lastSync: lastSyncTime.value,
        recordCount: response.data.recordCount
      })

      return response.data
    } catch (error: any) {
      syncStatus.value = 'error'
      errorMessage.value = error.message || '数据同步失败'
      throw error
    }
  }

  // 批量同步数据
  const batchSync = async (syncTasks: Array<{dataType: string, options?: any}>) => {
    const results = []

    for (const task of syncTasks) {
      try {
        const result = await syncMarketData(task.dataType as any, task.options)
        results.push({
          dataType: task.dataType,
          status: 'success',
          result
        })
      } catch (error: any) {
        results.push({
          dataType: task.dataType,
          status: 'error',
          error: error.message
        })
      }
    }

    return results
  }

  // 检查数据完整性
  const checkDataIntegrity = async (dataType: string, startDate: string, endDate: string) => {
    try {
      const response = await api.checkDataIntegrity(dataType, startDate, endDate)
      return response.data
    } catch (error) {
      console.error('数据完整性检查失败:', error)
      throw error
    }
  }

  // 清理过期数据
  const cleanupOldData = async (dataType: string, beforeDate: string) => {
    try {
      const response = await api.cleanupOldData(dataType, beforeDate)

      store.commit('data/UPDATE_DATA_STATS', {
        dataType,
        action: 'cleanup',
        count: response.data.deletedCount
      })

      return response.data
    } catch (error) {
      console.error('数据清理失败:', error)
      throw error
    }
  }

  // 获取数据统计信息
  const getDataStats = async () => {
    try {
      const response = await api.getDataStats()
      store.commit('data/SET_DATA_STATS', response.data)
      return response.data
    } catch (error) {
      console.error('获取数据统计失败:', error)
      throw error
    }
  }

  // 自动同步调度
  const startAutoSync = (interval: number = 300000) => { // 默认5分钟
    const autoSync = setInterval(async () => {
      if (syncStatus.value !== 'syncing') {
        try {
          await syncMarketData('daily', { incremental: true })
        } catch (error) {
          console.error('自动同步失败:', error)
        }
      }
    }, interval)

    return () => clearInterval(autoSync)
  }

  // 计算属性
  const isSyncing = computed(() => syncStatus.value === 'syncing')
  const hasError = computed(() => syncStatus.value === 'error')
  const progressPercentage = computed(() => syncProgress.value)

  return {
    syncStatus,
    syncProgress,
    lastSyncTime,
    errorMessage,
    isSyncing,
    hasError,
    progressPercentage,

    syncMarketData,
    batchSync,
    checkDataIntegrity,
    cleanupOldData,
    getDataStats,
    startAutoSync
  }
}