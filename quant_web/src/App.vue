<!-- App.vue - 修复后的根组件 -->
<template>
  <!--
    Naive UI 配置提供器
    负责管理整个应用的主题、语言、组件配置等
  -->
  <n-config-provider
    :theme="theme"
    :theme-overrides="themeOverrides"
    :locale="locale"
    :date-locale="dateLocale"
  >
    <!--
      加载条提供器
      为应用提供顶部加载条功能，用于显示页面加载、API 请求等进度
    -->
    <n-loading-bar-provider>
      <!--
        对话框提供器
        管理全局对话框的显示和状态
      -->
      <n-dialog-provider>
        <!--
          通知提供器
          管理全局通知的显示和状态
        -->
        <n-notification-provider>
          <!--
            消息提供器
            管理全局消息提示的显示和状态
          -->
          <n-message-provider>
            <!--
              全局样式组件
              为 Naive UI 组件提供基础样式支持
            -->
            <n-global-style />

            <!--
              动态布局组件
              根据路由配置动态切换不同的页面布局
            -->
            <component :is="currentLayout">
              <!--
                Vue Router 路由视图
                根据当前路由渲染对应的页面组件
              -->
              <router-view />
            </component>

            <!--
              全局回到顶部组件
              提供页面快速回到顶部的功能
            -->
            <n-back-top :right="20" :bottom="20" />
          </n-message-provider>
        </n-notification-provider>
      </n-dialog-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>

<script lang="ts">
// ============================================================================
// 引入 Vue 和相关依赖
// ============================================================================
import {computed, defineComponent, onMounted, onUnmounted, ref} from "vue"
import {useRoute} from "vue-router"

// ============================================================================
// 引入布局组件
// ============================================================================
import MainLayout from "@/layouts/MainLayout.vue" // 主布局 - 包含侧边栏和头部
import ReportLayout from "@/layouts/ReportLayout.vue" // 报表布局 - 专注于数据展示
import EmptyLayout from "@/layouts/EmptyLayout.vue" // 空布局 - 用于登录页等简单页面
// ============================================================================
// 引入 Naive UI 组件
// ============================================================================
import {
  darkTheme,
  dateZhCN,
  type GlobalTheme,
  type GlobalThemeOverrides,
  NBackTop,
  NConfigProvider,
  NDialogProvider,
  NGlobalStyle,
  NLoadingBarProvider,
  NMessageProvider,
  NNotificationProvider,
  zhCN
} from 'naive-ui'

// ============================================================================
// 引入主题配置
// ============================================================================
import {getThemeOverrides} from '@/assets/themes/naive-theme'

// ============================================================================
// 组件定义
// ============================================================================
export default defineComponent({
  name: "App",

  // ==========================================================================
  // 组件注册
  // ==========================================================================
  components: {
    // 布局组件
    MainLayout,
    ReportLayout,
    EmptyLayout,

    // Naive UI 组件
    NConfigProvider,
    NMessageProvider,
    NDialogProvider,
    NNotificationProvider,
    NLoadingBarProvider,
    NGlobalStyle,
    NBackTop
  },

  // ==========================================================================
  // 组合式 API 设置
  // ==========================================================================
  setup() {
    // ========================================================================
    // 路由和布局管理
    // ========================================================================

    // 获取当前路由信息
    const route = useRoute()

    /**
     * 计算当前布局组件
     * 根据路由元信息中的 layout 字段动态选择布局
     */
    const currentLayout = computed(() => {
      // 从路由元信息获取布局配置，默认为 'main' 布局
      const layout = (route.meta.layout as string) || "main"

      // 布局映射表
      const layoutMap: Record<string, any> = {
        main: MainLayout,      // 主布局 - 默认布局
        report: ReportLayout,  // 报表布局 - 用于数据报表页面
        empty: EmptyLayout,    // 空布局 - 用于登录、错误页等
      }

      // 返回对应的布局组件，如果未找到则使用主布局
      return layoutMap[layout] || MainLayout
    })

    // ========================================================================
    // 主题状态管理
    // ========================================================================

    // 主题状态引用，true 为深色主题，false 为浅色主题
    const isDarkTheme = ref(true)

    /**
     * 计算当前主题对象
     * 根据 isDarkTheme 状态返回对应的 Naive UI 主题
     */
    const theme = computed<GlobalTheme | null>(() => {
      return isDarkTheme.value ? darkTheme : null
    })

    /**
     * 计算主题覆盖配置
     * 根据当前主题状态返回对应的主题覆盖配置
     */
    const themeOverrides = computed<GlobalThemeOverrides>(() => {
      return getThemeOverrides(isDarkTheme.value)
    })

    // ========================================================================
    // 国际化配置
    // ========================================================================

    // 当前语言环境，使用中文
    const locale = zhCN

    // 日期时间语言环境，使用中文
    const dateLocale = dateZhCN

    // ========================================================================
    // 生命周期钩子
    // ========================================================================

    /**
     * 组件挂载后的初始化操作
     */
    onMounted(() => {
      console.log('🎯 App 组件已挂载')

      // 初始化主题状态
      initializeTheme()

      // 监听主题变化事件
      window.addEventListener('theme-change', handleThemeChange)
    })

    /**
     * 组件卸载前的清理操作
     */
    onUnmounted(() => {
      // 移除事件监听器
      window.removeEventListener('theme-change', handleThemeChange)
    })

    // ========================================================================
    // 方法定义
    // ========================================================================

    /**
     * 初始化主题状态
     * 从本地存储读取用户主题偏好
     */
    const initializeTheme = () => {
      try {
        const savedTheme = localStorage.getItem('quant-theme')
        if (savedTheme) {
          isDarkTheme.value = savedTheme === 'dark'
          console.log(`🎨 从本地存储加载主题偏好: ${isDarkTheme.value ? '深色' : '浅色'}`)
        } else {
          // 如果没有保存的偏好，使用系统偏好
          isDarkTheme.value = window.matchMedia('(prefers-color-scheme: dark)').matches
          console.log(`🎨 使用系统主题偏好: ${isDarkTheme.value ? '深色' : '浅色'}`)
        }

        // 更新 HTML 属性 - 使用 dataset 替代 setAttribute（修复 SonarQube 警告）
        updateHtmlThemeAttribute()

      } catch (error) {
        console.warn('⚠️ 主题初始化失败，使用默认深色主题:', error)
        isDarkTheme.value = true
        updateHtmlThemeAttribute()
      }
    }

    /**
     * 处理主题变化事件
     * @param event 主题变化事件
     */
    const handleThemeChange = (event: Event) => {
      const customEvent = event as CustomEvent<{ isDark: boolean }>
      if (customEvent.detail) {
        isDarkTheme.value = customEvent.detail.isDark
        updateHtmlThemeAttribute()
        console.log(`🔄 主题已切换为: ${isDarkTheme.value ? '深色' : '浅色'}`)
      }
    }

    /**
     * 更新 HTML 主题属性
     * 设置 events-theme 和 color-scheme 属性以支持 CSS 主题切换
     * 修复：使用 dataset 替代 setAttribute
     */
    const updateHtmlThemeAttribute = () => {
      const themeValue = isDarkTheme.value ? 'dark' : 'light'
      // 使用 dataset 替代 setAttribute（修复 SonarQube 警告）
      document.documentElement.dataset.theme = themeValue
      document.documentElement.style.setProperty('color-scheme', themeValue)
    }

    // ========================================================================
    // 返回模板使用的数据和方法
    // ========================================================================
    return {
      // 布局相关
      currentLayout,

      // 主题相关
      theme,
      themeOverrides,

      // 国际化相关
      locale,
      dateLocale
    }
  }
})
</script>

<style lang="scss">
// ============================================================================
// 全局样式
// ============================================================================

// 引入简化后的全局样式
@import '@/assets/scss/global.scss';

// 应用容器基础样式
#app {
  // 设置字体渲染优化
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;

  // 设置基础文字颜色
  color: var(--n-text-color-base);

  // 设置最小高度
  min-height: 100vh;
}

// 全局滚动条样式优化
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--n-border-color);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: var(--n-text-color-3);
  border-radius: 3px;

  &:hover {
    background: var(--n-text-color-2);
  }
}

// 选择文本样式
::selection {
  background: rgba(33, 150, 243, 0.3);
  color: inherit;
}

// 打印样式优化
@media print {
  .n-back-top {
    display: none !important;
  }
}
</style>