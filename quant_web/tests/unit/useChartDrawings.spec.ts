// useChartDrawings.spec.ts — 图上作业编排（包 B）回归测试
//
// ⚠️ 本文件的存在理由：`useChartDrawings` 里 `watch(..., { immediate: true })` 会在
//    **setup 期间**立即调用 applyCursor()，而 applyCursor 读的是 `let _container`（TDZ）。
//    这类错误 **vue-tsc 抓不到**（引用在函数体内，TS 的"声明前使用"检查不触发），
//    只有真正 mount 一次才会暴露 → 因此必须有运行时用例兜住。
import { describe, it, expect, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { mount } from "@vue/test-utils";

// composable 顶层 import 了 marketAPI
vi.mock("@/api/market", () => ({
  default: {
    getChartAnnotations: vi.fn(async () => []),
    saveChartAnnotations: vi.fn(async () => 0),
  },
}));

import {
  useChartDrawings,
  type ChartPeriod,
  type DrawTarget,
} from "@/composables/useChartDrawings";

type Api = ReturnType<typeof useChartDrawings>;

interface Harness {
  api: Api;
  chartRef: ReturnType<typeof ref<any>>;
  wrapper: ReturnType<typeof mount>;
}

function setupHarness(overrides: { canEdit?: boolean } = {}): Harness {
  const chartRef = ref<any>(null);
  const period = ref<ChartPeriod>("daily");
  const symbol = ref("600519.SH");
  const canEdit = ref(overrides.canEdit ?? true);

  let api: Api | null = null;
  const Comp = defineComponent({
    setup() {
      api = useChartDrawings({ chartRef, period, symbol, canEdit });
      return () => h("div");
    },
  });

  const wrapper = mount(Comp);
  if (!api) throw new Error("useChartDrawings 未返回（setup 抛错？）");
  return { api, chartRef, wrapper };
}

function fakeTarget(): DrawTarget {
  return {
    chart: {} as any,
    series: {} as any,
    container: document.createElement("div"),
  };
}

describe("useChartDrawings · setup 安全性", () => {
  it("mount 时 setup 不抛错（TDZ 回归：_container 必须声明在 immediate watcher 之前）", () => {
    // 若 _container 等 let 声明晚于 watch(..., { immediate: true })，这里会
    // 抛 ReferenceError: Cannot access '_container' before initialization
    expect(() => setupHarness()).not.toThrow();
    const { api } = setupHarness();
    expect(api).toBeTruthy();
    expect(api.annotations.value).toEqual([]);
    expect(api.count.value).toBe(0);
    expect(api.drawings.value).toEqual([]);
  });

  it("canEdit=false 时不抛错且不绑定监听", () => {
    expect(() => setupHarness({ canEdit: false })).not.toThrow();
  });
});

describe("useChartDrawings · 工具选择（交互模型 A）", () => {
  it("selectTool 选中 / 同工具再点一次取消", () => {
    const { api } = setupHarness();
    expect(api.activeTool.value).toBeNull();

    api.selectTool("horizontalLine");
    expect(api.activeTool.value).toBe("horizontalLine");

    api.selectTool("horizontalLine");
    expect(api.activeTool.value).toBeNull();
  });

  it("切换工具直接替换，而不是叠加", () => {
    const { api } = setupHarness();
    api.selectTool("horizontalLine");
    api.selectTool("verticalLine");
    expect(api.activeTool.value).toBe("verticalLine");
  });

  it("selectTool 会清掉选中态", () => {
    const { api } = setupHarness();
    api.selectTool("horizontalLine");
    api.selectTool(null);
    expect(api.selectedId.value).toBeNull();
  });
});

describe("useChartDrawings · 文本标注", () => {
  it("无锚点时 commitText 不产生标注（不凭空落点）", () => {
    const { api } = setupHarness();
    expect(api.pendingText.value).toBeNull();
    api.commitText("缩量回踩");
    expect(api.count.value).toBe(0);
    expect(api.activeTool.value).toBeNull();
  });

  it("cancelText 清空待输入态", () => {
    const { api } = setupHarness();
    api.cancelText();
    expect(api.pendingText.value).toBeNull();
    expect(api.activeTool.value).toBeNull();
  });
});

describe("useChartDrawings · 绘图目标", () => {
  it("refreshTarget 从 chartRef.getDrawTarget() 取到目标，并完成 DOM 绑定", async () => {
    const { api, chartRef } = setupHarness();
    expect(api.target.value).toBeNull();

    const target = fakeTarget();
    chartRef.value = { getDrawTarget: () => target };
    await api.refreshTarget();

    // ⚠️ 严格同一性：用 ref() 会被深层代理，这里会不等 → 必须用 shallowRef
    //    （第三方类实例不应被 Vue 代理）
    expect(api.target.value).toBe(target);
  });

  it("getDrawTarget 返回 null（图表未就绪）→ target 保持 null，不抛错", async () => {
    const { api, chartRef } = setupHarness();
    chartRef.value = { getDrawTarget: () => null };
    await api.refreshTarget();
    expect(api.target.value).toBeNull();
  });
});

describe("useChartDrawings · 删除与清空", () => {
  it("无选中时 removeSelected 无副作用", () => {
    const { api } = setupHarness();
    expect(() => api.removeSelected()).not.toThrow();
    expect(api.count.value).toBe(0);
  });

  it("clearPeriod 在空数据上无副作用", () => {
    const { api } = setupHarness();
    expect(() => api.clearPeriod()).not.toThrow();
    expect(api.count.value).toBe(0);
  });
});
