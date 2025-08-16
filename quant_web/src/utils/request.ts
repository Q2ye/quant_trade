import axios, { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { ElMessage } from 'element-plus';
import store from '@/store';

const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_API as string,
  timeout: 15000
});

service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = store.getters['user/token'];
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    // 确保返回 Error 对象
    const errorMessage = error.message || 'Request Configuration Error';
    return Promise.reject(new Error(errorMessage));
  }
);

service.interceptors.response.use(
  (response: AxiosResponse) => {
    const res = response.data;

    if (res.code !== 0) {
      const errorMessage = res.message || 'Error';
      ElMessage({
        message: errorMessage,
        type: 'error',
        duration: 5 * 1000
      });

      if (res.code === 401) {
        store.dispatch('user/logout').then(() => {
          location.reload();
        });
      }
      // 确保返回 Error 对象（第19行修复）
      return Promise.reject(new Error(errorMessage));
    } else {
      return res;
    }
  },
  (error) => {
    // 从错误对象中提取消息
    const errorMessage = error.response?.data?.message || 
                         error.message || 
                         'Request Error';
    
    ElMessage({
      message: errorMessage,
      type: 'error',
      duration: 5 * 1000
    });
    
    // 确保返回 Error 对象
    return Promise.reject(new Error(errorMessage));
  }
);

export default service;