<!--状态徽章-->
<template>
  <el-tag :type="statusType" size="small" effect="dark" class="status-badge">
    {{ status }}
  </el-tag>
</template>

<script>
export default {
  name: "StatusBadge",
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
  computed: {
    statusType() {
      const statusMap = {
        运行中: "success",
        已停止: "danger",
        已连接: "success",
        连接中: "warning",
        未连接: "danger",
        正常: "success",
        警告: "warning",
        危险: "danger",
      };

      if (this.type !== "default") return this.type;

      return statusMap[this.status] || "info";
    },
  },
};
</script>

<style lang="scss" scoped>
.status-badge {
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.5px;
  min-width: 60px;
  text-align: center;
}

:root {
  --font-weight-medium: 500;
}
</style>