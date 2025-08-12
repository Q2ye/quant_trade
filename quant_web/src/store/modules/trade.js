// 交易状态
import api from '../../api/trade';

const state = {
    accounts: [],
    currentAccount: null,
    positions: {},
    orders: {},
    executions: {},
    capitalHistory: {},
    tradeSignals: [],
    pendingExecutions: []
};

const mutations = {
    SET_ACCOUNTS(state, accounts) {
        state.accounts = accounts;
    },

    SET_CURRENT_ACCOUNT(state, account) {
        state.currentAccount = account;
    },

    SET_POSITIONS(state, {accountId, positions}) {
        state.positions[accountId] = positions;
    },

    SET_ORDERS(state, {accountId, orders}) {
        state.orders[accountId] = orders;
    },

    SET_EXECUTIONS(state, {accountId, executions}) {
        state.executions[accountId] = executions;
    },

    SET_CAPITAL_HISTORY(state, {accountId, history}) {
        state.capitalHistory[accountId] = history;
    },

    ADD_TRADE_SIGNAL(state, signal) {
        state.tradeSignals.push(signal);
    },

    ADD_ORDER(state, order) {
        if (!state.orders[order.accountId]) {
            state.orders[order.accountId] = [];
        }
        state.orders[order.accountId].push(order);
    },

    UPDATE_ORDER(state, updatedOrder) {
        const orders = state.orders[updatedOrder.accountId] || [];
        const index = orders.findIndex(o => o.id === updatedOrder.id);
        if (index !== -1) {
            orders.splice(index, 1, updatedOrder);
            state.orders[updatedOrder.accountId] = [...orders];
        }
    },

    ADD_EXECUTION(state, execution) {
        if (!state.executions[execution.accountId]) {
            state.executions[execution.accountId] = [];
        }
        state.executions[execution.accountId].push(execution);

        // 添加到待处理执行列表
        state.pendingExecutions.push(execution);
    },

    REMOVE_PENDING_EXECUTION(state, executionId) {
        state.pendingExecutions = state.pendingExecutions.filter(e => e.id !== executionId);
    },

    UPDATE_POSITION(state, {accountId, position}) {
        const positions = state.positions[accountId] || [];
        const index = positions.findIndex(p => p.ts_code === position.ts_code);

        if (index !== -1) {
            positions.splice(index, 1, position);
        } else {
            positions.push(position);
        }

        state.positions[accountId] = [...positions];
    }
};

const actions = {
    async fetchAccounts({commit, rootState}) {
        try {
            const userId = rootState.user.userInfo?.id;
            if (!userId) {
                throw new Error('用户未登录');
            }

            const accounts = await api.getAccountInfo(userId);
            commit('SET_ACCOUNTS', accounts);

            // 自动选择第一个账户
            if (accounts.length > 0) {
                commit('SET_CURRENT_ACCOUNT', accounts[0]);
            }

            return accounts;
        } catch (error) {
            console.error('获取交易账户失败:', error);
            throw error;
        }
    },

    async selectAccount({commit}, accountId) {
        try {
            const account = state.accounts.find(a => a.id === accountId);
            if (account) {
                commit('SET_CURRENT_ACCOUNT', account);
            }
            return account;
        } catch (error) {
            console.error('选择账户失败:', error);
            throw error;
        }
    },

    async fetchPositions({commit}, accountId) {
        try {
            const positions = await api.getPositions(accountId);
            commit('SET_POSITIONS', {accountId, positions});
            return positions;
        } catch (error) {
            console.error('获取持仓失败:', error);
            throw error;
        }
    },

    async fetchOrders({commit}, accountId) {
        try {
            const orders = await api.getOrders(accountId);
            commit('SET_ORDERS', {accountId, orders});
            return orders;
        } catch (error) {
            console.error('获取订单失败:', error);
            throw error;
        }
    },

    async fetchExecutions({commit}, accountId) {
        try {
            const executions = await api.getExecutions(accountId);
            commit('SET_EXECUTIONS', {accountId, executions});
            return executions;
        } catch (error) {
            console.error('获取成交记录失败:', error);
            throw error;
        }
    },

    async fetchCapitalHistory({commit}, accountId) {
        try {
            const history = await api.getCapitalHistory(accountId);
            commit('SET_CAPITAL_HISTORY', {accountId, history});
            return history;
        } catch (error) {
            console.error('获取资金历史失败:', error);
            throw error;
        }
    },

    async placeOrder({commit}, orderData) {
        try {
            const order = await api.placeOrder(orderData);
            commit('ADD_ORDER', order);

            // 如果是市价单，立即执行
            if (order.orderType === 'MARKET') {
                const execution = {
                    ...order,
                    id: `exec-${Date.now()}`,
                    executedAt: new Date().toISOString(),
                    status: 'FILLED'
                };
                commit('ADD_EXECUTION', execution);
                commit('UPDATE_ORDER', {...order, status: 'FILLED'});
            }

            return order;
        } catch (error) {
            console.error('下单失败:', error);
            throw error;
        }
    },

    async cancelOrder({commit}, {accountId, orderId}) {
        try {
            await api.cancelOrder(accountId, orderId);

            // 更新订单状态
            const orders = state.orders[accountId] || [];
            const orderIndex = orders.findIndex(o => o.id === orderId);
            if (orderIndex !== -1) {
                const updatedOrder = {...orders[orderIndex], status: 'CANCELLED'};
                orders.splice(orderIndex, 1, updatedOrder);
                commit('SET_ORDERS', {accountId, orders: [...orders]});
            }

            return true;
        } catch (error) {
            console.error('撤单失败:', error);
            throw error;
        }
    },

    async confirmSignal({commit, dispatch}, signal) {
        try {
            commit('ADD_TRADE_SIGNAL', signal);

            // 创建订单
            const orderData = {
                accountId: state.currentAccount.id,
                ts_code: signal.symbol,
                orderType: signal.orderType || 'LIMIT',
                direction: signal.action,
                price: signal.price,
                volume: signal.volume,
                strategyId: signal.strategyId
            };

            return await dispatch('placeOrder', orderData);
        } catch (error) {
            console.error('确认交易信号失败:', error);
            throw error;
        }
    },

    async acknowledgeExecution({commit}, executionId) {
        try {
            // 在实际应用中，这里会发送确认到服务器
            commit('REMOVE_PENDING_EXECUTION', executionId);
            return true;
        } catch (error) {
            console.error('确认成交失败:', error);
            throw error;
        }
    },

    // 订阅实时交易更新
    subscribeTradeUpdates({commit}) {
        api.subscribeTradeUpdates((update) => {
            if (update.type === 'ORDER_UPDATE') {
                commit('UPDATE_ORDER', update.data);
            } else if (update.type === 'EXECUTION') {
                commit('ADD_EXECUTION', update.data);

                // 更新持仓
                if (update.data.position) {
                    commit('UPDATE_POSITION', {
                        accountId: update.data.accountId,
                        position: update.data.position
                    });
                }
            } else if (update.type === 'SIGNAL') {
                commit('ADD_TRADE_SIGNAL', update.data);
            }
        });
    }
};

const getters = {
    currentPositions: (state) => {
        if (!state.currentAccount) return [];
        return state.positions[state.currentAccount.id] || [];
    },

    currentOrders: (state) => {
        if (!state.currentAccount) return [];
        return state.orders[state.currentAccount.id] || [];
    },

    currentExecutions: (state) => {
        if (!state.currentAccount) return [];
        return state.executions[state.currentAccount.id] || [];
    },

    accountEquity: (state) => (accountId) => {
        const history = state.capitalHistory[accountId];
        if (!history || history.length === 0) return 0;
        return history[history.length - 1].total_equity;
    },

    pendingExecutionsCount: (state) => {
        return state.pendingExecutions.length;
    }
};

export default {
    namespaced: true,
    state,
    mutations,
    actions,
    getters
};