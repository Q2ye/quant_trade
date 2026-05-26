// Vuex工具类型定义

import { Module } from "vuex";
import { RootState } from "./state-root-state";

/**
 * Vuex模块类型定义
 * @template T 模块状态类型
 */
export type VuexModule<T> = Module<T, RootState>;

/**
 * Vuex Action上下文接口
 * @template S 当前模块状态类型
 * @template R 根状态类型
 */
export interface ActionContext<S, R> {
  dispatch: any; // dispatch方法
  commit: any; // commit方法
  state: S; // 当前模块状态
  getters: any; // 当前模块getters
  rootState: R; // 根状态
  rootGetters: any; // 根getters
}

/**
 * Vuex Getter函数类型
 * @template T 当前模块状态类型
 * @template R 返回值类型
 */
export type Getter<T, R> = (state: T, getters: any, rootState: RootState) => R;

/**
 * Vuex Action函数类型
 * @template S 当前模块状态类型
 * @template R 根状态类型
 * @template P 参数类型
 * @template Result 返回结果类型
 */
export type Action<S, R, P = any, Result = any> = (
  context: ActionContext<S, R>,
  payload: P,
) => Promise<Result> | Result;

/**
 * Vuex Mutation函数类型
 * @template S 当前模块状态类型
 * @template P 参数类型
 */
export type Mutation<S, P = any> = (state: S, payload: P) => void;

/**
 * Vuex Module配置接口
 * @template S 模块状态类型
 * @template G Getters类型
 * @template M Mutations类型
 * @template A Actions类型
 */
export interface VuexModuleConfig<S, G = any, M = any, A = any> {
  namespaced?: boolean; // 是否启用命名空间
  state: S | (() => S); // 状态
  getters?: { [K in keyof G]: Getter<S, G[K]> }; // Getters
  mutations?: { [K in keyof M]: Mutation<S, M[K]> }; // Mutations
  actions?: { [K in keyof A]: Action<S, RootState, A[K]> }; // Actions
  modules?: Record<string, VuexModule<any>>; // 子模块
}

/**
 * 映射Getters辅助类型
 */
export type MappedGetters<T> = {
  [K in keyof T]: () => T[K];
};

/**
 * 映射Mutations辅助类型
 */
export type MappedMutations<T> = {
  [K in keyof T]: (payload?: T[K]) => void;
};

/**
 * 映射Actions辅助类型
 */
export type MappedActions<T> = {
  [K in keyof T]: (payload?: T[K]) => Promise<any>;
};

/**
 * Vuex Store创建选项接口
 */
export interface StoreOptions {
  strict?: boolean; // 是否启用严格模式
  devtools?: boolean; // 是否启用devtools
  plugins?: any[]; // 插件数组
}
