// usePrimitiveManager.ts — lightweight-charts 原语（Primitive）生命周期管理器
// 管理 ISeriesPrimitive 的 attach/detach/requestUpdate 生命周期
// 使用 requestAnimationFrame 合并高频更新请求
import { type ISeriesApi, type ISeriesPrimitive, type SeriesType, type Time } from "lightweight-charts";

export function usePrimitiveManager() {
  const _attached: Map<string, ISeriesPrimitive<Time>> = new Map();
  let _series: ISeriesApi<SeriesType, Time> | null = null;
  let _requestUpdate: (() => void) | null = null;
  let _pendingUpdate = false;
  let _rafId: number | null = null;

  /**
   * 将原语管理器绑定到指定的 series 和 requestUpdate 回调
   * ⚠️ 如果 series 变更（chart 重建场景），自动清空所有旧原语引用，
   *    避免原语残留到已销毁的 chart 上导致 XY 坐标漂移。
   */
  function bind(
    series: ISeriesApi<SeriesType, Time>,
    requestUpdate: () => void,
  ): void {
    // series 变更 → 旧 chart 已销毁，清空所有残留原语引用
    if (_series !== null && _series !== series) {
      _attached.clear();
    }
    _series = series;
    _requestUpdate = requestUpdate;
  }

  /**
   * 附加一个原语到系列
   */
  function attach(id: string, primitive: ISeriesPrimitive<Time>): void {
    if (!_series) {
      console.warn("[usePrimitiveManager] bind() must be called before attach()");
      return;
    }
    if (_attached.has(id)) {
      detach(id);
    }
    _series.attachPrimitive(primitive);
    _attached.set(id, primitive);
  }

  /**
   * 从系列中分离一个原语
   */
  function detach(id: string): void {
    const primitive = _attached.get(id);
    if (!primitive || !_series) return;
    _series.detachPrimitive(primitive);
    _attached.delete(id);
  }

  /**
   * 批量同步原语（增量 diff）
   */
  function syncPrimitives(
    current: Array<{ id: string; primitive: ISeriesPrimitive<Time> }>,
  ): void {
    const currentIds = new Set(current.map((p) => p.id));
    for (const id of Array.from(_attached.keys())) {
      if (!currentIds.has(id)) {
        detach(id);
      }
    }
    for (const { id, primitive } of current) {
      if (!_attached.has(id)) {
        attach(id, primitive);
      }
    }
  }

  /**
   * 请求更新（带 RAF 合并）
   */
  function scheduleUpdate(): void {
    if (_pendingUpdate) return;
    _pendingUpdate = true;
    _rafId = requestAnimationFrame(() => {
      _pendingUpdate = false;
      _rafId = null;
      _requestUpdate?.();
    }) as unknown as number;
  }

  /** 立即更新（不等待 RAF） */
  function updateNow(): void {
    _requestUpdate?.();
  }

  /** 分离所有原语并清理 */
  function detachAll(): void {
    if (!_series) return;
    for (const [, primitive] of _attached) {
      _series.detachPrimitive(primitive);
    }
    _attached.clear();
  }

  /** 释放所有资源 */
  function dispose(): void {
    detachAll();
    if (_rafId !== null) {
      cancelAnimationFrame(_rafId);
      _rafId = null;
    }
    _series = null;
    _requestUpdate = null;
    _pendingUpdate = false;
  }

  return {
    bind,
    attach,
    detach,
    syncPrimitives,
    scheduleUpdate,
    updateNow,
    detachAll,
    dispose,
    getAttachedIds: () => Array.from(_attached.keys()),
    getAttachedCount: () => _attached.size,
  };
}
