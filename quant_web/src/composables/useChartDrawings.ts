// useChartDrawings.ts — 图上作业编排（包 B）
//
// 统一管理 4 类绘图工具（趋势线 / 水平线 / 垂直线 / 文本标注）的：
//   ① 绘制状态编排（趋势线复用 useTrendLineDraw；其余三类为单击落点）
//   ② 选中 / 删除 / 清空（画布命中测试，像素距离判定）
//   ③ 持久化读写（user_preferences.display_settings.chart_annotations，按标的存、按周期过滤）
//
// 两条硬契约：
//   · 标注 id **必须以 `draw-` 开头** —— LightweightKLine.syncDrawings 仅 detach 该前缀，
//     否则删除后的标注会残留在画布上（幽灵标注）。
//   · time 一律归一化为 'YYYY-MM-DD'（coordinateToTime 可能返回 BusinessDay 对象）。
//
// 交互模型：选一次工具画一条，画完自动回 idle（见《包B-图上作业-开发路径说明》§七-1）。
import { computed, nextTick, onBeforeUnmount, ref, shallowRef, watch, type Ref } from "vue";
import {
  type IChartApi,
  type ISeriesApi,
  type ISeriesPrimitive,
  type SeriesType,
  type Time,
} from "lightweight-charts";
import {
  AnnotationLabelPrimitive,
  HorizontalLinePrimitive,
  TrendLinePrimitive,
  VerticalLinePrimitive,
  type AnnotationLabelData,
  type HorizontalLineData,
  type TrendLineData,
  type VerticalLineData,
} from "@/components/charts/primitives";
import { useTrendLineDraw } from "@/composables/useTrendLineDraw";
import { DRAW_COLORS, DRAW_DEFAULTS } from "@/components/charts/chart-palette";
import marketAPI from "@/api/market";

export type DrawingTool =
  | "trendLine"
  | "horizontalLine"
  | "verticalLine"
  | "annotationLabel";

/** 单击落点的工具（趋势线走拖拽，不在此列） */
type ClickTool = Exclude<DrawingTool, "trendLine">;

export type ChartPeriod = "daily" | "weekly" | "monthly";

/** 绘制目标：由 LightweightKLine.getDrawTarget() 提供 */
export interface DrawTarget {
  chart: IChartApi;
  series: ISeriesApi<SeriesType, Time>;
  container: HTMLElement;
}

type AnnotationBase = { id: string; period: ChartPeriod };

/** 标注 = 原语数据 + 周期归属（周期字段不参与渲染，仅用于隔离日/周/月） */
export type ChartAnnotation =
  | (TrendLineData & AnnotationBase)
  | (HorizontalLineData & AnnotationBase)
  | (VerticalLineData & AnnotationBase)
  | (AnnotationLabelData & AnnotationBase);

/** 命中容差（像素） */
const HIT_TOLERANCE_PX = 6;
/** 文本标注的命中框 */
const LABEL_HIT_W = 48;
const LABEL_HIT_H = 14;
/** mousedown→click 位移超过此值视为拖拽（平移图表），不做选择 */
const CLICK_MOVE_TOLERANCE_PX = 5;

/** 生成标注 id —— 前缀 `draw-` 是硬契约，见文件头 */
function newAnnotationId(tool: DrawingTool): string {
  return `draw-${tool}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

/** 把 lightweight-charts 的 Time 归一化为 'YYYY-MM-DD' */
function normalizeTime(time: Time): string {
  if (typeof time === "string") return time.slice(0, 10);
  if (typeof time === "number") {
    const d = new Date(time * 1000);
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const dd = String(d.getUTCDate()).padStart(2, "0");
    return `${d.getUTCFullYear()}-${mm}-${dd}`;
  }
  const bd = time as { year: number; month: number; day: number };
  return `${bd.year}-${String(bd.month).padStart(2, "0")}-${String(
    bd.day,
  ).padStart(2, "0")}`;
}

/** 标注数据 → 绘制原语（选中态用高亮色） */
function toPrimitive(
  annotation: ChartAnnotation,
  selected: boolean,
): ISeriesPrimitive<Time> {
  const width = selected ? DRAW_DEFAULTS.selectedLineWidth : DRAW_DEFAULTS.lineWidth;
  switch (annotation.type) {
    case "trendLine":
      return new TrendLinePrimitive({
        ...annotation,
        lineColor: selected ? DRAW_COLORS.selected : annotation.lineColor,
        lineWidth: width,
      });
    case "horizontalLine":
      return new HorizontalLinePrimitive({
        ...annotation,
        color: selected ? DRAW_COLORS.selected : annotation.color,
        lineWidth: width,
      });
    case "verticalLine":
      return new VerticalLinePrimitive({
        ...annotation,
        color: selected ? DRAW_COLORS.selected : annotation.color,
        lineWidth: width,
      });
    default:
      return new AnnotationLabelPrimitive({
        ...annotation,
        borderColor: selected ? DRAW_COLORS.selected : annotation.borderColor,
      });
  }
}

/** 点到线段的像素距离 */
function pointToSegmentDistance(
  px: number,
  py: number,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return Math.hypot(px - x1, py - y1);
  let t = ((px - x1) * dx + (py - y1) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

export interface UseChartDrawingsOptions {
  /** K 线容器组件引用（该组件需实现 getDrawTarget()） */
  chartRef: Readonly<Ref<any>>;
  /** 当前周期 */
  period: Readonly<Ref<ChartPeriod>>;
  /** 当前标的 */
  symbol: Readonly<Ref<string>>;
  /** 是否可编辑（预留：权限 / 只读策略 → false） */
  canEdit: Readonly<Ref<boolean>>;
}

export function useChartDrawings(options: UseChartDrawingsOptions) {
  const { chartRef, period, symbol, canEdit } = options;

  /**
   * 绘制目标（由 refreshTarget 从 chartRef 取，容器重建后会失效）
   *
   * ⚠️ 必须用 `shallowRef`：`{ chart, series, container }` 是第三方类实例
   *    （lightweight-charts 的 IChartApi / ISeriesApi + DOM 节点）。用 `ref()` 会被
   *    Vue 做**深层响应式代理** —— 对一个只读不改的外部句柄毫无收益，还要每次
   *    方法调用过一层 Proxy；且库一旦改用 `#private` 字段，代理会导致
   *    "Cannot read private member" 直接抛错（v5.2.0 实测未用，属隐患）。
   */
  const target = shallowRef<DrawTarget | null>(null);

  // ---- DOM 监听句柄（单击类工具 + 命中选择）----
  // ⚠️ 必须声明在**任何 watcher 之前**：下方 `watch(..., { immediate: true })`
  //    会在 setup 期间立即调用 applyCursor()，而 `let` 存在 TDZ ——
  //    声明晚于该 watch 会抛 "Cannot access '_container' before initialization"。
  //    （该用例已由 tests/unit/useChartDrawings.spec.ts 兜住）
  let _container: HTMLElement | null = null;
  let _onMouseDown: ((e: MouseEvent) => void) | null = null;
  let _onClick: ((e: MouseEvent) => void) | null = null;
  let _onKeyDown: ((e: KeyboardEvent) => void) | null = null;
  let _downX = 0;
  let _downY = 0;

  /**
   * 取/重取绘图目标。
   * ⚠️ 容器带 `:key`（或 v-if）会在周期/标的切换时销毁重建 → target 必须重取；
   *    首次挂载时图表实例可能尚未创建 → 有限次重试（≤10 帧）后放弃。
   */
  async function refreshTarget(attempt = 0): Promise<void> {
    await nextTick();
    const t = (chartRef.value?.getDrawTarget?.() ?? null) as DrawTarget | null;
    if (t) {
      target.value = t;
      return;
    }
    target.value = null;
    if (attempt < 10) {
      requestAnimationFrame(() => void refreshTarget(attempt + 1));
    }
  }

  /** 当前标的的**全部周期**标注（持久化单位） */
  const all = ref<ChartAnnotation[]>([]);
  const activeTool = ref<DrawingTool | null>(null);
  const selectedId = ref<string | null>(null);
  /** 文本工具：等待输入的时间/价格锚点 */
  const pendingText = ref<{ time: Time; price: number } | null>(null);

  const loading = ref(false);
  const loadError = ref(false);
  const saveError = ref(false);
  const saving = ref(false);

  /** 当前周期可见的标注 */
  const current = computed(() =>
    all.value.filter((a) => a.period === period.value),
  );
  const count = computed(() => current.value.length);
  const drawings = computed<ISeriesPrimitive<Time>[]>(() =>
    current.value.map((a) => toPrimitive(a, a.id === selectedId.value)),
  );

  // ---------------------------------------------------------------- 持久化
  async function persist(): Promise<void> {
    if (!symbol.value) return;
    saveError.value = false;
    saving.value = true;
    try {
      await marketAPI.saveChartAnnotations(symbol.value, all.value);
    } catch (e) {
      // 本地状态保留不丢，仅提示失败（用户可重试）
      saveError.value = true;
      console.error("[useChartDrawings] 保存标注失败:", e);
    } finally {
      saving.value = false;
    }
  }

  async function load(): Promise<void> {
    if (!symbol.value) {
      all.value = [];
      return;
    }
    loading.value = true;
    loadError.value = false;
    try {
      const items = await marketAPI.getChartAnnotations(symbol.value);
      all.value = Array.isArray(items) ? (items as ChartAnnotation[]) : [];
    } catch (e) {
      // 读取失败 → 降级为本地空态，但把 loadError 置位供 UI 提示
      loadError.value = true;
      all.value = [];
      console.error("[useChartDrawings] 读取标注失败:", e);
    } finally {
      loading.value = false;
    }
  }

  // ------------------------------------------------------- 坐标换算（像素↔值）
  function pointToTimePrice(e: MouseEvent): { time: Time; price: number } | null {
    const t = target.value;
    if (!t) return null;
    const rect = t.container.getBoundingClientRect();
    const time = t.chart.timeScale().coordinateToTime(e.clientX - rect.left);
    const price = t.series.coordinateToPrice(e.clientY - rect.top);
    if (time === null || price === null) return null;
    return { time: normalizeTime(time), price: Number(price) };
  }

  function priceToY(price: number): number | null {
    const t = target.value;
    if (!t) return null;
    const y = t.series.priceToCoordinate(price);
    return y === null ? null : Number(y);
  }

  function timeToX(time: Time): number | null {
    const t = target.value;
    if (!t) return null;
    const x = t.chart.timeScale().timeToCoordinate(time);
    return x === null ? null : Number(x);
  }

  // ------------------------------------------------------------------ 命中
  /** 返回命中的标注 id（取最近者），未命中 → null */
  function hitTest(px: number, py: number): string | null {
    let hitId: string | null = null;
    let hitDistance = Infinity;

    for (const a of current.value) {
      let distance: number | null = null;

      if (a.type === "horizontalLine") {
        const y = priceToY(a.price);
        if (y !== null) distance = Math.abs(py - y);
      } else if (a.type === "verticalLine") {
        const x = timeToX(a.time);
        if (x !== null) distance = Math.abs(px - x);
      } else if (a.type === "trendLine") {
        const p1 = timeToX(a.startTime);
        const q1 = priceToY(a.startPrice);
        const p2 = timeToX(a.endTime);
        const q2 = priceToY(a.endPrice);
        if (p1 !== null && q1 !== null && p2 !== null && q2 !== null) {
          distance = pointToSegmentDistance(px, py, p1, q1, p2, q2);
        }
      } else {
        const x = timeToX(a.time);
        const y = priceToY(a.price);
        if (
          x !== null &&
          y !== null &&
          Math.abs(px - x) <= LABEL_HIT_W &&
          Math.abs(py - y) <= LABEL_HIT_H
        ) {
          distance = Math.hypot(px - x, py - y);
        }
      }

      if (distance !== null && distance <= HIT_TOLERANCE_PX && distance < hitDistance) {
        hitDistance = distance;
        hitId = a.id;
      }
    }
    return hitId;
  }

  // -------------------------------------------------------------- 创建标注
  function createAt(
    tool: ClickTool,
    pt: { time: Time; price: number },
  ): ChartAnnotation {
    const base = { id: newAnnotationId(tool), period: period.value };
    if (tool === "horizontalLine") {
      return {
        ...base,
        type: "horizontalLine",
        price: pt.price,
        color: DRAW_COLORS.horizontalLine,
        lineWidth: DRAW_DEFAULTS.lineWidth,
        lineStyle: DRAW_DEFAULTS.lineStyle,
      };
    }
    if (tool === "verticalLine") {
      return {
        ...base,
        type: "verticalLine",
        time: pt.time,
        color: DRAW_COLORS.verticalLine,
        lineWidth: DRAW_DEFAULTS.lineWidth,
        lineStyle: DRAW_DEFAULTS.lineStyle,
      };
    }
    return {
      ...base,
      type: "annotationLabel",
      time: pt.time,
      price: pt.price,
      text: "",
      color: DRAW_COLORS.annotationLabel,
      fontSize: 12,
      fontFamily: "inherit",
      backgroundColor: DRAW_COLORS.annotationBg,
    };
  }

  // ------------------------------------------------- 趋势线（复用既有状态机）
  const trendLine = useTrendLineDraw({
    color: DRAW_COLORS.trendLine,
    lineWidth: DRAW_DEFAULTS.lineWidth,
    lineStyle: DRAW_DEFAULTS.lineStyle,
  });

  // 工具/目标/可编辑性变化 → 武装或解除趋势线状态机
  watch(
    [activeTool, target, canEdit],
    () => {
      const t = target.value;
      if (activeTool.value === "trendLine" && t && canEdit.value) {
        trendLine.activate(t.chart, t.series, t.container);
      } else {
        trendLine.deactivate();
      }
      applyCursor();
    },
    { immediate: true },
  );

  // 趋势线落定 → 转成标注
  watch(trendLine.state, (state) => {
    if (state !== "done") return;
    const data = trendLine.previewData.value;
    trendLine.consumePreview(); // 内部 deactivate → idle，供下一条重新 activate
    activeTool.value = null; // 交互模型 A：画一条即回 idle
    if (!data) return;
    all.value = [
      ...all.value,
      { ...data, period: period.value } as ChartAnnotation,
    ];
    void persist();
  });

  onBeforeUnmount(() => {
    trendLine.dispose();
  });

  // -------------------------------------------------- DOM 监听（单击类工具）
  // 句柄声明见上方"DOM 监听句柄"块（必须在 watcher 之前）

  function applyCursor(): void {
    if (!_container) return;
    if (!canEdit.value || activeTool.value === null) {
      _container.style.cursor = "";
    } else if (activeTool.value !== "trendLine") {
      _container.style.cursor = "crosshair";
    }
    // 趋势线激活时由 useTrendLineDraw 自行设置光标，此处不覆盖
  }

  function handleClick(e: MouseEvent): void {
    if (!canEdit.value || !_container) return;
    const tool = activeTool.value;

    // 趋势线由状态机处理
    if (tool === "trendLine") return;

    const pt = pointToTimePrice(e);
    if (!pt) return;

    if (tool) {
      if (tool === "annotationLabel") {
        pendingText.value = pt; // 交给工具条弹输入框
        return;
      }
      all.value = [...all.value, createAt(tool, pt)];
      activeTool.value = null; // 模型 A
      void persist();
      return;
    }

    // 无工具 → 选择
    const rect = _container.getBoundingClientRect();
    selectedId.value = hitTest(e.clientX - rect.left, e.clientY - rect.top);
  }

  function handleKeyDown(e: KeyboardEvent): void {
    if (e.key !== "Escape") return;
    if (activeTool.value) {
      selectTool(null);
    } else if (selectedId.value) {
      selectedId.value = null;
    }
  }

  function unbind(): void {
    if (_container) {
      if (_onMouseDown) _container.removeEventListener("mousedown", _onMouseDown);
      if (_onClick) _container.removeEventListener("click", _onClick);
    }
    if (_onKeyDown) window.removeEventListener("keydown", _onKeyDown);
    _container = null;
    _onMouseDown = null;
    _onClick = null;
    _onKeyDown = null;
  }

  /**
   * 绑定监听。
   * ⚠️ StockDetail 的 K 线容器带 `:key="kPeriod"` → 切周期会销毁重建，
   *    target 随之变化，必须在此重绑，否则切一次周期绘图即静默失效。
   */
  function bind(): void {
    const t = target.value;
    if (!t || !canEdit.value) {
      unbind();
      return;
    }
    if (_container === t.container) {
      applyCursor();
      return;
    }
    unbind();

    _container = t.container;
    _onMouseDown = (e: MouseEvent) => {
      _downX = e.clientX;
      _downY = e.clientY;
    };
    _onClick = (e: MouseEvent) => {
      // 平移图表也会触发 click → 位移超阈值视为拖拽
      if (
        Math.abs(e.clientX - _downX) > CLICK_MOVE_TOLERANCE_PX ||
        Math.abs(e.clientY - _downY) > CLICK_MOVE_TOLERANCE_PX
      ) {
        return;
      }
      handleClick(e);
    };
    _onKeyDown = handleKeyDown;

    _container.addEventListener("mousedown", _onMouseDown);
    _container.addEventListener("click", _onClick);
    window.addEventListener("keydown", _onKeyDown);
    applyCursor();
  }

  // 容器实例变化（:key / v-if 导致的重建）→ 自动重取目标，页面无需自行 watch
  watch(chartRef, () => void refreshTarget());

  watch([target, canEdit], bind, { immediate: true });
  onBeforeUnmount(unbind);

  // -------------------------------------------------------------- 对外动作
  function selectTool(tool: DrawingTool | null): void {
    selectedId.value = null;
    pendingText.value = null;
    activeTool.value = activeTool.value === tool ? null : tool;
  }

  function removeSelected(): void {
    if (!selectedId.value) return;
    all.value = all.value.filter((a) => a.id !== selectedId.value);
    selectedId.value = null;
    void persist();
  }

  /** 清空**当前周期**的标注 */
  function clearPeriod(): void {
    all.value = all.value.filter((a) => a.period !== period.value);
    selectedId.value = null;
    void persist();
  }

  function commitText(text: string): void {
    const pt = pendingText.value;
    pendingText.value = null;
    const value = (text || "").trim();
    if (!pt || !value) {
      activeTool.value = null;
      return;
    }
    all.value = [
      ...all.value,
      { ...createAt("annotationLabel", pt), text: value } as ChartAnnotation,
    ];
    activeTool.value = null;
    void persist();
  }

  function cancelText(): void {
    pendingText.value = null;
    activeTool.value = null;
  }

  watch(symbol, () => {
    selectedId.value = null;
    activeTool.value = null;
    void load();
  });

  return {
    // 状态
    target,
    refreshTarget,
    annotations: all,
    drawings,
    count,
    loading,
    loadError,
    saveError,
    saving,
    activeTool,
    selectedId,
    pendingText,
    // 动作
    load,
    persist,
    selectTool,
    removeSelected,
    clearPeriod,
    commitText,
    cancelText,
  };
}
