import {Module} from 'vuex';
import api, {LoginResponse, User} from '../../api/user';
import {RootState} from '../types';

interface UserState {
    token: string | null;
    userInfo: User | null;
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
                localStorage.setItem('user', JSON.stringify(userInfo));
            } else {
                localStorage.removeItem('user');
            }
        }
    },
    actions: {
        async login({commit}, credentials: { username: string; password: string }) {
            try {
                const response: LoginResponse = await api.login(credentials);
                commit('SET_TOKEN', response.token);
                commit('SET_USER_INFO', response.user);
                return response;
            } catch (error) {
                commit('SET_TOKEN', null);
                commit('SET_USER_INFO', null);
                throw error;
            }
        },
        async logout({commit}) {
            try {
                await api.logout();
            } finally {
                commit('SET_TOKEN', null);
                commit('SET_USER_INFO', null);
            }
        },
        async fetchUserInfo({commit}) {
            try {
                const userInfo: User = await api.getUserInfo();
                commit('SET_USER_INFO', userInfo);
                return userInfo;
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
        userInfo: state => state.userInfo
    }
};

export default userModule;