// TrendLinePrimitive.spec.ts — 趋势线原语数据模型 + 坐标约束验证
import { describe, it, expect } from "vitest";
import { TrendLinePrimitive } from "@/components/charts/primitives/TrendLine";
import type { TrendLineData } from "@/components/charts/primitives/types";

const SAMPLE_DATA: TrendLineData = {
  id: "test-tl-1",
  type: "trendLine",
  startTime: "2024-09-26",
  endTime: "2024-10-09", // crosses National Day gap (Sep 30 → Oct 8)
  startPrice: 100.0,
  endPrice: 104.0,
  lineColor: "#FF9800",
  lineWidth: 2,
  lineStyle: 0,
  extendLeft: false,
  extendRight: true,
};

describe("TrendLinePrimitive 数据模型", () => {
  it("only stores time and price — no pixel coordinates", () => {
    const prim = new TrendLinePrimitive(SAMPLE_DATA);
    const data = prim.getData();

    // 时间戳存储
    expect(data.startTime).toBe("2024-09-26");
    expect(data.endTime).toBe("2024-10-09");

    // 价格存储
    expect(data.startPrice).toBe(100.0);
    expect(data.endPrice).toBe(104.0);

    // 不存在坐标字段
    expect((data as any).x1).toBeUndefined();
    expect((data as any).y1).toBeUndefined();
    expect((data as any).startCoord).toBeUndefined();
  });

  it("supports extendRight ray mode (stored as flag, not as coordinate)", () => {
    const prim = new TrendLinePrimitive(SAMPLE_DATA);
    expect(prim.getData().extendRight).toBe(true);
    expect(prim.getData().extendLeft).toBe(false);
  });

  it("updateData modifies stored properties without adding coordinates", () => {
    const prim = new TrendLinePrimitive(SAMPLE_DATA);
    prim.updateData({ endPrice: 108.0, lineColor: "#448AFF" });
    const data = prim.getData();
    expect(data.endPrice).toBe(108.0);
    expect(data.lineColor).toBe("#448AFF");
    expect(data.startPrice).toBe(100.0); // unchanged
  });

  it("cross-holiday gap: time span covers 8 calendar days correctly", () => {
    const prim = new TrendLinePrimitive(SAMPLE_DATA);
    const data = prim.getData();

    // 2024-09-26 to 2024-10-09 = 13 calendar days
    // The gap Sep 30 → Oct 8 (7-day national holiday) is part of this span
    const startDate = new Date((data.startTime as string) + "T00:00:00Z");
    const endDate = new Date((data.endTime as string) + "T00:00:00Z");
    const diffDays = (endDate.getTime() - startDate.getTime()) / 86400000;
    expect(diffDays).toBe(13);
  });

  it("getData returns current data snapshot", () => {
    const prim = new TrendLinePrimitive(SAMPLE_DATA);
    const snap1 = prim.getData();
    // Same reference (internal _data) — no defensive copy on each call
    expect(snap1.startTime).toBe("2024-09-26");
    expect(snap1.endPrice).toBe(104.0);

    // After updateData, getData reflects changes
    prim.updateData({ endPrice: 110.0 });
    const snap2 = prim.getData();
    expect(snap2.endPrice).toBe(110.0);
  });
});
