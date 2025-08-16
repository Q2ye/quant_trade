// src/store/index.ts（修改后）
import {createLogger, createStore, Store} from 'vuex';
import createPersistedState from 'vuex-persistedstate';
import basket from './modules/basket';
import data from './modules/data';
import strategy from './modules/strategy';
import system from './modules/system';
import trade from './modules/trade';
import user from './modules/user';
import { RootState } from './types'; // 导入统一的RootState

const store: Store<RootState> = createStore({
    modules: {
        basket,
        data,
        strategy,
        system,
        trade,
        user
    },
    plugins: [
        createPersistedState({
            key: 'quant-platform',
            paths: [
                'user.token',
                'user.userInfo',
                'strategy.currentStrategy',
                'strategy.backtestParams',
                'basket.currentBasket'
            ]
        }),
        createLogger()
    ]
});

export default store;