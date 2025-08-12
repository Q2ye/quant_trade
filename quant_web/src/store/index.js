// Store主文件
import { createStore } from 'vuex'
import createPersistedState from 'vuex-persistedstate'
import strategy from './modules/strategy'
import basket from './modules/basket'
import trade from './modules/trade'
import system from './modules/system'
import data from './modules/data'
import user from './modules/user'

export default createStore({
  modules: {
    strategy,
    basket,
    trade,
    system,
    data,
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
    })
  ]
})
