<!-- 状态徽章组件 - 迁移到 Naive UI -->
<template>
  <n-tag :type="statusType" size="small" :bordered="false" class="status-badge">
    {{ status }}
  </n-tag>
</template>

<script>
import { defineComponent, computed } from 'vue'
import { NTag } from 'naive-ui'

export default defineComponent({
  name: "StatusBadge",
  components: {
    NTag
  },
  props: {
    status: {
      type: String,
      required: true,
    },
    type: {
      type: String,
      default: "default",
    },
  },
  setup(props) {
    const statusType = computed(() => {
      if (props.type !== "default") return props.type

      const statusMap = {
        "运行中": "success",
        "已停止": "error",
        "已连接": "success",
        "连接中": "warning",
        "未连接": "error",
        "正常": "success",
        "警告": "warning",
        "危险": "error",
        "成功": "success",
        "失败": "error",
        "进行中": "info",
        "待处理": "default"
      }

      return statusMap[props.status] || "default"
    })

    return {
      statusType,
    }
  },
})
</script>

<style lang="scss" scoped>
.status-badge {
  font-weight: 500;
  letter-spacing: 0.5px;
  min-width: 60px;
  text-align: center;
}
</style>