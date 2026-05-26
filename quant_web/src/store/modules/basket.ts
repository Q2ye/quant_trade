// quant_web/src/store/modules/basket.ts
import { Module } from "vuex";

import api from "@/api/basket";

// 使用统一的实体类型，避免重复定义
import {
  Basket,
  BasketPerformance,
  BasketItem,
  SimpleBasket,
  SimpleBasketItem,
  StockData,
} from "@/types";
import { RootState } from "@/types";

/**
 * 篮子状态接口定义
 */
interface BasketState {
  baskets: SimpleBasket[]; // 篮子列表（使用简化类型）
  currentBasket: SimpleBasket | null; // 当前选中的篮子
  basketPerformance: Record<string, BasketPerformance>; // 篮子绩效数据缓存
  basketComposition: Record<string, BasketItem[]>; // 篮子成分缓存
  basketSignals: Record<string, any[]>; // 篮子信号数据
}

const basketModule: Module<BasketState, RootState> = {
  namespaced: true,

  state: {
    baskets: [],
    currentBasket: null,
    basketPerformance: {},
    basketComposition: {},
    basketSignals: {},
  },

  mutations: {
    /**
     * 设置篮子列表
     */
    SET_BASKETS(state, baskets: Basket[]) {
      // 将完整的Basket类型转换为SimpleBasket类型用于store存储
      state.baskets = baskets.map((basket) => ({
        id: basket.id,
        name: basket.name,
        description: basket.description || "",
        items: basket.items.map((item) => ({
          symbol: item.symbol,
          weight: item.weight,
          name: item.name,
        })),
      }));
    },

    /**
     * 设置当前选中的篮子
     */
    SET_CURRENT_BASKET(state, basket: Basket | null) {
      state.currentBasket = basket
        ? {
            id: basket.id,
            name: basket.name,
            description: basket.description || "",
            items: basket.items.map((item) => ({
              symbol: item.symbol,
              weight: item.weight,
              name: item.name,
            })),
          }
        : null;
    },

    /**
     * 设置篮子成分数据
     */
    SET_BASKET_COMPOSITION(
      state,
      payload: { basketId: string; composition: BasketItem[] },
    ) {
      state.basketComposition[payload.basketId] = payload.composition;
    },

    /**
     * 设置篮子绩效数据
     */
    SET_BASKET_PERFORMANCE(
      state,
      payload: { basketId: string; performance: BasketPerformance },
    ) {
      state.basketPerformance[payload.basketId] = payload.performance;
    },

    /**
     * 添加篮子信号
     */
    ADD_BASKET_SIGNAL(state, payload: { basketId: string; signal: any }) {
      if (!state.basketSignals[payload.basketId]) {
        state.basketSignals[payload.basketId] = [];
      }
      state.basketSignals[payload.basketId].push(payload.signal);
    },

    /**
     * 更新篮子中的股票项
     */
    UPDATE_BASKET_ITEM(
      state,
      payload: { basketId: string; item: SimpleBasketItem },
    ) {
      const basket = state.baskets.find((b) => b.id === payload.basketId);
      if (basket) {
        const index = basket.items.findIndex(
          (i) => i.symbol === payload.item.symbol,
        );
        if (index !== -1) {
          basket.items.splice(index, 1, payload.item);
        }
      }
    },
  },

  actions: {
    /**
     * 获取篮子列表
     */
    async fetchBaskets({ commit }) {
      try {
        const response = await api.getBaskets();
        commit("SET_BASKETS", response.baskets);
        return response.baskets;
      } catch (error) {
        console.error("获取篮子列表失败:", error);
        throw error;
      }
    },

    /**
     * 创建新篮子
     */
    async createBasket(
      { commit, state },
      basketData: { name: string; description?: string },
    ) {
      try {
        // 构造创建篮子的请求数据，包含空的items数组
        const createData = {
          name: basketData.name,
          description: basketData.description || "",
          items: [] as BasketItem[],
          tags: [],
          isPublic: false,
        };

        const newBasket = await api.createBasket(createData);
        commit("SET_CURRENT_BASKET", newBasket);
        commit("SET_BASKETS", [...state.baskets, newBasket]);
        return newBasket;
      } catch (error) {
        console.error("创建篮子失败:", error);
        throw error;
      }
    },

    /**
     * 加载指定篮子的详细信息
     */
    async loadBasket({ commit }, basketId: string) {
      try {
        const basket = await api.getBasket(basketId);
        commit("SET_CURRENT_BASKET", basket);
        return basket;
      } catch (error) {
        console.error("加载篮子失败:", error);
        throw error;
      }
    },

    /**
     * 更新篮子信息
     */
    async updateBasket(
      { commit, state },
      payload: { id: string; data: { name?: string; description?: string } },
    ) {
      try {
        const updatedBasket = await api.updateBasket(payload.id, payload.data);

        // 确保description不为undefined
        const safeUpdatedBasket: Basket = {
          ...updatedBasket,
          description: updatedBasket.description || "",
        };

        commit("SET_CURRENT_BASKET", safeUpdatedBasket);

        // 更新篮子列表中的对应篮子
        const baskets = [...state.baskets];
        const index = baskets.findIndex((b) => b.id === payload.id);
        if (index !== -1) {
          baskets[index] = {
            id: safeUpdatedBasket.id,
            name: safeUpdatedBasket.name,
            description: safeUpdatedBasket.description || "",
            items: safeUpdatedBasket.items.map((item) => ({
              symbol: item.symbol,
              weight: item.weight,
              name: item.name,
            })),
          };
          commit("SET_BASKETS", baskets);
        }

        return safeUpdatedBasket;
      } catch (error) {
        console.error("更新篮子失败:", error);
        throw error;
      }
    },

    /**
     * 删除篮子
     */
    async deleteBasket({ commit, state }, basketId: string) {
      try {
        await api.deleteBasket(basketId);
        const baskets = state.baskets.filter((b) => b.id !== basketId);
        commit("SET_BASKETS", baskets);

        // 如果删除的是当前选中的篮子，清空当前篮子
        if (state.currentBasket && state.currentBasket.id === basketId) {
          commit("SET_CURRENT_BASKET", null);
        }

        return true;
      } catch (error) {
        console.error("删除篮子失败:", error);
        throw error;
      }
    },

    /**
     * 获取篮子成分
     */
    async fetchBasketComposition({ commit }, basketId: string) {
      try {
        const basket = await api.getBasket(basketId);
        const composition = basket.items || [];
        commit("SET_BASKET_COMPOSITION", { basketId, composition });
        return composition;
      } catch (error) {
        console.error("获取篮子成分失败:", error);
        throw error;
      }
    },

    /**
     * 获取篮子绩效数据
     */
    async fetchBasketPerformance(
      { commit },
      payload: { basketId: string; startDate: string; endDate: string },
    ) {
      try {
        const performance = await api.getBasketPerformance(payload.basketId, {
          start_date: payload.startDate,
          end_date: payload.endDate,
        });
        commit("SET_BASKET_PERFORMANCE", {
          basketId: payload.basketId,
          performance,
        });
        return performance;
      } catch (error) {
        console.error("获取篮子表现失败:", error);
        throw error;
      }
    },

    /**
     * 添加股票到篮子
     */
    async addStockToBasket(
      { commit, state },
      payload: { basketId: string; stock: StockData },
    ) {
      try {
        // 构造要添加的股票项
        const stockItem: BasketItem = {
          id: "", // 后端会生成
          basket_id: payload.basketId,
          symbol: payload.stock.symbol,
          name: payload.stock.name,
          weight: 0.1, // 默认权重
          created_at: new Date().toISOString(),
        };

        // 获取当前篮子
        const currentBasket = await api.getBasket(payload.basketId);

        // 更新篮子，添加新股票
        const updatedBasket = await api.updateBasket(payload.basketId, {
          items: [...currentBasket.items, stockItem],
        });

        commit("SET_CURRENT_BASKET", updatedBasket);

        // 同步更新篮子列表
        const baskets = [...state.baskets];
        const index = baskets.findIndex((b) => b.id === payload.basketId);
        if (index !== -1) {
          baskets[index] = {
            id: updatedBasket.id,
            name: updatedBasket.name,
            description: updatedBasket.description || "",
            items: updatedBasket.items.map((item) => ({
              symbol: item.symbol,
              weight: item.weight,
              name: item.name,
            })),
          };
          commit("SET_BASKETS", baskets);
        }

        return updatedBasket;
      } catch (error) {
        console.error("添加股票到篮子失败:", error);
        throw error;
      }
    },

    /**
     * 更新篮子中股票的权重
     */
    async updateBasketItem(
      { commit, state },
      payload: { basketId: string; item: SimpleBasketItem },
    ) {
      try {
        // 获取当前篮子
        const currentBasket = await api.getBasket(payload.basketId);

        // 更新对应股票的权重
        const updatedItems = currentBasket.items.map((item) =>
          item.symbol === payload.item.symbol
            ? { ...item, weight: payload.item.weight }
            : item,
        );

        const updatedBasket = await api.updateBasket(payload.basketId, {
          items: updatedItems,
        });

        commit("SET_CURRENT_BASKET", updatedBasket);

        // 同步更新篮子列表
        const baskets = [...state.baskets];
        const index = baskets.findIndex((b) => b.id === payload.basketId);
        if (index !== -1) {
          baskets[index] = {
            id: updatedBasket.id,
            name: updatedBasket.name,
            description: updatedBasket.description || "",
            items: updatedBasket.items.map((item) => ({
              symbol: item.symbol,
              weight: item.weight,
              name: item.name,
            })),
          };
          commit("SET_BASKETS", baskets);
        }

        return updatedBasket;
      } catch (error) {
        console.error("更新篮子成分失败:", error);
        throw error;
      }
    },

    /**
     * 从篮子中移除股票
     */
    async removeStockFromBasket(
      { commit, state },
      payload: { basketId: string; symbol: string },
    ) {
      try {
        // 获取当前篮子
        const currentBasket = await api.getBasket(payload.basketId);

        // 过滤掉要移除的股票
        const updatedItems = currentBasket.items.filter(
          (item) => item.symbol !== payload.symbol,
        );

        const updatedBasket = await api.updateBasket(payload.basketId, {
          items: updatedItems,
        });

        commit("SET_CURRENT_BASKET", updatedBasket);

        // 同步更新篮子列表
        const baskets = [...state.baskets];
        const basketIndex = baskets.findIndex((b) => b.id === payload.basketId);
        if (basketIndex !== -1) {
          baskets[basketIndex] = {
            id: updatedBasket.id,
            name: updatedBasket.name,
            description: updatedBasket.description || "",
            items: updatedBasket.items.map((item) => ({
              symbol: item.symbol,
              weight: item.weight,
              name: item.name,
            })),
          };
          commit("SET_BASKETS", baskets);
        }

        return true;
      } catch (error) {
        console.error("从篮子中移除股票失败:", error);
        throw error;
      }
    },
  },

  getters: {
    /**
     * 获取指定篮子的股票项
     */
    basketItems: (state) => (basketId: string) => {
      const basket = state.baskets.find((b) => b.id === basketId);
      return basket ? basket.items : [];
    },

    /**
     * 获取指定篮子的绩效数据
     */
    basketPerformance: (state) => (basketId: string) => {
      return state.basketPerformance[basketId] || null;
    },

    /**
     * 获取指定篮子的信号数据
     */
    basketSignals: (state) => (basketId: string) => {
      return state.basketSignals[basketId] || [];
    },

    /**
     * 获取当前选中的篮子
     */
    currentBasket: (state) => {
      return state.currentBasket;
    },
  },
};

export default basketModule;
