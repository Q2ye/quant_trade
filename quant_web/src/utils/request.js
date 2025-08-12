// Axios封装
import axios from 'axios';
import {ElMessage} from 'element-plus';
import store from '@/store';

const service = axios.create({
    baseURL: process.env.VUE_APP_BASE_API,
    timeout: 15000
});
service.interceptors.request.use(
    config => {
        const token = store.getters['user/token'];
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        return config;
    },
    error => {
        return Promise.reject(error);
    }
);
service.interceptors.response.use(
    response => {
        const res = response.data;

        if (res.code !== 0) {
            ElMessage({
                message: res.message || 'Error',
                type: 'error',
                duration: 5 * 1000
            });

            if (res.code === 401) {
                store.dispatch('user/logout').then(() => {
                    location.reload();
                });
            }
            return Promise.reject(new Error(res.message || 'Error'));
        } else {
            return res;
        }
    },
    error => {
        ElMessage({
            message: error.message || 'Request Error',
            type: 'error',
            duration: 5 * 1000
        });
        return Promise.reject(error);
    }
);
export default service;