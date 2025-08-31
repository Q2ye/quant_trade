import {Module} from 'vuex';
import api, {AccountInfo, Position, Order, TradeRecord } from '@/api/trade';
import {RootState} from '../types';

interface TradeState {
    accounts: AccountInfo[];
    currentAccount: AccountInfo | null;
    positions: Record<string, Position[]>;
    orders: Record<string, Order[]>;
    executions: Record<string, TradeRecord[]>;
    capitalHistory: Record<string, any[]>;
    tradeSignals: any[];
    pendingExecutions: any[];
}

const tradeModule: Module<TradeState, RootState> = {
    namespaced: true,
    state: {
        accounts: [],
        currentAccount: null,
        positions: {},
        orders: {},
        executions: {},
        capitalHistory: {},
        tradeSignals: [],
        pendingExecutions: []
    },
    mutations: {
        SET_ACCOUNTS(state, accounts: AccountInfo[]) {
            state.accounts = accounts;
        },
        SET_CURRENT_ACCOUNT(state, account: AccountInfo) {
            state.currentAccount = account;
        },
        SET_POSITIONS(state, payload: { accountId: string; positions: Position[] }) {
            state.positions[payload.accountId] = payload.positions;
        },
        SET_ORDERS(state, payload: { accountId: string; orders: Order[] }) {
            state.orders[payload.accountId] = payload.orders;
        },
        SET_EXECUTIONS(state, payload: { accountId: string; executions: TradeRecord[] }) {
            state.executions[payload.accountId] = payload.executions;
        },
        SET_CAPITAL_HISTORY(state, payload: { accountId: string; history: any[] }) {
            state.capitalHistory[payload.accountId] = payload.history;
        },
        ADD_TRADE_SIGNAL(state, signal: any) {
            state.tradeSignals.push(signal);
        },
        ADD_ORDER(state, order: Order) {
            if (!state.orders[order.accountId]) {
                state.orders[order.accountId] = [];
            }
            state.orders[order.accountId].push(order);
        },
        UPDATE_ORDER(state, updatedOrder: Order) {
            const orders = state.orders[updatedOrder.accountId] || [];
            const index = orders.findIndex(o => o.id === updatedOrder.id);
            if (index !== -1) {
                orders.splice(index, 1, updatedOrder);
                state.orders[updatedOrder.accountId] = [...orders];
            }
        },
        ADD_EXECUTION(state, execution: TradeRecord) {
            if (!state.executions[execution.accountId]) {
                state.executions[execution.accountId] = [];
            }
            state.executions[execution.accountId].push(execution);
            state.pendingExecutions.push(execution);
        },
        REMOVE_PENDING_EXECUTION(state, executionId: string) {
            state.pendingExecutions = state.pendingExecutions.filter(e => e.id !== executionId);
        },
        UPDATE_POSITION(state, payload: { accountId: string; position: Position }) {
            const positions = state.positions[payload.accountId] || [];
            const index = positions.findIndex(p => p.symbol === payload.position.symbol);

            if (index !== -1) {
                positions.splice(index, 1, payload.position);
            } else {
                positions.push(payload.position);
            }

            state.positions[payload.accountId] = [...positions];
        }
    },
    actions: {
        async fetchAccounts({commit, rootState}) {
            try {
                if (!rootState.user.userInfo?.id) {
                    throw new Error('用户未登录');
                }

                const accounts = await api.getAccountInfo();
                commit('SET_ACCOUNTS', accounts);

                if (accounts.length > 0) {
                    commit('SET_CURRENT_ACCOUNT', accounts[0]);
                }

                return accounts;
            } catch (error) {
                console.error('获取交易账户失败:', error);
                throw error; // 保持异常传递，让调用者处理
            }
        },
        async selectAccount({commit, state}, accountId: string) {
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
        async fetchPositions({commit}, accountId: string) {
            try {
                const positions = await api.getPositions();
                commit('SET_POSITIONS', {accountId, positions});
                return positions;
            } catch (error) {
                console.error('获取持仓失败:', error);
                throw error;
            }
        },
        async fetchOrders({commit}, accountId: string) {
            try {
                const orders = await api.getOrderHistory();
                commit('SET_ORDERS', {accountId, orders});
                return orders;
            } catch (error) {
                console.error('获取订单失败:', error);
                throw error;
            }
        },
        async fetchExecutions({commit}, accountId: string) {
            try {
                const executions = await api.getTradeRecords();
                commit('SET_EXECUTIONS', {accountId, executions});
                return executions;
            } catch (error) {
                console.error('获取成交记录失败:', error);
                throw error;
            }
        },
        async fetchCapitalHistory({commit}, accountId: string) {
            try {
                const history = await api.getTradePerformance();
                commit('SET_CAPITAL_HISTORY', {accountId, history});
                return history;
            } catch (error) {
                console.error('获取资金历史失败:', error);
                throw error;
            }
        },
        async placeOrder({commit}, orderData: any) {
            try {
                const order = await api.createOrder(orderData);
                commit('ADD_ORDER', order);

                if (order.orderType === 'MARKET') {
                    // 修复：移除TradeRecord中不存在的status属性
                    const execution: TradeRecord = {
                        accountId: order.accountId,
                        id: `exec-${Date.now()}`,
                        symbol: order.symbol,
                        price: order.price,
                        quantity: order.volume ?? order.quantity ?? 0,
                        executedAt: new Date().toISOString()
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
        async cancelOrder({commit, state}, payload: { accountId: string; orderId: string }) {
            try {
                await api.cancelOrder(payload.orderId);

                const orders = state.orders[payload.accountId] || [];
                const orderIndex = orders.findIndex(o => o.id === payload.orderId);
                if (orderIndex !== -1) {
                    const updatedOrder = {...orders[orderIndex], status: 'CANCELLED'};
                    orders.splice(orderIndex, 1, updatedOrder);
                    commit('SET_ORDERS', {accountId: payload.accountId, orders: [...orders]});
                }

                return true;
            } catch (error) {
                console.error('撤单失败:', error);
                throw error;
            }
        },
        async confirmSignal({commit, dispatch, state}, signal: any) {
            try {
                commit('ADD_TRADE_SIGNAL', signal);

                const orderData = {
                    accountId: state.currentAccount?.id,
                    symbol: signal.symbol,
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
        async acknowledgeExecution({commit}, executionId: string) {
            try {
                commit('REMOVE_PENDING_EXECUTION', executionId);
                return true;
            } catch (error) {
                console.error('确认成交失败:', error);
                throw error;
            }
        },
        subscribeTradeUpdates(_) {
            // 假设api.subscribeTradeUpdates是一个订阅函数
            // 实际实现可能需要使用WebSocket
        }
    },
    getters: {
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
        accountEquity: (state) => (accountId: string) => {
            const history = state.capitalHistory[accountId];
            if (!history || history.length === 0) return 0;
            return history[history.length - 1].total_equity;
        },
        pendingExecutionsCount: (state) => {
            return state.pendingExecutions.length;
        }
    }
};

export default tradeModule;