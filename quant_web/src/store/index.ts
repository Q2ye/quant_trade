import { createLogger, createStore, Store } from "vuex";
import createPersistedState from "vuex-persistedstate";
import basket from "./modules/basket";
import data from "./modules/data";
import strategy from "./modules/strategy";
import system from "./modules/system";
import trade from "./modules/trade";
import user from "./modules/user";
import layout from "./modules/layout";
import dashboard from "./modules/dashboard";
import strategyStudio from "./modules/strategyStudio";
import risk from "./modules/risk";
import performance from "./modules/performance";
import { RootState } from "@/types";

const store: Store<RootState> = createStore({
  modules: {
    user,
    basket,
    strategy,
    trade,
    data,
    system,
    layout,
    dashboard,
    strategyStudio,
    risk,
    performance,
  },
  plugins: [
    createPersistedState({
      key: "quant-platform-v3",
      paths: [
        "user.token",
        "user.userInfo",
        "events.currentStrategy",
        "events.backtestParams",
        "basket.currentBasket",
        "layout.theme",
        "layout.language",
        "layout.siderNavigation.collapsed",
        "layout.rightPanel.collapsed",
        "events.currentAccount",
      ],
    }),
    ...(process.env.NODE_ENV !== "production" ? [createLogger()] : []),
  ],
});

export default store;
