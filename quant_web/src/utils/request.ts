// utils/request.ts
import axios from 'axios';

// 创建axios实例
const request = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
    timeout: 30000,
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url);
    console.log('请求参数:', config.params || config.data);

    // 添加token等逻辑
    const token = localStorage.getItem('token');
    if (token) {
      config.params = config.params || {};
      config.params.token = token;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
    (response) => {
        return response.data;
    },
    (error) => {
        console.error('API请求错误:', error);

        // 处理不同的错误状态
        if (error.response) {
            // 服务器返回了错误状态码
            const {status, data} = error.response;

            if (status === 401) {
                // 未授权，清除token并跳转到登录页
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = '/login';
            }

            return Promise.reject(new Error(data.detail || data.message || `请求失败: ${status}`));
        } else if (error.request) {
            // 请求已发出但没有收到响应
            return Promise.reject(new Error('网络错误，请检查网络连接'));
        } else {
            // 其他错误
            return Promise.reject(new Error(error.message || '请求配置错误'));
        }
    }
);

export default request;