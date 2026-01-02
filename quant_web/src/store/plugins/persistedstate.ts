// 插件
// store/plugins/persistedstate.ts
import { Plugin } from 'vuex'
import { RootState } from "@/types/state";

// 持久化配置接口
interface PersistedStateConfig {
  key?: string
  paths?: string[]
  storage?: Storage
  getState?: (key: string, storage: Storage) => any
  setState?: (key: string, state: any, storage: Storage) => void
  reducer?: (state: RootState, paths: string[]) => object
  subscriber?: (store: any) => (handler: any) => void
  filter?: (mutation: any) => boolean
  arrayMerger?: (state: any[], saved: any[]) => any
  rehydrated?: (store: any) => void
  fetchBeforeUse?: boolean
  overwrite?: boolean
}

// 创建持久化插件
export function createPersistedState(config: PersistedStateConfig = {}): Plugin<RootState> {
  const {
    key = 'vuex',
    paths = [],
    storage = localStorage,
    getState = defaultGetState,
    setState = defaultSetState,
    reducer = defaultReducer,
    subscriber = defaultSubscriber,
    filter = () => true,
    arrayMerger = defaultArrayMerger,
    rehydrated,
    fetchBeforeUse = false,
    overwrite = false
  } = config

  return (store) => {
    // 获取保存的状态
    const savedState = getState(key, storage)

    if (savedState) {
      // 合并状态
      store.replaceState(overwrite
        ? savedState
        : merge(store.state, savedState, arrayMerger)
      )
    }

    // 监听mutation并保存状态
    const unsubscribe = subscriber(store)((mutation: any, state: RootState) => {
      if (filter(mutation)) {
        setState(key, reducer(state, paths), storage)
      }
    })

    // 触发rehydrated回调
    if (rehydrated) {
      rehydrated(store)
    }

    // 如果需要在使用前获取最新状态
    if (fetchBeforeUse) {
      const latestState = getState(key, storage)
      if (latestState) {
        store.replaceState(merge(store.state, latestState, arrayMerger))
      }
    }

    // 返回取消订阅函数（虽然Vuex插件通常不返回，但这是良好的实践）
    // return () => { unsubscribe && unsubscribe() }
  }
}

// 默认获取状态方法
function defaultGetState(key: string, storage: Storage): any {
  const value = storage.getItem(key)
  try {
    return value && value !== 'undefined' ? JSON.parse(value) : undefined
  } catch {
    return undefined
  }
}

// 默认设置状态方法
function defaultSetState(key: string, state: any, storage: Storage): void {
  storage.setItem(key, JSON.stringify(state))
}

// 默认reducer - 提取指定路径的状态
function defaultReducer(state: RootState, paths: string[]): object {
  return paths.reduce((subState, path) => {
    const pathArray = path.split('.')
    return set(subState, pathArray, get(state, pathArray))
  }, {})
}

// 默认订阅者 - 监听所有mutation
function defaultSubscriber(store: any): (handler: any) => void {
  return (handler) => store.subscribe(handler)
}

// 默认数组合并策略 - 用保存的数组覆盖当前数组
function defaultArrayMerger(_state: any[], saved: any[]): any {
  return saved
}

// 工具函数 - 获取嵌套对象属性
function get(obj: any, path: string[]): any {
  return path.reduce((current, key) => {
    return current ? current[key] : undefined
  }, obj)
}

// 工具函数 - 设置嵌套对象属性
function set(obj: any, path: string[], value: any): any {
  const lastKey = path.pop()
  const target = path.reduce((current, key) => {
    if (!current[key] || typeof current[key] !== 'object') {
      current[key] = {}
    }
    return current[key]
  }, obj)

  if (lastKey) {
    target[lastKey] = value
  }

  return obj
}

// 深度合并对象
function merge(target: any, source: any, arrayMerger: (state: any[], saved: any[]) => any): any {
  if (isObject(target) && isObject(source)) {
    for (const key in source) {
      if (source.hasOwnProperty(key)) {
        if (Array.isArray(target[key]) && Array.isArray(source[key])) {
          target[key] = arrayMerger(target[key], source[key])
        } else if (isObject(target[key]) && isObject(source[key])) {
          merge(target[key], source[key], arrayMerger)
        } else {
          target[key] = source[key]
        }
      }
    }
  }
  return target
}

// 检查是否为对象
function isObject(obj: any): boolean {
  return obj !== null && typeof obj === 'object' && !Array.isArray(obj)
}

// 定义持久化状态类型
interface PersistedReducedState {
  user?: {
    userInfo?: any;
    token?: string;
    preferences?: any;
  };
  layout?: {
    sidebarCollapsed?: boolean;
    theme?: string;
  };
  trade?: {
    recentSymbols?: any[];
  };
  strategy?: {
    recentStrategies?: any[];
  };
  strategyStudio?: {
    editor?: any;
    parameters?: any;
    backtestConfig?: any;
  };
}

// 针对量化交易平台的定制化配置
export const quantPersistedState = createPersistedState({
  key: 'quant-trading-platform',
  paths: [
    'user.userInfo',
    'user.token',
    'user.preferences',
    'layout.sidebarCollapsed',
    'layout.theme',
    'events.recentSymbols',
    'events.recentStrategies',
    'strategyStudio.editor',
    'strategyStudio.parameters',
    'strategyStudio.backtestConfig'
  ],
  storage: localStorage,

  // 自定义reducer，处理敏感数据
  reducer: (state: RootState, paths: string[]): PersistedReducedState => {
    const reduced = defaultReducer(state, paths) as PersistedReducedState;

    // 移除敏感信息
    if (reduced.user && reduced.user.userInfo) {
      const { password, ...safeUserInfo } = reduced.user.userInfo;
      reduced.user.userInfo = safeUserInfo;
    }

    return reduced;
  },

  // 过滤mutation，只有重要变化才保存
  filter: (mutation) => {
    const persistMutations = [
      'user/SET_USER_INFO',
      'user/SET_TOKEN',
      'user/UPDATE_PREFERENCES',
      'layout/TOGGLE_SIDEBAR',
      'layout/SET_THEME',
      'events/ADD_RECENT_SYMBOL',
      'events/ADD_STRATEGY',
      'strategyStudio/UPDATE_EDITOR_SETTINGS',
      'strategyStudio/UPDATE_PARAMETER',
      'strategyStudio/UPDATE_BACKTEST_CONFIG'
    ];

    return persistMutations.includes(mutation.type);
  },

  // 数组合并策略 - 对于交易相关数据，保留最新项
  arrayMerger: (state: any[], saved: any[]) => {
    // 对于最近交易标的，合并并去重，保留最新的20个
    if (state && state.length > 0 && saved && saved.length > 0) {
      const merged = [...state, ...saved];
      const unique = Array.from(new Map(merged.map(item => [item.symbol || item.id, item])).values());
      return unique.slice(0, 20);
    }
    return saved || state;
  },

  // 重hydrated回调
  rehydrated: (store) => {
    console.log('Vuex状态恢复完成');

    // 恢复后的一些初始化操作
    if (store.state.user.token) {
      // 自动重新连接WebSocket等
      // 注意：这里需要根据实际项目调整，确保websocket模块存在
      if (store.dispatch('websocket/reconnect')) {
        store.dispatch('websocket/reconnect');
      }
    }
  }
});

// 导出默认函数
export default createPersistedState;