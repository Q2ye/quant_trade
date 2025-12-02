<!-- 数据卡片组件 - 迁移到 Naive UI 和统一图标方案 -->
<template>
  <div class="dashboard-card">
    <!-- 使用 Naive UI 的加载组件 -->
    <n-spin :show="loading">
      <div class="card-header">
        <div
          class="card-icon"
          :style="{ backgroundColor: color + '20', color: color }"
        >
          <!-- 使用 SmartIcon 组件 -->
          <smart-icon :name="getIconName(icon)" />
        </div>
        <div class="card-title">{{ title }}</div>
        <status-badge v-if="status" :status="status" class="status-badge" />
      </div>

      <div class="card-value">
        {{ value }} <span class="unit">{{ unit }}</span>
      </div>

      <div class="card-footer">
        <div v-if="trend !== 0" class="trend" :class="trendClass">
          <!-- 使用 SmartIcon 组件 -->
          <smart-icon 
            :name="trend > 0 ? 'TrendingUp' : 'TrendingDown'" 
            size="16" 
            :class="trendIconClass" 
          />
          <span>{{ Math.abs(trend) }}%</span>
        </div>
        <div class="slot-content">
          <slot></slot>
        </div>
      </div>
    </n-spin>
  </div>
</template>

<script>
import { defineComponent, computed } from 'vue'
import { NSpin } from 'naive-ui'
// 导入 SmartIcon 组件
import SmartIcon from '../common/SmartIcon.vue'
import StatusBadge from "../ui/StatusBadge.vue"

export default defineComponent({
  name: "DashboardCard",
  components: {
    NSpin,
    SmartIcon, // 注册 SmartIcon 组件
    StatusBadge
  },
  props: {
    title: {
      type: String,
      required: true,
    },
    value: {
      type: [String, Number],
      default: "",
    },
    unit: {
      type: String,
      default: "",
    },
    icon: {
      type: String,
      default: "chart",
    },
    color: {
      type: String,
      default: "#18a058", // 使用 Naive UI 的成功色作为默认
    },
    trend: {
      type: Number,
      default: 0,
    },
    status: {
      type: String,
      default: "",
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    // 图标名称映射函数 - 映射到统一的图标名称
    const getIconName = (iconName) => {
      const iconMap = {
        chart: "StatsChart", // 统计图表图标
        user: "PeopleCircle", // 用户图标
        money: "CashOutline" // 金钱图标
      }
      return iconMap[iconName] || "StatsChart"
    }

    const trendClass = computed(() => {
      return props.trend > 0 ? "trend-up" : "trend-down"
    })

    const trendIconClass = computed(() => {
      return props.trend > 0 ? "trend-icon trend-up" : "trend-icon trend-down"
    })

    return {
      getIconName,
      trendClass,
      trendIconClass
    }
  },
})
</script>

<style lang="scss" scoped>
.dashboard-card {
  background-color: var(--n-card-color);
  border-radius: var(--n-border-radius);
  box-shadow: var(--n-box-shadow-1);
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: all 0.3s var(--n-bezier);
  border: 1px solid var(--n-border-color);
}

.dashboard-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--n-box-shadow-2);
}

.card-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  margin-right: 8px;
}

.card-title {
  font-size: 14px;
  color: var(--n-text-color-2);
  flex: 1;
}

.status-badge {
  margin-left: 8px;
}

.card-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--n-text-color-1);
  margin-bottom: 8px;
  line-height: 1.2;
}

.unit {
  font-size: 14px;
  color: var(--n-text-color-3);
  font-weight: 400;
}

.card-footer {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.trend {
  display: flex;
  align-items: center;
  font-size: 13px;
}

.trend-icon {
  margin-right: 4px;
}

.trend-up {
  color: var(--n-success-color);
}

.trend-down {
  color: var(--n-error-color);
}

.slot-content {
  flex: 1;
  text-align: right;
}
</style>