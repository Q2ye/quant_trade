// types/index.ts — 统一类型导出入口
// 扁平化后的所有类型统一从此文件导出

// ============================================================================
// 通用基础类型（枚举、API 基类、实体基类、工具类型）
// ============================================================================
export * from "./common";

// ============================================================================
// 领域 API 类型
// ============================================================================
export * from "./api-backtest";
export * from "./api-basket";
export * from "./api-data";
export * from "./api-performance";
export * from "./api-shared";
export * from "./api-strategy";
export * from "./api-system";
export * from "./api-trade";
export * from "./api-user";
export * from "./api-websocket";

// ============================================================================
// 领域实体类型
// ============================================================================
export * from "./entities-basket";
export * from "./entities-dashboard";
export * from "./entities-data";
export * from "./entities-performance";
export * from "./entities-risk";
export * from "./entities-strategy";
export * from "./entities-system";
export * from "./entities-trading";
export * from "./entities-user";

// ============================================================================
// 工具类型
// ============================================================================
export * from "./utils-charts";
export * from "./utils-form";
export * from "./utils-table";
export * from "./utils-vuex";
export * from "./utils-userConverter";

// ============================================================================
// 状态类型
// ============================================================================
export * from "./state-root-state";
export * from "./state-basket-state";
export * from "./state-dashboard-state";
export * from "./state-data-state";
export * from "./state-layout-state";
export * from "./state-performance-state";
export * from "./state-risk-state";
export * from "./state-strategy-state";
export * from "./state-strategy-studio-state";
export * from "./state-system-state";
export * from "./state-trade-state";
export * from "./state-user-state";
