// useTimeCoordinate.spec.ts — 坐标转换 + 脏检查单元测试
import { describe, it, expect, beforeEach } from "vitest";
import { useTimeCoordinate } from "@/composables/useTimeCoordinate";

describe("useTimeCoordinate", () => {
  let tc: ReturnType<typeof useTimeCoordinate>;

  beforeEach(() => {
    tc = useTimeCoordinate();
  });

  describe("toEpochSeconds", () => {
    it("converts 'YYYY-MM-DD' string to epoch seconds", () => {
      const result = tc.toEpochSeconds("2025-01-15");
      // 2025-01-15T00:00:00Z in seconds
      const expected = Math.floor(new Date("2025-01-15T00:00:00Z").getTime() / 1000);
      expect(result).toBe(expected);
    });

    it("returns number time as-is", () => {
      expect(tc.toEpochSeconds(1700000000 as any)).toBe(1700000000);
    });

    it("handles different dates consistently", () => {
      const d1 = tc.toEpochSeconds("2024-09-30");
      const d2 = tc.toEpochSeconds("2024-10-08");
      // 8-day gap (including Oct 1-7 national holiday)
      expect(d2 - d1).toBe(8 * 86400);
    });
  });

  describe("脏检查 (needsRecalc / updateCache)", () => {
    it("initially needs recalc", () => {
      expect(tc.needsRecalc({ from: "2025-01-01", to: "2025-01-31" }, 800)).toBe(true);
    });

    it("does not need recalc for same range and width", () => {
      const range = { from: "2025-01-01" as any, to: "2025-01-31" as any };
      tc.needsRecalc(range, 800);
      tc.updateCache(range, 800);
      expect(tc.needsRecalc(range, 800)).toBe(false);
    });

    it("needs recalc when width changes", () => {
      const range = { from: "2025-01-01" as any, to: "2025-01-31" as any };
      tc.updateCache(range, 800);
      expect(tc.needsRecalc(range, 900)).toBe(true);
    });

    it("needs recalc when visible range changes", () => {
      tc.updateCache({ from: "2025-01-01" as any, to: "2025-01-31" as any }, 800);
      expect(tc.needsRecalc({ from: "2025-02-01" as any, to: "2025-02-28" as any }, 800)).toBe(true);
    });

    it("needs recalc after markDirty", () => {
      const range = { from: "2025-01-01" as any, to: "2025-01-31" as any };
      tc.updateCache(range, 800);
      tc.markDirty();
      expect(tc.needsRecalc(range, 800)).toBe(true);
    });

    it("needs recalc with null range", () => {
      expect(tc.needsRecalc(null, 800)).toBe(true);
    });
  });

  describe("toCoord / timeToX", () => {
    it("returns null when chart is null", () => {
      expect(tc.toCoord(null, null, "2025-01-15", 100)).toBeNull();
      expect(tc.timeToX(null, "2025-01-15")).toBeNull();
    });

    it("returns null when series is null for toCoord", () => {
      // Even with chart, null series → null for toCoord
      expect(tc.toCoord({} as any, null, "2025-01-15", 100)).toBeNull();
    });
  });

  describe("time point with gaps", () => {
    it("timeToEpoch correctly computes gap between pre/post holiday dates", () => {
      // 2024-09-30 (last trading day before National Day) → 2024-10-08 (first after)
      const preHoliday = tc.toEpochSeconds("2024-09-30");
      const postHoliday = tc.toEpochSeconds("2024-10-08");
      expect(postHoliday - preHoliday).toBe(8 * 86400); // 8 calendar days
    });

    it("timeToEpoch correctly handles weekend gap", () => {
      const friday = tc.toEpochSeconds("2025-01-17"); // Friday
      const monday = tc.toEpochSeconds("2025-01-20"); // Monday
      expect(monday - friday).toBe(3 * 86400); // 3 calendar days
    });
  });

  describe("reset", () => {
    it("clears cache and marks dirty", () => {
      const range = { from: "2025-01-01" as any, to: "2025-01-31" as any };
      tc.updateCache(range, 800);
      tc.reset();
      expect(tc.needsRecalc(range, 800)).toBe(true);
    });
  });
});
