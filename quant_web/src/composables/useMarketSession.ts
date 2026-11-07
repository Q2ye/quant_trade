// useMarketSession.ts —— A 股「交易时段」唯一判定入口
//
// ⚠️ 背景（2026-10-11 修复）：
//   此前 `AppHeader.vue` 与 `IndexDetail.vue` **各写一份**时段判定，且实现不一致 ——
//   IndexDetail 只看时钟（`t >= 570 && t <= 900`），**不判周末、不扣午休**
//   ⇒ 周末下午会显示「交易中」。本文件是唯一实现，两处都改为调用它。
//
// ⚠️ 职责切分（单一职责，勿合并）：
//   - 「**哪天**是交易日」= 后端 `/market/trading-calendar`（需要日历表）
//   - 「**现在**是不是交易时段」= 本文件（需要时钟）
//   两者相与才是「交易中」。
//
// ⚠️ 日历降级：接口未返回前 / 接口失败时，只按「周末」判定（与修复前行为一致），
//   不阻塞页面渲染；日历到位后自动收敛为完整判定。

import { computed, onMounted, onUnmounted, ref, type ComputedRef } from "vue";
import marketAPI from "@/api/market";

export type MarketSession =
  | "weekend"
  | "holiday"
  | "pre"
  | "open"
  | "lunch"
  | "closed";

export interface MarketSessionState {
  /** 是否处于连续竞价时段（09:30–11:30 / 13:00–15:00） */
  isOpen: boolean;
  session: MarketSession;
  /** 短文案：交易中 / 未开盘 / 午间休市 / 已收盘 / 休市（周末）/ 休市（非交易日） */
  label: string;
  /** 长文案（页头用）：交易时段: 09:30-11:30 / 13:00-15:00，其余同 label */
  sessionText: string;
  /** 当日所属月份的交易日历是否已就绪（false = 尚未判定法定节假日） */
  calendarReady: boolean;
}

// ---- 交易日历缓存（模块级：多个组件共享，头部每秒刷新不会重复打接口） ----
const dayCache = new Map<string, Set<string>>(); // "YYYY-MM" -> Set<"YYYY-MM-DD">
const inflight = new Map<string, Promise<void>>();

const pad = (n: number) => String(n).padStart(2, "0");
const ym = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
const ymd = (d: Date) => `${ym(d)}-${pad(d.getDate())}`;

/** 确保 anchor 所在月份的交易日历已加载（失败静默降级，不抛错、不阻塞渲染） */
async function ensureMonth(anchor: Date): Promise<void> {
  const key = ym(anchor);
  if (dayCache.has(key)) return;
  const pending = inflight.get(key);
  if (pending) return pending;

  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);

  const task = (async () => {
    try {
      const days = await marketAPI.getTradingCalendar(ymd(first), ymd(last));
      if (Array.isArray(days)) dayCache.set(key, new Set(days));
    } catch {
      // 日历不可用 → 保持「仅周末」降级判定；下次 tick 会重试
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, task);
  return task;
}

export function useMarketSession(): {
  state: ComputedRef<MarketSessionState>;
  /** 手动确保日历就绪（跨月/跨日时由内部自动调用，一般无需外部调用） */
  ensureCalendar: () => Promise<void>;
} {
  const now = ref(new Date());
  let timer: number | undefined;

  const state = computed<MarketSessionState>(() => {
    const d = now.value;
    const weekday = d.getDay();
    const minutes = d.getHours() * 60 + d.getMinutes();

    const monthKey = ym(d);
    const calendarReady = dayCache.has(monthKey);

    // ① 周末（无需日历）
    if (weekday === 0 || weekday === 6) {
      return {
        isOpen: false,
        session: "weekend",
        label: "休市（周末）",
        sessionText: "休市（周末）",
        calendarReady,
      };
    }

    // ② 法定节假日（需日历；未就绪时先按「交易日」放行，就绪后自动纠正）
    const monthDays = dayCache.get(monthKey);
    if (monthDays && !monthDays.has(ymd(d))) {
      return {
        isOpen: false,
        session: "holiday",
        label: "休市（非交易日）",
        sessionText: "休市（非交易日）",
        calendarReady,
      };
    }

    // ③ 时段（纯时钟）
    if (minutes < 570) {
      return { isOpen: false, session: "pre", label: "未开盘", sessionText: "未开盘", calendarReady };
    }
    if (minutes < 690) {
      return {
        isOpen: true,
        session: "open",
        label: "交易中",
        sessionText: "交易时段: 09:30-11:30",
        calendarReady,
      };
    }
    if (minutes < 780) {
      return { isOpen: false, session: "lunch", label: "午间休市", sessionText: "午间休市", calendarReady };
    }
    if (minutes < 900) {
      return {
        isOpen: true,
        session: "open",
        label: "交易中",
        sessionText: "交易时段: 13:00-15:00",
        calendarReady,
      };
    }
    return { isOpen: false, session: "closed", label: "已收盘", sessionText: "已收盘", calendarReady };
  });

  onMounted(() => {
    void ensureMonth(now.value);
    // 30 秒粒度足够（判据精确到分钟）；跨月时补拉新月份日历
    timer = window.setInterval(() => {
      const prev = now.value;
      const next = new Date();
      if (ym(prev) !== ym(next)) void ensureMonth(next);
      now.value = next;
    }, 30_000);
  });

  onUnmounted(() => {
    if (timer !== undefined) window.clearInterval(timer);
  });

  return {
    state,
    ensureCalendar: () => ensureMonth(new Date()),
  };
}
