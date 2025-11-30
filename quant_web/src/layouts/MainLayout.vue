<template>
  <div class="main-layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <!-- 顶部状态栏 -->
    <AppHeader class="app-header page-header-anti-bleed"/>

    <!-- 侧边栏和工作区容器 -->
    <div class="layout-container">
      <!-- 左侧导航栏 -->
      <AppSidebar
          class="app-sidebar sidebar-anti-bleed"
          :class="{ collapsed: sidebarCollapsed }"
          @collapse="handleSidebarCollapse"
      />

      <!-- 中间工作区 -->
      <main class="workspace sidebar-content-adapter">
        <div class="workspace-content">
          <router-view/>
        </div>
      </main>
    </div>

    <!-- 底部状态栏 -->
    <footer class="app-footer no-bleed-through">
      <div class="footer-content">
        <div class="footer-section">
          <n-icon size="14" class="footer-icon">
            <ComputerFilled />
          </n-icon>
          <span>CPU: {{ systemStats.cpuUsage }}% | 内存: {{ systemStats.memoryUsage }}%</span>
        </div>
        <div class="footer-section">
          <n-icon size="14" class="footer-icon">
            <CloudSyncFilled />
          </n-icon>
          <span>数据连接: {{ systemStats.dataStatus }}</span>
        </div>
        <div class="footer-section">
          <n-icon size="14" class="footer-icon">
            <SwapHorizFilled />
          </n-icon>
          <span>交易通道: {{ systemStats.tradeStatus }}</span>
        </div>
        <div class="footer-log">
          <n-icon size="14" class="footer-icon">
            <CodeFilled />
          </n-icon>
          <span>{{ systemStats.lastLog }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { NIcon } from 'naive-ui'
import {
  ComputerFilled,        // 系统/CPU图标
  CloudSyncFilled,          // 数据连接图标
  SwapHorizFilled,    // 交易通道图标
  CodeFilled             // 日志/终端图标
} from '@vicons/material'

import AppHeader from '../components/ui/AppHeader.vue'
import AppSidebar from '../components/ui/AppSidebar.vue'

export default {
  name: "MainLayout",
  components: {
    AppHeader,
    AppSidebar,
    NIcon,
    ComputerFilled,
    CloudSyncFilled,
    SwapHorizFilled,
    CodeFilled
  },
  setup() {
    const sidebarCollapsed = ref(false)
    const systemStats = reactive({
      cpuUsage: 0,
      memoryUsage: 0,
      dataStatus: '正常',
      tradeStatus: '已连接',
      lastLog: '[2023-08-20 09:30:05] 策略引擎启动成功'
    })

    const handleSidebarCollapse = (collapsed: boolean) => {
      sidebarCollapsed.value = collapsed
    }

    // 模拟系统状态更新
    let statsInterval: number
    onMounted(() => {
      statsInterval = setInterval(() => {
        systemStats.cpuUsage = Math.floor(Math.random() * 30) + 30
        systemStats.memoryUsage = Math.floor(Math.random() * 20) + 50
      }, 5000) as unknown as number
    })

    onUnmounted(() => {
      clearInterval(statsInterval)
    })

    return {
      sidebarCollapsed,
      systemStats,
      handleSidebarCollapse
    }
  }
}
</script>

<style lang="scss" scoped>
@use 'sass:map'; // 导入Sass的map功能，用于处理键值对数据
@use '@/assets/scss/themes' as *; // 导入主题变量
@use '@/assets/scss/variables' as *; // 导入全局变量
@use '@/assets/scss/mixins' as local_mix; // 导入混入函数

/* 主布局容器 */
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-height: 100vh;
  background: theme-color("primary-bg");
  position: relative;
  transition: background-color theme-animation("transition-normal");
  overflow: hidden;

  /* 关键：定义精确的高度变量 */
  --header-height: #{theme-layout("header-height")}; /* 从主题获取头部高度 */
  --footer-height: 30px; /* 底部状态栏固定高度 */
}

/* 布局内容区域容器 */
.layout-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
  min-height: 0;
  /* 关键：精确计算可用高度，减去头部和底部 */
  height: calc(100vh - var(--header-height) - var(--footer-height));
}

/* 工作区主内容区域 */
.workspace {
  width: calc(100% - #{theme-layout("sidebar-width")});
  transition: all theme-animation("transition-normal");
  background: theme-color("primary-bg");
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;

  /* 工作区内容容器 */
  .workspace-content {
    flex: 1;
    height: 100%;
    min-height: 0;

    /* 确保内部内容适应容器 */
    display: flex;
    flex-direction: column;
    margin-bottom: map.get($spacers, 3); // 底部外边距
    /* 如果内部需要滚动，在特定容器设置 */
    > * {
      flex: 1;
      overflow: hidden;
    }
  }

  /* 侧边栏折叠状态下的样式调整 */
  .sidebar-collapsed & {
    margin-left: 0;
    width: calc(100% - #{theme-layout("sidebar-collapsed-width")});
  }
}

/* 底部状态栏样式 */
.app-footer {
  height: 30px; // 固定高度
  background-color: theme-color("toolbar-bg"); // 工具栏背景色
  border-top: theme-border("border-width") solid theme-color("border-color"); // 顶部边框
  display: flex; // flex布局
  align-items: center; // 垂直居中
  padding: 0 map.get($spacers, 4); // 水平内边距
  font-size: theme-typography("font-size-base") * 0.85; // 字体大小为基准的85%
  color: theme-color("text-secondary"); // 次要文本颜色
  flex-shrink: 0; // 防止在flex容器中收缩
  position: relative; // 相对定位
  z-index: 100; // 较高的堆叠顺序，确保显示在最上层

  /* 底部内容容器 */
  .footer-content {
    display: flex; // flex布局
    align-items: center; // 垂直居中
    width: 100%; // 占满宽度
    margin: 0 auto; // 水平居中
  }

  /* 底部各信息区块 */
  .footer-section {
    display: flex; // flex布局
    align-items: center; // 垂直居中
    margin-right: map.get($spacers, 4); // 右边距
    white-space: nowrap; // 防止文字换行

    /* Naive UI 图标样式 */
    .footer-icon {
      margin-right: map.get($spacers, 1); // 图标右边距
      color: theme-color("accent-color"); // 强调色
    }

    /* 文字样式 */
    span {
      font-size: theme-typography("font-size-base") * 0.8; // 文字大小为基准的80%
      color: theme-color("text-secondary"); // 次要文本颜色
    }
  }

  /* 日志显示区域 */
  .footer-log {
    margin-left: auto; // 自动左边距，推至最右侧
    display: flex; // flex布局
    align-items: center; // 垂直居中
    white-space: nowrap; // 防止文字换行
    overflow: hidden; // 隐藏溢出内容
    text-overflow: ellipsis; // 文字溢出显示省略号
    max-width: 300px; // 最大宽度限制

    /* 日志图标 */
    .footer-icon {
      margin-right: map.get($spacers, 1); // 图标右边距
      color: theme-color("accent-color"); // 强调色
    }

    /* 日志文字 */
    span {
      font-size: theme-typography("font-size-base") * 0.8; // 文字大小
      color: theme-color("text-secondary"); // 次要文本颜色
    }
  }
}

// ========== 响应式设计 ==========

/* 大屏幕尺寸下的响应式调整 */
@include local_mix.media-breakpoint-down(lg) {
  .workspace {
    margin-left: theme-layout("sidebar-collapsed-width"); // 左边距为折叠侧边栏宽度
    width: calc(100% - #{theme-layout("sidebar-collapsed-width")}); // 计算宽度

    /* 侧边栏折叠状态 */
    .sidebar-collapsed & {
      margin-left: 0; // 移除左边距
      width: 100%; // 占满宽度
    }
  }
}

/* 中等屏幕尺寸下的响应式调整 */
@include local_mix.media-breakpoint-down(md) {
  .app-footer {
    .footer-content {
      justify-content: space-between; // 子元素两端对齐
    }

    .footer-section {
      margin-right: map.get($spacers, 3); // 调整右边距

      /* 隐藏第三个区块（交易通道信息） */
      &:nth-child(3) {
        display: none;
      }
    }

    .footer-log {
      max-width: 200px; // 缩小日志区域最大宽度
    }
  }

  .workspace .workspace-content {
    padding: map.get($spacers, 3); // 添加内边距
  }
}

/* 小屏幕尺寸下的响应式调整 */
@include local_mix.media-breakpoint-down(sm) {
  .workspace {
    margin-left: 0; // 移除左边距
    width: 100%; // 占满宽度

    /* 侧边栏折叠状态 */
    .sidebar-collapsed & {
      width: calc(100% - #{theme-layout("sidebar-collapsed-width")}); // 调整宽度
    }
  }

  .app-footer {
    padding: 0 map.get($spacers, 2); // 调整内边距

    .footer-section {
      margin-right: map.get($spacers, 2); // 调整右边距

      /* 隐藏第二个区块（内存信息） */
      &:nth-child(2) {
        display: none;
      }

      /* 调整文字大小 */
      span {
        font-size: theme-typography("font-size-base") * 0.7; // 更小的字体
      }
    }

    .footer-log {
      max-width: 150px; // 进一步缩小日志区域

      /* 调整日志文字大小 */
      span {
        font-size: theme-typography("font-size-base") * 0.7; // 更小的字体
      }
    }
  }

  .workspace .workspace-content {
    padding: map.get($spacers, 2); // 调整内边距
  }
}

// ========== 动画与效果 ==========

/* 侧边栏内容适配器的过渡动画 */
.sidebar-content-adapter {
  transition: all theme-animation("transition-normal"); // 所有属性的过渡动画

  /* 侧边栏折叠时的变换效果 */
  .sidebar-collapsed & {
    transform: theme-animation("hover-transform"); // 悬停变换效果
  }
}

/* 主布局的主题过渡效果 */
.main-layout {
  transition: background-color theme-animation("transition-normal"); // 背景色过渡
}

/* 滚动条样式 - 只应用到内容区域 */
.workspace .workspace-content {
  @include local_mix.custom-scrollbar; // 应用自定义滚动条样式
}

// ========== Naive UI 特定适配 ==========

/* Naive UI 图标在底部状态栏的样式优化 */
.footer-icon {
  flex-shrink: 0; // 防止图标收缩

  /* 确保图标颜色与主题一致 */
  :deep(svg) {
    color: inherit;
  }
}

/* 确保 Naive UI 组件在布局中的正确显示 */
:deep(.n-config-provider) {
  height: 100%;

  /* 确保 Naive UI 组件继承布局的高度 */
  & > * {
    height: 100%;
  }
}

/* Naive UI 全局样式适配 */
:deep(.n-layout) {
  background: transparent; // 透明背景以适配自定义主题

  &.n-layout--absolute-positioned {
    position: relative; // 确保在布局容器中正确定位
  }
}

/* 确保路由视图正确继承样式 */
:deep(.n-layout-scroll-container) {
  height: 100%;
  overflow: auto;

  /* 应用自定义滚动条 */
  @include local_mix.custom-scrollbar;
}
</style>