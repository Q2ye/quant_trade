import { computed, onUnmounted, ref, type Ref } from "vue";
import type { SyncStatusResponse } from "@/api/data-sync";

/**
 * 同步计时器 — 消除 DataSyncOverview / DataSync 重复的 now 定时器 + elapsedTime
 */
export function useSyncTimer(syncStatus: Ref<SyncStatusResponse | null>) {
  const now = ref(Date.now());
  const timer = setInterval(() => {
    now.value = Date.now();
  }, 1000);

  const isRunning = computed(() => syncStatus.value?.status === "running");

  const elapsedTime = computed(() => {
    if (!syncStatus.value?.created_at) return 0;
    if (!isRunning.value) return 0;
    return Math.max(
      0,
      Math.round(
        (now.value - new Date(syncStatus.value.created_at).getTime()) / 1000,
      ),
    );
  });

  const formatSeconds = (s: number): string => {
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    const sec = s % 60;
    if (m < 60) return `${m}m ${sec}s`;
    const h = Math.floor(m / 60);
    const min = m % 60;
    return `${h}h ${min}m ${sec}s`;
  };

  const formattedElapsedTime = computed(() => formatSeconds(elapsedTime.value));
  const formattedRemainingTime = computed(() =>
    formatSeconds(estimatedRemainingTime.value),
  );

  const estimatedRemainingTime = computed(() => {
    if (!isRunning.value) return 0;
    const progress = syncStatus.value?.progress?.progress_percentage || 0;
    if (progress <= 0)
      return syncStatus.value?.progress?.estimated_time_remaining || 0;
    const elapsed = elapsedTime.value;
    return Math.round((elapsed / progress) * (100 - progress));
  });

  onUnmounted(() => {
    clearInterval(timer);
  });

  return {
    now,
    isRunning,
    elapsedTime,
    estimatedRemainingTime,
    formattedElapsedTime,
    formattedRemainingTime,
  };
}
