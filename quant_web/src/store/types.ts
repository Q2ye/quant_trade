import { Module } from 'vuex';

// 系统模块状态
export interface SystemState {
  dataLoaded: boolean;
  lastSyncTime: string | null;
  // 其他系统状态...
}

// 用户模块状态
export interface UserState {
  isAuthenticated: boolean;
  username: string | null;
  // 其他用户状态...
}

// 根状态类型
export interface RootState {
  system: SystemState;
  user: UserState;
  // 其他模块状态...
}

// 模块类型辅助
export type VuexModule<T> = Module<T, RootState>;