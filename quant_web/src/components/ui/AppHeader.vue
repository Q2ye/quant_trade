<template>
  <header class="app-header">
    <div class="logo-section">
      <div class="logo">
        <i class="fas fa-chart-line"></i>
        <span class="logo-text">A股量化交易平台</span>
      </div>
    </div>

    <div class="status-section">
      <div class="market-status">
        <div class="status-indicator status-open"></div>
        <span>交易中: 上证 3,245.68 (+1.25%)</span>
      </div>
    </div>

    <div class="header-widgets">
      <div class="header-widget">
        <i class="fas fa-database"></i>
        <span>数据更新: 2023-08-20</span>
      </div>
      <div class="header-widget">
        <i class="fas fa-bolt"></i>
        <span>策略运行: 3/5</span>
      </div>
    </div>

    <div class="time-section">
      <div class="current-time">{{ formattedTime }}</div>
    </div>

    <div class="user-section">
      <el-dropdown @command="handleCommand">
        <div class="user-info">
          <el-avatar icon="el-icon-user-solid" size="small" />
          <span class="user-name">Admin</span>
          <i class="el-icon-arrow-down" />
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人中心</el-dropdown-item>
            <el-dropdown-item command="settings">系统设置</el-dropdown-item>
            <el-dropdown-item divided command="logout"
              >退出登录</el-dropdown-item
            >
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<script>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";

export default {
  name: "AppHeader",
  setup() {
    const router = useRouter();
    const currentTime = ref(new Date());

    const formattedTime = ref("");

    const updateTime = () => {
      currentTime.value = new Date();
      formattedTime.value = currentTime.value.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    };

    let timeInterval;
    onMounted(() => {
      updateTime();
      timeInterval = setInterval(updateTime, 1000);
    });

    onUnmounted(() => {
      clearInterval(timeInterval);
    });

    const handleCommand = (command) => {
      if (command === "logout") {
        router.push("/login");
      } else if (command === "settings") {
        router.push("/system/settings");
      }
    };

    return {
      formattedTime,
      handleCommand,
    };
  },
};
</script>

<style lang="scss" scoped>
@use "@/assets/scss/global.scss";

.app-header {
  height: var(--header-height);
  background-color: var(--secondary-bg);
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  z-index: 100;
}

.logo-section {
  width: 220px;

  .logo {
    display: flex;
    align-items: center;
    font-size: 18px;
    font-weight: bold;
    color: var(--accent-color);

    i {
      margin-right: 10px;
      font-size: 20px;
    }
  }
}

.status-section {
  flex: 1;
  display: flex;
  justify-content: center;
}

.market-status {
  display: flex;
  align-items: center;

  .status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 8px;

    &.status-open {
      background-color: var(--success-color);
    }

    &.status-closed {
      background-color: var(--danger-color);
    }
  }
}

.header-widgets {
  display: flex;
  margin-left: auto;
  gap: 15px;

  .header-widget {
    display: flex;
    align-items: center;
    font-size: 13px;

    i {
      margin-right: 5px;
      color: var(--accent-color);
    }
  }
}

.time-section {
  margin: 0 20px;

  .current-time {
    font-size: 16px;
    font-weight: 500;
    color: var(--text-primary);
  }
}

.user-section {
  margin-left: 10px;

  .user-info {
    display: flex;
    align-items: center;
    cursor: pointer;
    padding: 5px;
    border-radius: 4px;
    transition: all 0.3s;

    &:hover {
      background-color: rgba(255, 255, 255, 0.1);
    }

    .user-name {
      margin: 0 8px;
      font-size: 14px;
      color: var(--text-primary);
    }
  }
}
</style>
