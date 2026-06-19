// useVisibilityCulling.ts — 视口可见性裁剪
// 根据当前 visibleTimeRange 过滤原语，跳过不可见元素的 draw() 调用
import { type Time } from "lightweight-charts";

/** 可见性裁剪的基础接口（原语数据需实现） */
export interface CullablePrimitive {
  /** 原语的参考时间 */
  referenceTime: Time;
  /** 是否始终可见（如延长射线），跳过裁剪 */
  alwaysVisible?: boolean;
  /** 可选的结束时间（趋势线等有跨度） */
  endTime?: Time;
}

/** 可见性裁剪结果 */
export interface CullingResult<T extends CullablePrimitive> {
  visible: T[];
  hidden: T[];
}

/**
 * 将 epoch 秒数转为数字（兼容字符串日期）
 */
function timeToNumber(t: Time): number {
  if (typeof t === "number") return t;
  if (typeof t === "string") {
    return Math.floor(new Date(t + "T00:00:00Z").getTime() / 1000);
  }
  return Math.floor(new Date(String(t)).getTime() / 1000);
}

export function useVisibilityCulling() {
  /**
   * 裁剪原语列表，只保留时间在 visibleRange 内的
   * @param primitives - 待裁剪的原语列表
   * @param visibleRange - 当前可见时间范围 { from, to } (可为 null)
   * @param paddingRatio - 视口外扩展比例（默认 0.1 = 视口两侧各扩展 10%）
   * @returns { visible, hidden }
   */
  function cull<T extends CullablePrimitive>(
    primitives: T[],
    visibleRange: { from: Time; to: Time } | null,
    paddingRatio: number = 0.1,
  ): CullingResult<T> {
    if (!visibleRange || primitives.length === 0) {
      return { visible: primitives, hidden: [] };
    }

    const rangeFrom = timeToNumber(visibleRange.from);
    const rangeTo = timeToNumber(visibleRange.to);
    const rangeSpan = rangeTo - rangeFrom;
    const paddedFrom = rangeFrom - rangeSpan * paddingRatio;
    const paddedTo = rangeTo + rangeSpan * paddingRatio;

    const visible: T[] = [];
    const hidden: T[] = [];

    for (const p of primitives) {
      // 始终可见的原语跳过裁剪
      if (p.alwaysVisible) {
        visible.push(p);
        continue;
      }

      const pFrom = timeToNumber(p.referenceTime);
      const pTo = p.endTime ? timeToNumber(p.endTime) : pFrom;

      // 原语的时间区间与视口区间有交集 → 可见
      if (pTo >= paddedFrom && pFrom <= paddedTo) {
        visible.push(p);
      } else {
        hidden.push(p);
      }
    }

    return { visible, hidden };
  }

  /**
   * 检查单个原语是否在可见范围内
   */
  function isVisible(
    primitive: CullablePrimitive,
    visibleRange: { from: Time; to: Time } | null,
  ): boolean {
    if (!visibleRange) return true;
    if (primitive.alwaysVisible) return true;

    const rangeFrom = timeToNumber(visibleRange.from);
    const rangeTo = timeToNumber(visibleRange.to);
    const pFrom = timeToNumber(primitive.referenceTime);
    const pTo = primitive.endTime ? timeToNumber(primitive.endTime) : pFrom;

    return pTo >= rangeFrom && pFrom <= rangeTo;
  }

  return {
    cull,
    isVisible,
  };
}
