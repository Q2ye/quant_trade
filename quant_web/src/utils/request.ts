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
    // 添加token等逻辑 - 使用与user模块一致的key
    const token = localStorage.getItem('token');
    if (token) {
      // 根据后端API，token可能需要在查询参数中传递
      if (config.method === 'get' || config.method === 'delete') {
        config.params = config.params || {};
        config.params.token = token;
      } else if (config.method === 'post' || config.method === 'put') {
        // 对于POST/PUT请求，根据后端API决定是放在body还是查询参数
        // 这里假设后端API期望token在查询参数中
        config.params = config.params || {};
        config.params.token = token;
      }
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
      const { status, data } = error.response;

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