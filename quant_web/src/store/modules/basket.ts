import { Module } from 'vuex';
import { RootState } from '../types';
import api from '@/api/basket';

// 定义必要的类型接口
interface BasketItem {
  symbol: string;
  weight: number;
}

interface PerformanceData {
  returns: number;
  volatility: number;
  maxDrawdown: number;
  sharpeRatio: number;
}

interface StockData {
  symbol: string;
  name: string;
}

// 与API返回的Basket结构保持一致
interface Basket {
  id: string;
  name: string;
  description: string;
  stocks: BasketItem[]; // 将items改为stocks以匹配API
}

interface BasketState {
  baskets: Basket[];
  currentBasket: Basket | null;
  basketPerformance: Record<string, PerformanceData>;
  basketComposition: Record<string, BasketItem[]>;
  basketSignals: Record<string, any[]>;
}

const basketModule: Module<BasketState, RootState> = {
  namespaced: true,
  state: {
    baskets: [],
    currentBasket: null,
    basketPerformance: {},
    basketComposition: {},
    basketSignals: {}
  },
  mutations: {
    SET_BASKETS(state, baskets: Basket[]) {
      state.baskets = baskets.map(basket => ({
        ...basket,
        stocks: basket.stocks || []  // 确保stocks数组存在
      }));
    },
    SET_CURRENT_BASKET(state, basket: Basket) {
      state.currentBasket = basket ? {
        ...basket,
        stocks: basket.stocks || []  // 确保stocks数组存在
      } : null;
    },
    SET_BASKET_COMPOSITION(state, payload: { basketId: string; composition: BasketItem[] }) {
      state.basketComposition[payload.basketId] = payload.composition;
    },
    SET_BASKET_PERFORMANCE(state, payload: { basketId: string; performance: PerformanceData }) {
      state.basketPerformance[payload.basketId] = payload.performance;
    },
    ADD_BASKET_SIGNAL(state, payload: { basketId: string; signal: any }) {
      if (!state.basketSignals[payload.basketId]) {
        state.basketSignals[payload.basketId] = [];
      }
      state.basketSignals[payload.basketId].push(payload.signal);
    },
    UPDATE_BASKET_ITEM(state, payload: { basketId: string; item: BasketItem }) {
      const basket = state.baskets.find(b => b.id === payload.basketId);
      if (basket) {
        const index = basket.stocks.findIndex(i => i.symbol === payload.item.symbol);
        if (index !== -1) {
          basket.stocks.splice(index, 1, payload.item);
        }
      }
    }
  },
  actions: {
    async fetchBaskets({ commit }) {
      try {
        const baskets = await api.getBaskets();
        commit('SET_BASKETS', baskets);
        return baskets;
      } catch (error) {
        console.error('获取篮子列表失败:', error);
        throw error;
      }
    },
    async createBasket({ commit, state }, basketData: Omit<Basket, 'id'>) {
      try {
        // 确保创建时包含空stocks数组
        const newBasket = await api.createBasket({
          ...basketData,
          stocks: basketData.stocks || []
        });
        commit('SET_CURRENT_BASKET', newBasket);
        commit('SET_BASKETS', [...state.baskets, newBasket]);
        return newBasket;
      } catch (error) {
        console.error('创建篮子失败:', error);
        throw error;
      }
    },
    async loadBasket({ commit }, basketId: string) {
      try {
        const basket = await api.getBasket(basketId);
        commit('SET_CURRENT_BASKET', basket);
        return basket;
      } catch (error) {
        console.error('加载篮子失败:', error);
        throw error;
      }
    },
    async updateBasket({ commit, state }, basket: Basket) {
      try {
        const updatedBasket = await api.updateBasket(basket.id, basket);
        // 确保 description 不为 undefined
        const safeUpdatedBasket: Basket = {
          ...updatedBasket,
          description: updatedBasket.description ?? ''
        };
        commit('SET_CURRENT_BASKET', safeUpdatedBasket);

        const baskets = [...state.baskets];
        const index = baskets.findIndex(b => b.id === basket.id);
        if (index !== -1) {
          baskets.splice(index, 1, safeUpdatedBasket);
          commit('SET_BASKETS', baskets);
        }

        return safeUpdatedBasket;
      } catch (error) {
        console.error('更新篮子失败:', error);
        throw error;
      }
    },
    async deleteBasket({ commit, state }, basketId: string) {
      try {
        await api.deleteBasket(basketId);
        const baskets = state.baskets.filter(b => b.id !== basketId);
        commit('SET_BASKETS', baskets);

        if (state.currentBasket && state.currentBasket.id === basketId) {
          commit('SET_CURRENT_BASKET', null);
        }

        return true;
      } catch (error) {
        console.error('删除篮子失败:', error);
        throw error;
      }
    },
    async fetchBasketComposition({ commit }, basketId: string) {
      try {
        const basket = await api.getBasket(basketId);
        const composition = basket.stocks || [];
        commit('SET_BASKET_COMPOSITION', { basketId, composition });
        return composition;
      } catch (error) {
        console.error('获取篮子成分失败:', error);
        throw error;
      }
    },
    async fetchBasketPerformance({ commit }, basketId: string) {
      try {
        const performance = await api.getBasketPerformance(basketId);
        commit('SET_BASKET_PERFORMANCE', { basketId, performance });
        return performance;
      } catch (error) {
        console.error('获取篮子表现失败:', error);
        throw error;
      }
    },
    async addStockToBasket({ commit, state }, payload: { basketId: string; stock: StockData }) {
      try {
        // 使用默认权重0.1
        const stockPayload = {
          symbol: payload.stock.symbol,
          weight: 0.1 // 默认权重
        };

        const updatedBasket = await api.addStockToBasket(payload.basketId, stockPayload);
        commit('SET_CURRENT_BASKET', updatedBasket);

        // 同步更新baskets数组
        const baskets = [...state.baskets];
        const index = baskets.findIndex(b => b.id === payload.basketId);
        if (index !== -1) {
          baskets[index] = {
            ...updatedBasket,
            description: updatedBasket.description ?? ''
          };
          commit('SET_BASKETS', baskets);
        }

        return updatedBasket;
      } catch (error) {
        console.error('添加股票到篮子失败:', error);
        throw error;
      }
    },
    async updateBasketItem({ commit, state }, payload: { basketId: string; item: BasketItem }) {
      try {
        const updatedBasket = await api.adjustStockWeight(
          payload.basketId,
          payload.item.symbol,
          payload.item.weight
        );
        commit('SET_CURRENT_BASKET', updatedBasket);

        // 同步更新baskets数组
        const baskets = [...state.baskets];
        const index = baskets.findIndex(b => b.id === payload.basketId);
        if (index !== -1) {
          baskets[index] = {
            ...updatedBasket,
            description: updatedBasket.description ?? ''
          };
          commit('SET_BASKETS', baskets);
        }

        return updatedBasket;
      } catch (error) {
        console.error('更新篮子成分失败:', error);
        throw error;
      }
    },
    async removeStockFromBasket({ commit, state }, payload: { basketId: string; symbol: string }) {
      try {
        const basket = state.baskets.find(b => b.id === payload.basketId);
        if (!basket) throw new Error('篮子未找到');

        await api.removeStockFromBasket(payload.basketId, payload.symbol);

        const updatedBasket = {
          ...basket,
          stocks: basket.stocks.filter(i => i.symbol !== payload.symbol)
        };

        commit('SET_CURRENT_BASKET', updatedBasket);

        // 同步更新baskets数组
        const baskets = [...state.baskets];
        const basketIndex = baskets.findIndex(b => b.id === payload.basketId);
        if (basketIndex !== -1) {
          baskets[basketIndex] = updatedBasket;
          commit('SET_BASKETS', baskets);
        }

        return true;
      } catch (error) {
        console.error('从篮子中移除股票失败:', error);
        throw error;
      }
    }
  },
  getters: {
    basketItems: (state) => (basketId: string) => {
      const basket = state.baskets.find(b => b.id === basketId);
      return basket ? basket.stocks : [];
    },
    basketPerformance: (state) => (basketId: string) => {
      return state.basketPerformance[basketId] || null;
    },
    basketSignals: (state) => (basketId: string) => {
      return state.basketSignals[basketId] || [];
    }
  }
};

export default basketModule;