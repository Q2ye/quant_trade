/**
 * useBacktestPolling.ts — 回测任务状态轮询
 *
 * 统一所有回测场景的轮询逻辑：
 * - 单任务轮询（策略工作台、回测配置页）
 * - 批量任务轮询（回测工作台多策略对比）
 *
 * 特性：
 * - 自适应间隔：2s → 5s → 15s → 30s（按已运行时间）
 * - 容错重试：连续失败 ≤3 次不放弃，翻倍退避
 * - 自动清理：onUnmounted 时停止
 */

import { onUnmounted } from "vue";
import backtestAPI from "@/api/backtest";

// ============================================================
// 类型
// ============================================================

export interface PollingCallbacks {
  /** 每轮轮询回调，返回当前 task 对象 */
  onProgress?: (task: any) => void;
  /** 回测完成 */
  onCompleted?: (task: any) => void;
  /** 回测失败 */
  onFailed?: (task: any) => void;
  /** 回测取消 */
  onCancelled?: (task: any) => void;
}

export interface PollingOptions {
  /** 自定义任务状态查询函数（默认 backtestAPI.getTask） */
  fetchTask?: (taskId: string) => Promise<any>;
  /** 初始延迟 (ms)，默认 500 */
  initialDelay?: number;
}

export interface BatchPollingCallbacks {
  /** 单个任务完成（completed/failed）时回调 */
  onEachDone?: (task: any, taskId: string) => void;
  /** 完成时获取详细结果（如 getResult），返回的数据合并到 onAllDone 的 results 中 */
  fetchResult?: (taskId: string) => Promise<Record<string, any> | null>;
  /** 全部完成或超时，results 中 resultData 为 fetchResult 的返回值 */
  onAllDone?: (results: Array<{ task: any; taskId: string; resultData: Record<string, any> | null }>) => void;
  /** 超时（达到 maxAttempts） */
  onTimeout?: (taskIds: string[]) => void;
}

// ============================================================
// 自适应间隔
// ============================================================

const ELAPSED_THRESHOLDS: Array<{ maxSec: number; intervalMs: number }> = [
  { maxSec: 30, intervalMs: 2000 },   // 0-30s: 2s
  { maxSec: 300, intervalMs: 5000 },  // 30s-5min: 5s
  { maxSec: 1800, intervalMs: 15000 }, // 5min-30min: 15s
  { maxSec: Infinity, intervalMs: 30000 }, // >30min: 30s
];

function getAdaptiveInterval(elapsedMs: number): number {
  const sec = elapsedMs / 1000;
  for (const t of ELAPSED_THRESHOLDS) {
    if (sec <= t.maxSec) return t.intervalMs;
  }
  return 30000;
}

// ============================================================
// 单任务轮询
// ============================================================

export function useBacktestPolling(
  taskId: import("vue").Ref<string>,
  callbacks: PollingCallbacks = {},
  options: PollingOptions = {},
) {
  const fetchFn = options.fetchTask || ((id: string) => backtestAPI.getTask(id));
  const initialDelay = options.initialDelay ?? 500;

  let timer: ReturnType<typeof setTimeout> | null = null;
  let startedAt = 0;
  let consecutiveErrors = 0;
  const MAX_CONSECUTIVE_ERRORS = 3;
  let stopped = false;

  const stop = () => {
    stopped = true;
    if (timer) { clearTimeout(timer); timer = null; }
  };

  const scheduleNext = () => {
    if (stopped) return;
    const elapsed = Date.now() - startedAt;
    const interval = getAdaptiveInterval(elapsed);
    // 连续错误时翻倍退避
    const backoff = Math.min(consecutiveErrors, 3); // cap at 3 doublings
    const delay = interval * Math.pow(2, backoff);
    timer = setTimeout(poll, delay);
  };

  const poll = async () => {
    if (stopped) return;
    const id = taskId.value;
    if (!id) { stop(); return; }

    try {
      const task: any = await fetchFn(id);
      consecutiveErrors = 0; // reset on success

      callbacks.onProgress?.(task);

      if (task.status === "completed") {
        stop();
        callbacks.onCompleted?.(task);
        return;
      } else if (task.status === "failed") {
        stop();
        callbacks.onFailed?.(task);
        return;
      } else if (task.status === "cancelled") {
        stop();
        callbacks.onCancelled?.(task);
        return;
      }

      scheduleNext();
    } catch {
      consecutiveErrors++;
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        stop();
        callbacks.onFailed?.({ status: "failed", error_message: "轮询失败：连续 3 次 API 错误" });
        return;
      }
      scheduleNext();
    }
  };

  const start = () => {
    stop();
    stopped = false;
    startedAt = Date.now();
    consecutiveErrors = 0;
    // 首次延迟后开始，给后端一点时间
    timer = setTimeout(poll, initialDelay);
  };

  // 当 taskId 变化时自动开始轮询
  // （由外部显式调用 start()，composable 不自动启动）

  onUnmounted(() => stop());

  return { start, stop };
}

// ============================================================
// 批量任务轮询
// ============================================================

export function useBatchBacktestPolling(
  taskIds: import("vue").Ref<string[]>,
  callbacks: BatchPollingCallbacks = {},
  options: { maxAttempts?: number } = {},
) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let startedAt = 0;
  let consecutiveErrors = 0;
  const MAX_CONSECUTIVE_ERRORS = 5;
  let stopped = false;
  let attempts = 0;
  const { maxAttempts = 240 } = options;

  // 跟踪已完成的任务，避免重复 fetchResult
  const resolvedIds = new Set<string>();

  const stop = () => {
    stopped = true;
    if (timer) { clearTimeout(timer); timer = null; }
  };

  const scheduleNext = () => {
    if (stopped) return;
    const elapsed = Date.now() - startedAt;
    const interval = getAdaptiveInterval(elapsed);
    const backoff = Math.min(consecutiveErrors, 3);
    const delay = interval * Math.pow(2, backoff);
    timer = setTimeout(poll, delay);
  };

  const poll = async () => {
    if (stopped) return;
    const ids = taskIds.value;
    if (!ids || ids.length === 0) { stop(); return; }

    attempts++;
    let pollSuccess = false;

    // 检查是否已达最大尝试次数
    if (attempts >= maxAttempts) {
      stop();
      callbacks.onTimeout?.(ids);
      return;
    }

    try {
      let allDone = true;
      const doneResults: Array<{ task: any; taskId: string; resultData: Record<string, any> | null }> = [];

      for (const tid of ids) {
        try {
          const task: any = await backtestAPI.getTask(tid);
          pollSuccess = true;

          if (task.status !== "completed" && task.status !== "failed" && task.status !== "cancelled") {
            allDone = false;
            continue;
          }

          callbacks.onEachDone?.(task, tid);

          // 对已完成的任务获取详细结果
          let resultData: Record<string, any> | null = null;
          if (task.status === "completed" && callbacks.fetchResult && !resolvedIds.has(tid)) {
            try {
              resultData = await callbacks.fetchResult(tid);
              resolvedIds.add(tid);
            } catch {
              // fetchResult 失败不影响主流程
            }
          }

          doneResults.push({ task, taskId: tid, resultData });
        } catch {
          allDone = false;
        }
      }

      if (pollSuccess) consecutiveErrors = 0;
      else consecutiveErrors++;

      if (allDone) {
        stop();
        callbacks.onAllDone?.(doneResults);
        return;
      }

      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        stop();
        return;
      }

      scheduleNext();
    } catch {
      consecutiveErrors++;
      if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
        stop();
        return;
      }
      scheduleNext();
    }
  };

  const start = () => {
    stop();
    stopped = false;
    startedAt = Date.now();
    consecutiveErrors = 0;
    attempts = 0;
    resolvedIds.clear();
    timer = setTimeout(poll, 800);
  };

  onUnmounted(() => stop());

  return { start, stop };
}
