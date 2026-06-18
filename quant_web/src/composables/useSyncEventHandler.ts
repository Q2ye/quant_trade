import { onUnmounted, type Ref } from "vue";
import webSocketService from "@/api/websocket";
import type { SyncEventMessage } from "@/types";
import type { SyncStatusResponse } from "@/api/data-sync";

interface SyncEventCallbacks {
  onStarted?: (taskId: string) => void;
  onCompleted?: () => void;
  onFailed?: (errorMessage?: string) => void;
  onCancelled?: () => void;
}

/**
 * 同步 WS 事件统一处理 — 消除 DataSyncOverview / DataSync 重复的 switch-case
 */
export function useSyncEventHandler(
  syncStatus: Ref<SyncStatusResponse | null>,
  callbacks?: SyncEventCallbacks,
) {
  const handleSyncEvent = (eventData: SyncEventMessage) => {
    if (!syncStatus.value) return;

    const s = syncStatus.value;
    switch (eventData._event) {
      case "data_sync_started":
        s.status = "running";
        s.task_id = eventData.task_id;
        callbacks?.onStarted?.(eventData.task_id);
        break;
      case "data_sync_progress":
        s.status = "running";
        if (s.progress && eventData.progress != null) {
          s.progress.progress_percentage = eventData.progress;
        }
        break;
      case "data_sync_completed":
        s.status = "completed";
        if (s.progress) s.progress.progress_percentage = 100;
        s.updated_at = new Date().toISOString();
        callbacks?.onCompleted?.();
        break;
      case "data_sync_failed":
        s.status = "failed";
        s.message = eventData.error_message || "同步失败";
        s.updated_at = new Date().toISOString();
        callbacks?.onFailed?.(eventData.error_message);
        break;
      case "data_sync_cancelled":
        s.status = "cancelled";
        s.updated_at = new Date().toISOString();
        callbacks?.onCancelled?.();
        break;
    }
  };

  // 自动订阅（组件挂载时立即激活 WS 通道）
  webSocketService.subscribeSyncStatus(handleSyncEvent);

  const unsubscribe = () => {
    webSocketService.unsubscribe("events:sync", handleSyncEvent);
  };

  onUnmounted(unsubscribe);

  return { unsubscribe, handleSyncEvent };
}
