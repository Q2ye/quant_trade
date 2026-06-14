// 数据同步逻辑
import { ref, computed } from "vue";
import { useStore } from "vuex";
import dataSyncService from "@/api/data-sync";

export function useDataSync() {
  const store = useStore();

  const syncStatus = ref<"idle" | "syncing" | "error">("idle");
  const syncProgress = ref(0);
  const lastSyncTime = ref<Date | null>(null);
  const errorMessage = ref<string>("");

  // 同步指定类型数据
  const syncMarketData = async (
    dataType: "daily" | "minute" | "financial" | "stock_basic" | "moneyflow",
    options?: any,
  ) => {
    syncStatus.value = "syncing";
    syncProgress.value = 0;
    errorMessage.value = "";

    try {
      let result;
      const params = {
        ...options,
        stock_codes: options?.stock_codes,
        start_date: options?.start_date,
        end_date: options?.end_date,
        batch_size: options?.batch_size,
      };

      switch (dataType) {
        case "daily":
          result = await dataSyncService.syncDailyData(params);
          break;
        case "stock_basic":
          result = await dataSyncService.syncStockBasic(params);
          break;
        case "moneyflow":
          result = await dataSyncService.syncMoneyflowData(params);
          break;
        default: {
          const task = { data_type: dataType } as {
            data_type: string;
            start_date?: string;
            end_date?: string;
          };
          if (params?.start_date) task.start_date = params.start_date;
          if (params?.end_date) task.end_date = params.end_date;
          result = await dataSyncService.batchSyncData({
            tasks: [task],
            priority: "medium",
          });
        }
      }

      syncStatus.value = "idle";
      syncProgress.value = 100;
      lastSyncTime.value = new Date();

      store.commit("data/UPDATE_SYNC_STATUS", {
        dataType,
        lastSync: lastSyncTime.value,
        recordCount: 0,
      });

      return result;
    } catch (error: any) {
      syncStatus.value = "error";
      errorMessage.value = error.message || "数据同步失败";
      throw error;
    }
  };

  // 批量同步数据（并行执行）
  const batchSync = async (
    syncTasks: Array<{ dataType: string; options?: any }>,
  ) => {
    const settled = await Promise.allSettled(
      syncTasks.map((task) =>
        syncMarketData(task.dataType as any, task.options),
      ),
    );
    return settled.map((r, i) =>
      r.status === "fulfilled"
        ? {
            dataType: syncTasks[i].dataType,
            status: "success" as const,
            result: r.value,
          }
        : {
            dataType: syncTasks[i].dataType,
            status: "error" as const,
            error: (r.reason as any)?.message,
          },
    );
  };

  // 查询同步状态
  const checkSyncStatus = async () => {
    try {
      const status = await dataSyncService.getSyncStatus();
      return status;
    } catch (error) {
      console.error("获取同步状态失败:", error);
      throw error;
    }
  };

  // 获取支持的数据类型
  const getSupportedTypes = async () => {
    try {
      return await dataSyncService.getSupportedDataTypes();
    } catch (error) {
      console.error("获取支持的数据类型失败:", error);
      throw error;
    }
  };

  // 取消当前同步
  const cancelSync = async () => {
    try {
      await dataSyncService.cancelSync();
      syncStatus.value = "idle";
    } catch (error) {
      console.error("取消同步失败:", error);
      throw error;
    }
  };

  // 自动同步调度
  const startAutoSync = (interval: number = 300000) => {
    const autoSync = setInterval(async () => {
      if (syncStatus.value !== "syncing") {
        try {
          await syncMarketData("daily");
        } catch (error) {
          console.error("自动同步失败:", error);
        }
      }
    }, interval);

    return () => clearInterval(autoSync);
  };

  // 计算属性
  const isSyncing = computed(() => syncStatus.value === "syncing");
  const hasError = computed(() => syncStatus.value === "error");
  const progressPercentage = computed(() => syncProgress.value);

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
    checkSyncStatus,
    getSupportedTypes,
    cancelSync,
    startAutoSync,
  };
}
