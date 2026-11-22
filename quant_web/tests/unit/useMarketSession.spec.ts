// useMarketSession.spec.ts — 交易时段唯一判定入口（2026-10-11 修复回归）
//
// ⚠️ 本文件的存在理由：修复前的两处实现在 `vue-tsc` 下**完全合法**（只是逻辑错），
//    静态检查永远抓不到 → 必须用运行时用例钉死。以下三例**直接复现被报告的缺陷**：
//      ① 周末下午 → 旧实现（只看时钟）显示「交易中」，实为「休市（周末）」
//      ② 工作日午休（11:30–13:00）→ 旧实现显示「交易中」，实为「午间休市」
//      ③ 法定节假日 → 旧实现完全无法识别
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { defineComponent, h } from "vue";
import { mount } from "@vue/test-utils";

const { calendarMock } = vi.hoisted(() => ({ calendarMock: vi.fn() }));

vi.mock("@/api/market", () => ({
  default: { getTradingCalendar: calendarMock },
}));

import { useMarketSession } from "@/composables/useMarketSession";

/** 2026-10 真实交易日（取自 `trade_calendar` SSE：10-10/11 为周末、10-01~10-07 为长假） */
const OCT_TRADING_DAYS = [
  "2026-10-08",
  "2026-10-09",
  "2026-10-12",
  "2026-10-13",
];

async function mountAt(nowIso: string) {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(nowIso));

  let stateRef: any = null;
  const Comp = defineComponent({
    setup() {
      stateRef = useMarketSession().state;
      return () => h("div");
    },
  });
  const wrapper = mount(Comp);
  // 冲掉 ensureMonth 的微任务（日历 mock 是 async）
  await vi.advanceTimersByTimeAsync(0);
  return { wrapper, state: () => stateRef.value };
}

beforeEach(() => {
  calendarMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useMarketSession · 时段判定", () => {
  it("① 周末下午 → 休市（周末）—— 修复前显示「交易中」", async () => {
    calendarMock.mockImplementation(async () => OCT_TRADING_DAYS);
    // 2026-10-11 是周日
    const { wrapper, state } = await mountAt("2026-10-11T13:03:00");
    expect(state().session).toBe("weekend");
    expect(state().label).toBe("休市（周末）");
    expect(state().isOpen).toBe(false);
    wrapper.unmount();
  });

  it("② 工作日午休 → 午间休市 —— 修复前显示「交易中」", async () => {
    calendarMock.mockImplementation(async () => OCT_TRADING_DAYS);
    const { wrapper, state } = await mountAt("2026-10-09T12:00:00");
    expect(state().session).toBe("lunch");
    expect(state().label).toBe("午间休市");
    expect(state().isOpen).toBe(false);
    wrapper.unmount();
  });

  it("③ 法定节假日（工作日）→ 休市（非交易日）", async () => {
    calendarMock.mockImplementation(async () => OCT_TRADING_DAYS);
    // 2026-10-05 是周一，但为国庆假日（不在交易日列表内）
    const { wrapper, state } = await mountAt("2026-10-05T10:00:00");
    expect(state().session).toBe("holiday");
    expect(state().label).toBe("休市（非交易日）");
    expect(state().isOpen).toBe(false);
    wrapper.unmount();
  });

  it("④ 交易日盘中 → 交易中（区分上午/下午时段文案）", async () => {
    calendarMock.mockImplementation(async () => OCT_TRADING_DAYS);
    const am = await mountAt("2026-10-09T10:00:00");
    expect(am.state().isOpen).toBe(true);
    expect(am.state().label).toBe("交易中");
    expect(am.state().sessionText).toBe("交易时段: 09:30-11:30");
    am.wrapper.unmount();

    const pm = await mountAt("2026-10-09T14:00:00");
    expect(pm.state().isOpen).toBe(true);
    expect(pm.state().sessionText).toBe("交易时段: 13:00-15:00");
    pm.wrapper.unmount();
  });

  it("⑤ 盘前 / 收盘后", async () => {
    calendarMock.mockImplementation(async () => OCT_TRADING_DAYS);
    const pre = await mountAt("2026-10-09T08:00:00");
    expect(pre.state().session).toBe("pre");
    expect(pre.state().isOpen).toBe(false);
    pre.wrapper.unmount();

    const post = await mountAt("2026-10-09T16:00:00");
    expect(post.state().session).toBe("closed");
    expect(post.state().label).toBe("已收盘");
    post.wrapper.unmount();
  });

  it("⑥ 日历接口失败 → 降级为「仅周末 + 时段」判定，不误报节假日、不抛错", async () => {
    calendarMock.mockRejectedValue(new Error("network down"));
    // 用 12 月（未在上方用例中缓存过）避免模块级日历缓存串扰
    const { wrapper, state } = await mountAt("2026-12-15T10:00:00");
    expect(state().calendarReady).toBe(false);
    expect(state().session).toBe("open");
    expect(state().isOpen).toBe(true);
    wrapper.unmount();
  });
});
