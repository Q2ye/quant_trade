import {Module} from 'vuex';
import api, {BacktestResult, Strategy} from '../../api/strategy';
import {RootState} from '../types';

interface StrategyState {
    currentStrategy: Strategy | null;
    strategies: Strategy[];
    backtestParams: {
        startDate: string;
        endDate: string;
        initialCapital: number;
        commission: number;
        slippage: number;
    };
    backtestResults: BacktestResult | null;
    runningStrategies: string[];
}

const strategyModule: Module<StrategyState, RootState> = {
    namespaced: true,
    state: {
        currentStrategy: null,
        strategies: [],
        backtestParams: {
            startDate: '2020-01-01',
            endDate: '2023-12-31',
            initialCapital: 100000,
            commission: 0.0003,
            slippage: 0.01
        },
        backtestResults: null,
        runningStrategies: []
    },
    mutations: {
        SET_CURRENT_STRATEGY(state, strategy: Strategy) {
            state.currentStrategy = strategy;
        },
        SET_STRATEGIES(state, strategies: Strategy[]) {
            state.strategies = strategies;
        },
        SET_BACKTEST_PARAMS(state, params: StrategyState['backtestParams']) {
            state.backtestParams = params;
        },
        SET_BACKTEST_RESULTS(state, results: BacktestResult) {
            state.backtestResults = results;
        },
        ADD_RUNNING_STRATEGY(state, strategyId: string) {
            if (!state.runningStrategies.includes(strategyId)) {
                state.runningStrategies.push(strategyId);
            }
        },
        REMOVE_RUNNING_STRATEGY(state, strategyId: string) {
            state.runningStrategies = state.runningStrategies.filter(id => id !== strategyId);
        }
    },
    actions: {
        async fetchStrategies({commit}) {
            try {
                const response = await api.getStrategyList();
                commit('SET_STRATEGIES', response.strategies);
                return response;
            } catch (error) {
                console.error('获取策略列表失败:', error);
                throw error;
            }
        },
        async loadStrategy({commit}, strategyId: string) {
            try {
                const strategy = await api.getStrategyDetails(strategyId);
                commit('SET_CURRENT_STRATEGY', strategy);
                return strategy;
            } catch (error) {
                console.error('加载策略失败:', error);
                throw error;
            }
        },
        async saveStrategy({state, commit}) {
            if (!state.currentStrategy) {
                throw new Error('没有当前策略');
            }

            try {
                const updatedStrategy = await api.updateStrategy(
                    state.currentStrategy.id,
                    state.currentStrategy
                );
                commit('SET_CURRENT_STRATEGY', updatedStrategy);
                return updatedStrategy;
            } catch (error) {
                console.error('保存策略失败:', error);
                throw error;
            }
        },
        async runBacktest({commit, state}) {
            if (!state.currentStrategy) {
                throw new Error('没有当前策略');
            }

            try {
                const results = await api.runStrategyBacktest(
                    state.currentStrategy.id,
                    state.backtestParams
                );
                commit('SET_BACKTEST_RESULTS', results);
                return results;
            } catch (error) {
                console.error('回测执行失败:', error);
                throw error;
            }
        },
        async startStrategy({commit}, strategyId: string) {
            try {
                await api.startStrategy(strategyId);
                commit('ADD_RUNNING_STRATEGY', strategyId);
                return true;
            } catch (error) {
                console.error('启动策略失败:', error);
                throw error;
            }
        },
        async stopStrategy({commit}, strategyId: string) {
            try {
                await api.stopStrategy(strategyId);
                commit('REMOVE_RUNNING_STRATEGY', strategyId);
                return true;
            } catch (error) {
                console.error('停止策略失败:', error);
                throw error;
            }
        }
    }
};

export default strategyModule;