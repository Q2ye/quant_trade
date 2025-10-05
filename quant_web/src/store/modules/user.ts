// store/modules/user.ts
import { Module } from 'vuex';
import authApi from '../../api/auth';
import userApi from '../../api/user';
import { RootState } from "@/types";
import { User } from '@/types/entities/user'; // 使用entities的User类型
import { AuthResponse } from '@/api/auth';
import {UserConverter} from "@/types/utils/converters/userConverter";

interface UserState {
    token: string | null;
    userInfo: User | null; // 使用entities的User类型
}

const userModule: Module<UserState, RootState> = {
    namespaced: true,
    state: {
        token: localStorage.getItem('token') || null,
        userInfo: null
    },
    mutations: {
        SET_TOKEN(state, token: string | null) {
            state.token = token;
            if (token) {
                localStorage.setItem('token', token);
            } else {
                localStorage.removeItem('token');
            }
        },
        SET_USER_INFO(state, userInfo: User | null) {
            state.userInfo = userInfo;
            if (userInfo) {
                // 只存储必要信息，避免存储敏感数据
                const storageUser = {
                    id: userInfo.id,
                    username: userInfo.username,
                    email: userInfo.email,
                    role: userInfo.role,
                    preferences: userInfo.preferences
                };
                localStorage.setItem('user', JSON.stringify(storageUser));
            } else {
                localStorage.removeItem('user');
            }
        }
    },
    actions: {
        async login({ commit }, credentials: { username: string; password: string }) {
            try {
                const response: AuthResponse = await authApi.login(credentials);
                commit('SET_TOKEN', response.token);

                // 关键修改：进行数据转换
                const userEntity: User = UserConverter.fromApiResponse(response.user);
                commit('SET_USER_INFO', userEntity);

                return { ...response, user: userEntity }; // 返回转换后的数据
            } catch (error) {
                commit('SET_TOKEN', null);
                commit('SET_USER_INFO', null);
                throw error;
            }
        },
        async logout({ commit }) {
            try {
                await authApi.logout();
            } catch (error) {
                console.warn('Logout API call failed, but clearing local state anyway:', error);
            } finally {
                commit('SET_TOKEN', null);
                commit('SET_USER_INFO', null);
            }
        },
        async fetchUserInfo({ commit }) {
            try {
                const apiUser = await userApi.getCurrentUser();

                // 关键修改：进行数据转换
                const userEntity: User = UserConverter.fromApiResponse(apiUser);
                commit('SET_USER_INFO', userEntity);

                return userEntity; // 返回转换后的实体
            } catch (error) {
                commit('SET_TOKEN', null);
                commit('SET_USER_INFO', null);
                throw error;
            }
        }
    },
    getters: {
        isAuthenticated: state => !!state.token,
        token: state => state.token,
        userInfo: state => state.userInfo,

        // 添加有用的getters
        userPreferences: state => state.userInfo?.preferences,
        userRole: state => state.userInfo?.role,
        hasPermission: (state) => (module: string, action: 'read' | 'write' | 'execute') => {
            // 这里可以根据需要实现权限检查逻辑
            if (!state.userInfo) return false;
            // 简单的基于角色的权限检查
            if (state.userInfo.role === 'admin') return true;
            // 可以扩展更复杂的权限逻辑
            return false;
        }
    }
};

export default userModule;