import { createLogger, createStore, Store } from "vuex";
import createPersistedState from "vuex-persistedstate";
import basket from "./modules/basket";
import strategy from "./modules/strategy";
import system from "./modules/system";
import trade from "./modules/trade";
import user from "./modules/user";
import dashboard from "./modules/dashboard";
import risk from "./modules/risk";
import { RootState } from "@/types";

const store: Store<RootState> = createStore({
  modules: {
    user,
    basket,
    strategy,
    trade,
    system,
    dashboard,
    risk,
  },
  plugins: [
    createPersistedState({
      key: "quant-platform-v3",
      paths: [
        "user.token",
        "user.userInfo",
        "basket.currentBasket",
      ],
    }),
    ...(process.env.NODE_ENV !== "production" ? [createLogger()] : []),
  ],
});

export default store;
