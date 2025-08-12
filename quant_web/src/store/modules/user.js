// 用户状态
import api from '../../api/user';

const state = {
    token: localStorage.getItem('token') || null,
    userInfo: null
};
const mutations = {
    SET_TOKEN(state, token) {
        state.token = token;
        if (token) {
            localStorage.setItem('token', token);
        } else {
            localStorage.removeItem('token');
        }
    },
    SET_USER_INFO(state, userInfo) {
        state.userInfo = userInfo;
    }
};
const actions = {
    async login({commit}, credentials) {
        try {
            const response = await api.login(credentials);
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
            const userInfo = await api.getUserInfo();
            commit('SET_USER_INFO', userInfo);
            return userInfo;
        } catch (error) {
            commit('SET_TOKEN', null);
            commit('SET_USER_INFO', null);
            throw error;
        }
    }
};
const getters = {
    isAuthenticated: state => !!state.token,
    token: state => state.token,
    userInfo: state => state.userInfo
};
export default {
    namespaced: true,
    state,
    mutations,
    actions,
    getters
};