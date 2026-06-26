// quant_web/src/store/modules/risk.ts
// 风险管理 Vuex 模块
import { Module } from "vuex";
import { RootState, RiskState } from "@/types";
import riskAPI from "@/api/risk";
import type { RiskRule, RiskEvent, RiskAlert, RiskMetricsData } from "@/api/risk";

const riskModule: Module<RiskState, RootState> = {
  namespaced: true,
  state: {
    riskRules: {
      rules: [],
      editingRule: null,
    },
    realTimeMonitoring: {
      accountRisk: {
        totalRisk: 0,
        positionRisk: 0,
        concentrationRisk: 0,
        liquidityRisk: 0,
      },
      strategyRisks: new Map(),
      marketRisk: {
        volatility: 0,
        correlation: 0,
        sentiment: 0,
      },
    },
    riskEvents: {
      events: [],
      statistics: {
        today: 0,
        critical: 0,
        unresolved: 0,
      },
    },
    blacklist: {
      stocks: [],
    },
    riskReports: {
      daily: null,
      weekly: null,
      monthly: null,
    },
    loading: {
      rules: false,
      monitoring: false,
      events: false,
      blacklist: false,
    },
  },

  mutations: {
    SET_RULES(state, rules: RiskState["riskRules"]["rules"]) {
      state.riskRules.rules = rules;
    },
    SET_EVENTS(state, events: RiskState["riskEvents"]["events"]) {
      state.riskEvents.events = events;
    },
    SET_BLACKLIST(state, blacklist: RiskState["blacklist"]["stocks"]) {
      state.blacklist.stocks = blacklist;
    },
    SET_CURRENT_RULE(state, rule: RiskState["riskRules"]["editingRule"]) {
      state.riskRules.editingRule = rule;
    },
    ADD_EVENT(state, event: RiskState["riskEvents"]["events"][0]) {
      state.riskEvents.events.unshift(event);
      if (state.riskEvents.events.length > 1000) {
        state.riskEvents.events = state.riskEvents.events.slice(0, 1000);
      }
    },
    SET_LOADING(state, loading: Partial<RiskState["loading"]>) {
      state.loading = { ...state.loading, ...loading };
    },
    SET_MONITORING(state, data: RiskState["realTimeMonitoring"]["accountRisk"]) {
      state.realTimeMonitoring.accountRisk = data;
    },
    UPDATE_EVENT_STATISTICS(state) {
      const now = new Date().toISOString().split("T")[0];
      state.riskEvents.statistics = {
        today: state.riskEvents.events.filter((event) =>
          event.timestamp.startsWith(now),
        ).length,
        critical: state.riskEvents.events.filter(
          (event) => event.level === "critical",
        ).length,
        unresolved: state.riskEvents.events.filter(
          (event) => !event.actionTaken,
        ).length,
      };
    },
  },

  actions: {
    // ==================== 规则管理 ====================

    async fetchRiskRules({ commit }: any) {
      commit("SET_LOADING", { rules: true });
      try {
        const result = await riskAPI.getRiskRules();
        const rules = (result.rules || []).map((r: RiskRule) => ({
          id: r.name,           // 使用 name 作为唯一标识
          name: r.name,
          type: r.rule_type || "position",
          condition: {},
          action: "alert" as const,
          enabled: r.enabled,
          priority: 1,
          description: r.description || "",
        }));
        commit("SET_RULES", rules);
        return rules;
      } catch (error) {
        console.error("获取风控规则失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { rules: false });
      }
    },

    async toggleRiskRule({ commit, state, dispatch }: any, { ruleName, enabled }: { ruleName: string; enabled: boolean }) {
      try {
        await riskAPI.toggleRiskRule(ruleName, enabled);
        // 更新本地状态
        const rules = state.riskRules.rules.map((r: any) =>
          r.name === ruleName ? { ...r, enabled } : r
        );
        commit("SET_RULES", rules);
        return { rule_name: ruleName, enabled };
      } catch (error) {
        console.error("更新规则状态失败:", error);
        throw error;
      }
    },

    // ==================== 信号检查 ====================

    async checkSignal(_ctx: any, signalData: Record<string, any>) {
      try {
        return await riskAPI.checkSignal(signalData);
      } catch (error) {
        console.error("信号风控检查失败:", error);
        throw error;
      }
    },

    // ==================== 风险指标 ====================

    async fetchRiskMetrics({ commit }: any) {
      commit("SET_LOADING", { monitoring: true });
      try {
        const metrics = await riskAPI.getRiskMetrics();
        commit("SET_MONITORING", {
          totalRisk: metrics.overall_risk_level === "critical" ? 90
            : metrics.overall_risk_level === "warning" ? 60
            : metrics.overall_risk_level === "normal" ? 30 : 0,
          positionRisk: Math.round((metrics.position_ratio || 0) * 100) / 100,
          concentrationRisk: Math.round(((metrics.metrics?.concentration_risk) || 0) * 100) / 100,
          liquidityRisk: Math.round(((metrics.metrics?.liquidity_risk) || 0) * 100) / 100,
        });
        return metrics;
      } catch (error) {
        console.error("获取风险指标失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { monitoring: false });
      }
    },

    // ==================== 风险事件 ====================

    async fetchRiskEvents({ commit }: any, params?: { level?: string; page?: number; page_size?: number }) {
      commit("SET_LOADING", { events: true });
      try {
        const result = await riskAPI.getRiskEvents(params);
        const items = result.items || [];
        const events = items.map((e: RiskEvent) => ({
          id: String(e.id || ""),
          ruleId: e.rule_name || "",
          strategyId: e.signal_data?.strategy_id || "",
          type: e.event_type || "",
          level: (e.level === "critical" ? "critical"
            : e.level === "warning" ? "error"
            : e.level === "normal" ? "info"
            : "info") as "info" | "warning" | "error" | "critical",
          message: e.message || "",
          triggerValue: {
            current_value: e.current_value,
            threshold_value: e.threshold_value,
            metric_name: e.metric_name,
            ...(e.signal_data || {}),
          },
          actionTaken: "",
          timestamp: e.created_at || new Date().toISOString(),
        }));
        commit("SET_EVENTS", events);
        commit("UPDATE_EVENT_STATISTICS");
        return { items: events, pagination: result.pagination };
      } catch (error) {
        console.error("获取风险事件失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { events: false });
      }
    },

    // ==================== 告警 ====================

    async fetchRiskAlerts(_ctx: any, params?: { alert_level?: string }) {
      try {
        const result = await riskAPI.getRiskAlerts(params);
        return result.items || [];
      } catch (error) {
        console.error("获取风险告警失败:", error);
        throw error;
      }
    },

    async acknowledgeAlert(_ctx: any, alertId: string) {
      try {
        return await riskAPI.acknowledgeRiskAlert(alertId);
      } catch (error) {
        console.error("确认告警失败:", error);
        throw error;
      }
    },

    // ==================== 阈值管理 ====================

    async fetchThresholds() {
      try {
        const result = await riskAPI.getThresholds();
        return result.thresholds || [];
      } catch (error) {
        console.error("获取阈值失败:", error);
        throw error;
      }
    },

    async updateThreshold(_ctx: any, { metricName, data }: { metricName: string; data: any }) {
      try {
        return await riskAPI.updateThreshold(metricName, data);
      } catch (error) {
        console.error("更新阈值失败:", error);
        throw error;
      }
    },

    // ==================== 黑名单 ====================

    async fetchBlacklist({ commit }: any) {
      commit("SET_LOADING", { blacklist: true });
      try {
        const result = await riskAPI.getRiskRules();
        const blacklistRule = (result.rules || []).find(
          (r: RiskRule) => r.rule_type === "blacklist" || r.rule_type === "market_blacklist" || r.rule_type === "sector_blacklist"
        );
        // 黑名单股票存储在规则的 condition.symbols 中
        const symbols: string[] = blacklistRule ? [] : [];
        const stocks = symbols.map((symbol: string) => ({
          symbol,
          name: symbol,  // 名称由视图层从股票 API 查询
          reason: blacklistRule?.rule_type || "blacklist",
          addedDate: new Date().toISOString().split("T")[0],
          enabled: blacklistRule?.enabled ?? true,
        }));
        commit("SET_BLACKLIST", stocks);
        return stocks;
      } catch (error) {
        console.error("获取黑名单失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { blacklist: false });
      }
    },

    // ==================== 客户端事件触发（供 WS 和本地使用） ====================

    async triggerRiskEvent(
      { commit }: any,
      eventData: Omit<RiskState["riskEvents"]["events"][0], "id" | "timestamp">,
    ) {
      const event: RiskState["riskEvents"]["events"][0] = {
        ...eventData,
        id: `event-${Date.now()}`,
        timestamp: new Date().toISOString(),
      };
      commit("ADD_EVENT", event);
      commit("UPDATE_EVENT_STATISTICS");

      if (eventData.actionTaken === "alert" || eventData.level === "critical") {
        commit(
          "layout/ADD_ALERT",
          {
            type: "warning",
            title: "风控警报",
            message: eventData.message,
            timestamp: new Date().toISOString(),
          },
          { root: true },
        );
      }
    },
  },

  getters: {
    activeRules: (state) =>
      state.riskRules.rules.filter((rule) => rule.enabled),
    recentEvents: (state) => state.riskEvents.events.slice(0, 50),
    criticalEvents: (state) =>
      state.riskEvents.events.filter(
        (event) => event.level === "critical" || event.level === "error",
      ),
    unresolvedEvents: (state) =>
      state.riskEvents.events.filter((event) => !event.actionTaken),
  },
};

export default riskModule;
