<!-- 预警提示组件 - 迁移到 Naive UI 和统一图标方案 -->
<template>
  <n-alert
    v-if="alert"
    :type="alertType"
    :title="alert.title"
    closable
    @close="$emit('dismiss', alert.id)"
    class="app-alert"
  >
    <template #icon>
      <!-- 使用 SmartIcon 组件 -->
      <smart-icon :name="getAlertIcon(alert.level)" />
    </template>

    {{ alert.content }}

    <template #action>
      <n-button
        v-if="alert.action"
        text
        type="primary"
        size="small"
        @click="$emit('action', alert)"
      >
        {{ alert.action }}
      </n-button>
    </template>
  </n-alert>
</template>

<script>
import { defineComponent, computed } from 'vue'
import { NAlert, NButton } from 'naive-ui'
// 导入 SmartIcon 组件
import SmartIcon from '../common/SmartIcon.vue'

export default defineComponent({
  name: "AppAlert",
  components: {
    NAlert,
    NButton,
    SmartIcon // 注册 SmartIcon 组件
  },
  props: {
    alert: {
      type: Object,
      required: true,
      default: () => ({
        level: "info",
        title: "",
        content: "",
        timestamp: Date.now(),
        id: Date.now().toString(),
      }),
    },
  },
  emits: ["action", "dismiss"],
  setup(props) {
    const alertType = computed(() => {
      const level = props.alert?.level || "info"
      switch (level) {
        case "critical":
          return "error"
        case "warning":
          return "warning"
        default:
          return "info"
      }
    })

    // 获取警告图标 - 使用统一的图标名称
    const getAlertIcon = (level) => {
      const iconMap = {
        critical: "Warning", // 严重警告图标
        warning: "AlertCircle", // 警告图标
        info: "InformationCircle" // 信息图标
      }
      return iconMap[level] || "InformationCircle"
    }

    return {
      alertType,
      getAlertIcon
    }
  },
})
</script>

<style lang="scss" scoped>
.app-alert {
  margin-bottom: 8px;
  transition: all 0.3s var(--n-bezier);

  &:hover {
    transform: translateY(-1px);
    box-shadow: var(--n-box-shadow-2);
  }
}
</style>