// 交易执行
// quant_web/src/store/modules/trade.ts
import {Module} from 'vuex';
import api from '@/api/trade';
import {Account, Order, Position, Trade, RootState} from "@/types";
import {OrderStatus} from "@/types/entities/base";
import {state} from "@antv/g2plot/lib/adaptor/common";

// 使用统一的类型
interface TradeState {
    accounts: Account[];
    currentAccount: Account | null;
    positions: Record<string, Position[]>;
    orders: Record<string, Order[]>;
    executions: Record<string, Trade[]>;
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
        SET_ACCOUNTS(state, accounts: Account[]) {
            state.accounts = accounts;
        },
        SET_CURRENT_ACCOUNT(state, account: Account) {
            state.currentAccount = account;
        },
        SET_POSITIONS(state, payload: { accountId: string; positions: Position[] }) {
            state.positions[payload.accountId] = payload.positions;
        },
        SET_ORDERS(state, payload: { accountId: string; orders: Order[] }) {
            state.orders[payload.accountId] = payload.orders;
        },
        SET_EXECUTIONS(state, payload: { accountId: string; executions: Trade[] }) {
            state.executions[payload.accountId] = payload.executions;
        },
        SET_CAPITAL_HISTORY(state, payload: { accountId: string; history: any[] }) {
            state.capitalHistory[payload.accountId] = payload.history;
        },
        ADD_TRADE_SIGNAL(state, signal: any) {
            state.tradeSignals.push(signal);
        },
        ADD_ORDER(state, order: Order) {
            if (!state.orders[order.account_id]) {
                state.orders[order.account_id] = [];
            }
            state.orders[order.account_id].push(order);
        },
        UPDATE_ORDER(state, updatedOrder: Order) {
            const orders = state.orders[updatedOrder.account_id] || [];
            const index = orders.findIndex(o => o.order_id === updatedOrder.order_id);
            if (index !== -1) {
                orders.splice(index, 1, updatedOrder);
                state.orders[updatedOrder.account_id] = [...orders];
            }
        },
        ADD_EXECUTION(state, execution: Trade) {
            if (!state.executions[execution.account_id]) {
                state.executions[execution.account_id] = [];
            }
            state.executions[execution.account_id].push(execution);
            state.pendingExecutions.push(execution);
        },
        REMOVE_PENDING_EXECUTION(state, executionId: string) {
            state.pendingExecutions = state.pendingExecutions.filter(e => e.trade_id !== executionId);
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
                if (!rootState.user?.userInfo?.id) {
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
                throw error;
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
        async fetchPositions({commit, state}) {
            try {
                if (!state.currentAccount?.id) {
                    throw new Error('未选择账户');
                }
                const positions = await api.getPositions();
                commit('SET_POSITIONS', {accountId: state.currentAccount.id, positions});
                return positions;
            } catch (error) {
                console.error('获取持仓失败:', error);
                throw error;
            }
        },
        async fetchOrders({commit, state}) {
            try {
                if (!state.currentAccount?.id) {
                    throw new Error('未选择账户');
                }
                // 修复：移除 accountId 参数，因为 OrderQueryParams 不包含该属性
                const response = await api.getOrders();
                const orders = response.data || response; // 处理分页响应和普通数组响应
                commit('SET_ORDERS', {accountId: state.currentAccount.id, orders});
                return orders;
            } catch (error) {
                console.error('获取订单失败:', error);
                throw error;
            }
        },
        async fetchExecutions({commit, state}) {
            try {
                if (!state.currentAccount?.id) {
                    throw new Error('未选择账户');
                }
                // 修复：移除 accountId 参数，因为 TradeQueryParams 不包含该属性
                const response = await api.getTradeRecords();
                const executions = response.data || response; // 处理分页响应和普通数组响应
                commit('SET_EXECUTIONS', {accountId: state.currentAccount.id, executions});
                return executions;
            } catch (error) {
                console.error('获取成交记录失败:', error);
                throw error;
            }
        },
        async fetchCapitalHistory({commit, state}) {
            try {
                if (!state.currentAccount?.id) {
                    throw new Error('未选择账户');
                }
                const history = await api.getTradePerformance(state.currentAccount.id);
                commit('SET_CAPITAL_HISTORY', {accountId: state.currentAccount.id, history});
                return history;
            } catch (error) {
                console.error('获取资金历史失败:', error);
                throw error;
            }
        },
        async placeOrder({commit, state}, orderData: any) {
            try {
                if (!state.currentAccount?.id) {
                    throw new Error('未选择账户');
                }

                // 修复：适配 API 参数格式
                const apiOrderData = {
                    symbol: orderData.symbol,
                    direction: orderData.direction,
                    orderType: orderData.order_type,
                    price: orderData.price,
                    volume: orderData.volume,
                    strategyId: orderData.strategy_id
                };

                const order = await api.createOrder(apiOrderData);

                commit('ADD_ORDER', order);

                // 修复：修正类型比较和变量名
                if (order.order_type === 'market') {
                    const execution: Trade = {
                        created_at: order.created_at,
                        id: order.id,
                        updated_at: order.updated_at,
                        trade_id: `exec-${Date.now()}`,
                        account_id: state.currentAccount.id,
                        order_id: order.order_id,
                        ts_code: order.ts_code,
                        symbol: order.symbol,
                        name: order.name,
                        price: order.price || 0,
                        volume: order.volume,
                        amount: (order.price || 0) * order.volume, // 使用 amount 而不是 value
                        commission: 0,
                        tax: 0,
                        trade_time: new Date().toISOString(),
                        direction: order.direction,
                        strategy_id: order.strategy_id
                    };
                    commit('ADD_EXECUTION', execution);
                    commit('UPDATE_ORDER', {...order, status: OrderStatus.FILLED});
                }

                return order;
            } catch (error) {
                console.error('下单失败:', error);
                throw error;
            }
        },
        async cancelOrder({commit, state}, orderId: string) {
            try {
                if (!state.currentAccount?.id) {
                    throw new Error('未选择账户');
                }

                await api.cancelOrder(orderId);

                const orders = state.orders[state.currentAccount.id] || [];
                const orderIndex = orders.findIndex(o => o.order_id === orderId);
                if (orderIndex !== -1) {
                    const updatedOrder = {...orders[orderIndex], status: OrderStatus.CANCELLED};
                    orders.splice(orderIndex, 1, updatedOrder);
                    commit('SET_ORDERS', {accountId: state.currentAccount.id, orders: [...orders]});
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
                    symbol: signal.symbol,
                    order_type: signal.order_type || 'limit',
                    direction: signal.direction,
                    price: signal.price,
                    volume: signal.volume,
                    strategy_id: signal.strategy_id
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
            return history[history.length - 1].total_asset;
        },
        pendingExecutionsCount: (state) => {
            return state.pendingExecutions.length;
        }
    }
};

export default tradeModule;