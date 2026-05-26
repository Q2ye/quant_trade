// guard.ts
import { NavigationGuardNext, RouteLocationNormalized } from "vue-router";
import store from "../store";

export const authGuard = (
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) => {
  const publicPages = ["/login", "/register"];
  const authRequired = !publicPages.includes(to.path);

  // 检查本地存储中是否有token，而不是依赖Vuex getter
  const token = localStorage.getItem("token"); // 使用与user模块一致的key
  const isAuthenticated = !!token;

  if (to.path === "/login" && isAuthenticated) {
    return next("/dashboard");
  }

  if (authRequired && !isAuthenticated) {
    next("/login");
  } else {
    next();
  }
};

export const dataReadyGuard = async (
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) => {
  // 跳过公开页面的数据检查
  if (to.path === "/login" || to.path === "/register") {
    return next();
  }

  const token = localStorage.getItem("token");
  if (!token) {
    return next("/login");
  }

  // 检查Vuex user模块是否已加载用户信息
  const userState = (store.state as any).user;
  if (!userState.userInfo) {
    try {
      await store.dispatch("user/fetchUserInfo");
    } catch (error) {
      console.error("Failed to fetch user info:", error);
      // 用户信息获取失败，清除token并重定向到登录页
      localStorage.removeItem("token");
      return next("/login");
    }
  }

  const rootState = store.state as any;
  // 检查系统数据是否已加载
  if (rootState.system?.dataLoaded) {
    next();
  } else {
    try {
      await store.dispatch("system/loadInitialData");
      next();
    } catch (error) {
      console.error("Failed to load initial events:", error);
      // 数据加载失败时仍然允许导航，但显示错误状态
      next();
    }
  }
};

// 布局守卫保持不变...
export const layoutGuard = (
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 一念量化`;
  } else {
    document.title = "一念量化";
  }
  if (from.meta.layout !== to.meta.layout) {
    // 强制重新渲染布局组件
    window.dispatchEvent(new Event("resize"));
  }

  next();
};
