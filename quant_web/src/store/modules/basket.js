 // 篮子状态
 import api from '../../api/basket';

const state = {
  baskets: [],
  currentBasket: null,
  basketPerformance: {},
  basketComposition: {},
  basketSignals: {}
};

const mutations = {
  SET_BASKETS(state, baskets) {
    state.baskets = baskets;
  },

  SET_CURRENT_BASKET(state, basket) {
    state.currentBasket = basket;
  },

  SET_BASKET_COMPOSITION(state, { basketId, composition }) {
    state.basketComposition[basketId] = composition;
  },

  SET_BASKET_PERFORMANCE(state, { basketId, performance }) {
    state.basketPerformance[basketId] = performance;
  },

  ADD_BASKET_SIGNAL(state, { basketId, signal }) {
    if (!state.basketSignals[basketId]) {
      state.basketSignals[basketId] = [];
    }
    state.basketSignals[basketId].push(signal);
  },

  UPDATE_BASKET_ITEM(state, { basketId, item }) {
    const basket = state.baskets.find(b => b.id === basketId);
    if (basket) {
      const index = basket.items.findIndex(i => i.id === item.id);
      if (index !== -1) {
        basket.items.splice(index, 1, item);
      } else {
        basket.items.push(item);
      }
    }
  }
};

const actions = {
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

  async createBasket({ commit }, basketData) {
    try {
      const newBasket = await api.createBasket(basketData);
      commit('SET_CURRENT_BASKET', newBasket);
      commit('SET_BASKETS', [...state.baskets, newBasket]);
      return newBasket;
    } catch (error) {
      console.error('创建篮子失败:', error);
      throw error;
    }
  },

  async loadBasket({ commit }, basketId) {
    try {
      const basket = await api.getBasket(basketId);
      commit('SET_CURRENT_BASKET', basket);
      return basket;
    } catch (error) {
      console.error('加载篮子失败:', error);
      throw error;
    }
  },

  async updateBasket({ commit }, basket) {
    try {
      const updatedBasket = await api.updateBasket(basket);
      commit('SET_CURRENT_BASKET', updatedBasket);

      // 更新篮子列表中的对应项
      const baskets = [...state.baskets];
      const index = baskets.findIndex(b => b.id === basket.id);
      if (index !== -1) {
        baskets.splice(index, 1, updatedBasket);
        commit('SET_BASKETS', baskets);
      }

      return updatedBasket;
    } catch (error) {
      console.error('更新篮子失败:', error);
      throw error;
    }
  },

  async deleteBasket({ commit, state }, basketId) {
    try {
      await api.deleteBasket(basketId);

      // 从状态中移除篮子
      const baskets = state.baskets.filter(b => b.id !== basketId);
      commit('SET_BASKETS', baskets);

      // 如果当前篮子是被删除的篮子，则清空当前篮子
      if (state.currentBasket && state.currentBasket.id === basketId) {
        commit('SET_CURRENT_BASKET', null);
      }

      return true;
    } catch (error) {
      console.error('删除篮子失败:', error);
      throw error;
    }
  },

  async fetchBasketComposition({ commit }, basketId) {
    try {
      const composition = await api.getBasketComposition(basketId);
      commit('SET_BASKET_COMPOSITION', { basketId, composition });
      return composition;
    } catch (error) {
      console.error('获取篮子成分失败:', error);
      throw error;
    }
  },

  async fetchBasketPerformance({ commit }, basketId) {
    try {
      const performance = await api.getBasketPerformance(basketId);
      commit('SET_BASKET_PERFORMANCE', { basketId, performance });
      return performance;
    } catch (error) {
      console.error('获取篮子表现失败:', error);
      throw error;
    }
  },

  async addStockToBasket({ commit }, { basketId, stock }) {
    try {
      const updatedItem = await api.addStockToBasket(basketId, stock);
      commit('UPDATE_BASKET_ITEM', { basketId, item: updatedItem });
      return updatedItem;
    } catch (error) {
      console.error('添加股票到篮子失败:', error);
      throw error;
    }
  },

  async updateBasketItem({ commit }, { basketId, item }) {
    try {
      const updatedItem = await api.updateBasketItem(basketId, item);
      commit('UPDATE_BASKET_ITEM', { basketId, item: updatedItem });
      return updatedItem;
    } catch (error) {
      console.error('更新篮子成分失败:', error);
      throw error;
    }
  },

  async removeStockFromBasket({ commit }, { basketId, itemId }) {
    try {
      await api.removeStockFromBasket(basketId, itemId);

      // 从状态中移除
      const basket = state.baskets.find(b => b.id === basketId);
      if (basket) {
        const items = basket.items.filter(i => i.id !== itemId);
        commit('SET_CURRENT_BASKET', { ...basket, items });
      }

      return true;
    } catch (error) {
      console.error('从篮子中移除股票失败:', error);
      throw error;
    }
  },

  async executeBasketTrade({ commit }, { basketId, tradeType }) {
    try {
      const signals = await api.executeBasketTrade(basketId, tradeType);

      // 添加信号到状态
      signals.forEach(signal => {
        commit('ADD_BASKET_SIGNAL', { basketId, signal });
      });

      return signals;
    } catch (error) {
      console.error('执行篮子交易失败:', error);
      throw error;
    }
  }
};

const getters = {
  basketItems: (state) => (basketId) => {
    const basket = state.baskets.find(b => b.id === basketId);
    return basket ? basket.items : [];
  },

  basketPerformance: (state) => (basketId) => {
    return state.basketPerformance[basketId] || null;
  },

  basketSignals: (state) => (basketId) => {
    return state.basketSignals[basketId] || [];
  }
};

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters
};