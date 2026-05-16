// quant_web/src/store/modules/risk.ts
// 风险管理
import { Module } from "vuex";
import { RootState, RiskState } from "@/types";
import riskAPI from "@/api/risk";

const riskModule: Module<RiskState, RootState> = {
  namespaced: true,
  state: {
    // 风控规则配置
    riskRules: {
      rules: [],
      editingRule: null,
    },
    // 实时风险监控
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
    // 风险事件记录
    riskEvents: {
      events: [],
      statistics: {
        today: 0,
        critical: 0,
        unresolved: 0,
      },
    },
    // 黑名单管理
    blacklist: {
      stocks: [],
    },
    // 风险报告
    riskReports: {
      daily: null,
      weekly: null,
      monthly: null,
    },
    // 加载状态
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
    async fetchRiskRules({ commit, rootState }: any) {
      commit("SET_LOADING", { rules: true });
      try {
        const rules = await riskAPI.getRiskRules(rootState.user.token || "");
        commit("SET_RULES", rules as any);
        return rules;
      } catch (error) {
        console.error("获取风控规则失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { rules: false });
      }
    },
    async createRiskRule(
      { commit, state },
      ruleData: Omit<RiskState["riskRules"]["rules"][0], "id">,
    ) {
      try {
        const newRule: RiskState["riskRules"]["rules"][0] = {
          ...ruleData,
          id: `rule-${Date.now()}`,
        };
        // 这里调用API创建规则
        const updatedRules = [...state.riskRules.rules, newRule];
        commit("SET_RULES", updatedRules);
        return newRule;
      } catch (error) {
        console.error("创建风控规则失败:", error);
        throw error;
      }
    },
    async triggerRiskEvent(
      { commit },
      eventData: Omit<RiskState["riskEvents"]["events"][0], "id" | "timestamp">,
    ) {
      const event: RiskState["riskEvents"]["events"][0] = {
        ...eventData,
        id: `event-${Date.now()}`,
        timestamp: new Date().toISOString(),
      };
      commit("ADD_EVENT", event);
      commit("UPDATE_EVENT_STATISTICS");

      // 根据规则执行相应动作
      if (eventData.actionTaken === "alert") {
        // 发送警报
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
    async fetchRiskEvents({ commit }) {
      commit("SET_LOADING", { events: true });
      try {
        const response = await riskAPI.getRiskEvents({ limit: 100 });
        const events = (response as any).data?.items ?? response as any;
        commit("SET_EVENTS", events);
        commit("UPDATE_EVENT_STATISTICS");
        return events;
      } catch (error) {
        console.error("获取风险事件失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { events: false });
      }
    },
    async fetchBlacklist({ commit, rootState }: any) {
      commit("SET_LOADING", { blacklist: true });
      try {
        const rules = await riskAPI.getRiskRules(rootState.user.token || "");
        const blacklistRules =
          (rules as any)?.filter?.((r: any) => r.type === "blacklist") ?? [];
        commit("SET_BLACKLIST", blacklistRules);
        return blacklistRules;
      } catch (error) {
        console.error("获取黑名单失败:", error);
        throw error;
      } finally {
        commit("SET_LOADING", { blacklist: false });
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
