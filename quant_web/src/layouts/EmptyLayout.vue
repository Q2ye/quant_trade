<template>
  <div class="empty-layout">
    <router-view />
  </div>
</template>

<script>
export default {
  name: "EmptyLayout"
}
</script>

<style scoped>
.empty-layout {
  height: 100vh;
  overflow: hidden;
}
</style>