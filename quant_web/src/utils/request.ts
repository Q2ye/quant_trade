// common/request.ts - 优化版本
import axios from "axios";
import { createDiscreteApi } from "naive-ui";
const { message } = createDiscreteApi(["message"]);

// 认证接口自身返回 401 时（密码错误 / token 已失效 / 已登出），只把错误抛给调用方，
// 不再触发"清理登录态 + 派发登出"。否则登出请求 401 会再次进入 401 分支，
// 形成 401 → logout → 401 的无限递归（表现为控制台刷屏）。
const AUTH_ENDPOINTS = [
  "/system/auth/login",
  "/system/auth/logout",
  "/system/auth/refresh",
];
const isAuthEndpoint = (url?: string) =>
  !!url && AUTH_ENDPOINTS.some((path) => url.includes(path));

// 创建axios实例
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 120000,
  withCredentials: false, // 大多数 API 不需要携带 cookie
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    // 优化日志：生产环境减少日志量
    if (import.meta.env.VITE_APP_ENV === "development") {
      console.log("🚀 发送请求:", {
        method: config.method?.toUpperCase(),
        url: config.url,
        baseURL: config.baseURL,
        params: config.params,
        data: config.data,
      });
    }

    // 优化 URL 处理：确保正确的路径格式
    if (config.url) {
      // 移除可能的前导斜杠，避免双斜杠
      // if (config.url.startsWith('/')) {
      //   config.url = config.url.slice(1);
      // }

      // 检查绝对 URL（可能绕过代理）
      if (config.url.startsWith("http")) {
        console.warn("⚠️ 请求使用绝对 URL，可能绕过代理:", config.url);
      }
    }

    // Token 处理 - 使用标准 Bearer token
    const token = localStorage.getItem("token");
    if (token) {
      config.headers = config.headers || {};
      config.headers.Authorization = `Bearer ${token}`;

      if (import.meta.env.VITE_APP_ENV === "development") {
        console.log("✅ 已添加认证 token");
      }
    }

    return config;
  },
  (error) => {
    console.error("❌ 请求拦截器错误:", error);
    return Promise.reject(error);
  },
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    if (import.meta.env.VITE_APP_ENV === "development") {
      console.log("✅ 请求成功:", {
        url: response.config.url,
        status: response.status,
      });
    }
    return response.data;
  },
  (error) => {
    // 网络层错误
    if (error.code === "ECONNABORTED") {
      const errorMsg = "请求超时，请检查网络连接";
      message.error(errorMsg);
      return Promise.reject(new Error(errorMsg));
    }

    // 无响应错误（网络问题/代理问题）
    if (!error.response) {
      const fullURL = error.config?.baseURL + error.config?.url;
      console.error("💥 网络连接失败:", {
        url: fullURL,
        error: error.message,
      });

      // 更具体的错误诊断
      let userMsg = "网络连接失败";
      if (
        error.message.includes("Failed to fetch") ||
        error.message.includes("Network Error")
      ) {
        userMsg =
          "无法连接到服务器，请检查：\n1. 后端服务是否启动\n2. 代理配置是否正确";
      }

      message.error(userMsg);
      return Promise.reject(new Error(userMsg));
    }

    // 服务器返回错误状态码
    const { status, data } = error.response;
    let errorMessage = data?.message || data?.detail || `请求失败: ${status}`;

    switch (status) {
      case 401: {
        // 认证接口自身的 401（密码错误 / token 失效 / 重复登出）不做登出流程
        if (isAuthEndpoint(error.config?.url)) {
          break;
        }
        errorMessage = "登录已过期，请重新登录";
        // 无 token 说明登录态已被清理（并发 401 的后续请求），跳过避免重复处理
        if (!getAuthToken()) {
          break;
        }
        clearAuth();
        // 修复 2026-11（A38）：同步清理 Vuex store（此前只清 localStorage，
        // 登录态残留导致 UI 状态与后端不一致）；这里直接 commit，不再 dispatch
        // user/logout —— 本地 token 已失效，再调登出接口必然 401 并再次进入本分支
        import("@/store")
          .then((m) => {
            const store = m.default;
            store.commit("user/SET_TOKEN", null);
            store.commit("user/SET_USER_INFO", null);
          })
          .catch(() => {});
        // 使用 setTimeout 避免在请求上下文中直接跳转
        setTimeout(() => {
          if (window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
        }, 300);
        break;
      }
      case 403:
        errorMessage = "没有权限访问该资源";
        break;
      case 404:
        errorMessage = `请求的资源不存在: ${error.config?.url}`;
        break;
      case 500:
        errorMessage = "服务器内部错误，请稍后重试";
        break;
      case 502:
      case 503:
        errorMessage = "服务暂时不可用，请稍后重试";
        break;
    }

    message.error(errorMessage);
    return Promise.reject(new Error(errorMessage));
  },
);

// 工具函数
export const setAuthToken = (token: string) => {
  if (token) {
    localStorage.setItem("token", token);
  } else {
    localStorage.removeItem("token");
  }
};

export const getAuthToken = () => {
  return localStorage.getItem("token");
};

export const clearAuth = () => {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
};

export default request;
