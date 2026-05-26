// main.ts - 修复后的主入口文件
import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import store from "./store";
import i18n from "./locales";

// 引入 ECharts 库
import * as echarts from "echarts";

// 引入 Iconify 图标组件
import { Icon } from "@iconify/vue";

// ============================================================================
// Naive UI 完整引入
// ============================================================================
import {
  // 配置提供器
  NConfigProvider,

  // 消息相关提供器
  NMessageProvider,
  NNotificationProvider,
  NDialogProvider,
  NLoadingBarProvider,

  // 布局组件
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NLayoutContent,
  NLayoutFooter,

  // 导航组件
  NMenu,
  NBreadcrumb,
  NBreadcrumbItem,
  NDropdown,

  // 数据展示组件
  NDataTable,
  NCard,
  NCollapse,
  NCollapseItem,
  NStatistic,
  NTag,
  NTimeline,
  NTimelineItem,
  NList,
  NListItem,
  NThing,
  NAvatar,
  NAvatarGroup,
  NBadge,
  NRate,
  NProgress,
  NCalendar,

  // 数据输入组件
  NButton,
  NButtonGroup,
  NInput,
  NInputNumber,
  NInputGroup,
  NInputGroupLabel,
  NSelect,
  NRadio,
  NRadioGroup,
  NRadioButton,
  NCheckbox,
  NCheckboxGroup,
  NSwitch,
  NSlider,
  NDatePicker,
  NTimePicker,
  NUpload,
  NUploadDragger,
  NColorPicker,
  NForm,
  NFormItem,
  NFormItemGi,
  NGrid,
  NGridItem,
  NDynamicInput,

  // 反馈组件
  NModal,
  NDrawer,
  NDrawerContent,
  NPopconfirm, // 修复拼写错误
  NPopover,
  NPopselect, // 修复拼写错误
  NTooltip,
  NAlert,
  NSpin,
  NEmpty,
  NResult,
  NSkeleton,

  // 其他组件
  NDivider,
  NScrollbar,
  NBackTop,
  NAnchor,
  NAnchorLink,
  NAffix,
  NGlobalStyle,
  NEllipsis,
  NElement,
  NText,
  NP,
  NH1,
  NH2,
  NH3,
  NH4,
  NH5,
  NH6,
  NBlockquote,
  NUl,
  NOl,
  NLi,
  NHr,

  // 工具函数
  createDiscreteApi,

  // 主题相关
  darkTheme,
} from "naive-ui";

// 引入主题配置
import {
  getThemeOverrides,
  injectThemeCSSVariables,
  setCurrentThemeMode,
} from "@/assets/themes/naive-theme";

// 注册全局指令
import resize from "./directives/resize";

// ============================================================================
// 创建 Vue 应用实例
// ============================================================================
const app = createApp(App);

// ============================================================================
// 全局组件注册
// ============================================================================

// 注册图标组件
app.component("Icon", Icon);

// 注册所有 Naive UI 组件
const naiveComponents = {
  NConfigProvider,
  NMessageProvider,
  NNotificationProvider,
  NDialogProvider,
  NLoadingBarProvider,
  NLayout,
  NLayoutHeader,
  NLayoutSider,
  NLayoutContent,
  NLayoutFooter,
  NMenu,
  NBreadcrumb,
  NBreadcrumbItem,
  NDropdown,
  NDataTable,
  NCard,
  NCollapse,
  NCollapseItem,
  NStatistic,
  NTag,
  NTimeline,
  NTimelineItem,
  NList,
  NListItem,
  NThing,
  NAvatar,
  NAvatarGroup,
  NBadge,
  NRate,
  NProgress,
  NCalendar,
  NButton,
  NButtonGroup,
  NInput,
  NInputNumber,
  NInputGroup,
  NInputGroupLabel,
  NSelect,
  NRadio,
  NRadioGroup,
  NRadioButton,
  NCheckbox,
  NCheckboxGroup,
  NSwitch,
  NSlider,
  NDatePicker,
  NTimePicker,
  NUpload,
  NUploadDragger,
  NColorPicker,
  NForm,
  NFormItem,
  NFormItemGi,
  NGrid,
  NGridItem,
  NDynamicInput,
  NModal,
  NDrawer,
  NDrawerContent,
  NPopconfirm, // 修复拼写错误
  NPopover,
  NPopselect, // 修复拼写错误
  NTooltip,
  NAlert,
  NSpin,
  NEmpty,
  NResult,
  NSkeleton,
  NDivider,
  NScrollbar,
  NBackTop,
  NAnchor,
  NAnchorLink,
  NAffix,
  NGlobalStyle,
  NEllipsis,
  NElement,
  NText,
  NP,
  NH1,
  NH2,
  NH3,
  NH4,
  NH5,
  NH6,
  NBlockquote,
  NUl,
  NOl,
  NLi,
  NHr,
};

// 批量注册 Naive UI 组件
Object.entries(naiveComponents).forEach(([name, component]) => {
  app.component(name, component);
});

// ============================================================================
// 全局属性配置
// ============================================================================

// 设置 ECharts 为全局属性
app.config.globalProperties.$echarts = echarts;

// ============================================================================
// Naive UI 离散 API 配置
// ============================================================================

// 创建 Naive UI 离散 API 实例（用于在非 setup 上下文中使用）
const { message, notification, dialog, loadingBar } = createDiscreteApi(
  ["message", "dialog", "notification", "loadingBar"],
  {
    // 配置离散组件的主题
    configProviderProps: {
      theme: darkTheme,
      themeOverrides: getThemeOverrides(true), // 默认使用深色主题
    },
  },
);

// 设置为全局属性，以便在任何地方使用
app.config.globalProperties.$naiveMessage = message;
app.config.globalProperties.$naiveNotification = notification;
app.config.globalProperties.$naiveDialog = dialog;
app.config.globalProperties.$naiveLoadingBar = loadingBar;

// ============================================================================
// 插件注册
// ============================================================================

// 使用 Vuex 状态管理
app.use(store);

// 使用 Vue Router 路由
app.use(router);

// 使用国际化
app.use(i18n);

// 注册自定义指令
app.directive("resize", resize);

// ============================================================================
// 应用初始化函数
// ============================================================================

/**
 * 初始化应用
 * 在应用挂载前执行必要的初始化操作
 */
async function initializeApp() {
  try {
    console.log("🚀 开始初始化量化交易平台...");

    // 初始化主题系统
    await initializeThemeSystem();

    // 初始化用户偏好设置
    await initializeUserPreferences();

    // 挂载应用
    app.mount("#app");

    console.log("✅ 应用初始化完成，已成功挂载到 DOM");

    // 发送应用就绪事件，通知其他模块应用已准备就绪
    document.dispatchEvent(new Event("vue-app-ready"));

    console.log("📢 应用就绪事件已发送");
  } catch (error) {
    console.error("❌ 应用初始化失败:", error);

    // 即使初始化失败也尝试挂载应用，保证基本功能可用
    try {
      app.mount("#app");
      console.log("⚠️ 应用在降级模式下成功挂载");
    } catch (mountError) {
      console.error("💥 应用挂载完全失败:", mountError);
    }
  }
}

/**
 * 初始化主题系统
 * 从本地存储加载用户主题偏好，或使用系统默认主题
 */
async function initializeThemeSystem() {
  try {
    // 从 localStorage 读取用户主题偏好
    const savedTheme = localStorage.getItem("quant-theme");
    const isDark = savedTheme ? savedTheme === "dark" : true; // 默认为深色主题

    console.log(`🎨 初始化主题系统，使用${isDark ? "深色" : "浅色"}主题`);

    // 使用 dataset 而不是 setAttribute（修复 SonarQube 警告）
    document.documentElement.dataset.theme = isDark ? "dark" : "light";

    // 设置主题颜色方案
    document.documentElement.style.setProperty(
      "color-scheme",
      isDark ? "dark" : "light",
    );

    // 注入主题 CSS 变量到 DOM（--color-* 系列），供 SCSS 系统使用
    injectThemeCSSVariables(isDark);
    setCurrentThemeMode(isDark);
  } catch (error) {
    console.warn("⚠️ 主题系统初始化失败，使用默认深色主题:", error);
    // 失败时使用默认深色主题
    document.documentElement.dataset.theme = "dark";
    document.documentElement.style.setProperty("color-scheme", "dark");
    injectThemeCSSVariables(true);
    setCurrentThemeMode(true);
  }
}

/**
 * 初始化用户偏好设置
 * 加载用户保存的个性化配置
 */
async function initializeUserPreferences() {
  try {
    // 可以在这里加载用户的其他偏好设置
    // 例如：语言设置、布局偏好、表格配置等

    console.log("⚙️ 用户偏好设置初始化完成");
  } catch (error) {
    console.warn("⚠️ 用户偏好设置初始化失败:", error);
  }
}

// ============================================================================
// 启动应用
// ============================================================================

// 启动应用
initializeApp().catch((error) => {
  console.error("💥 应用启动过程中发生未处理的错误:", error);
});

// ============================================================================
// 开发环境调试支持
// ============================================================================

// 在开发环境下将应用实例暴露给全局，方便调试
// 修复：使用 globalThis 替代 window（修复 ESLint 警告）
if (import.meta.env.VITE_APP_ENV) {
  // @ts-ignore
  globalThis.__QUANT_APP__ = app;
  console.log("🔧 开发模式：应用实例已暴露到 globalThis.__QUANT_APP__");
}
