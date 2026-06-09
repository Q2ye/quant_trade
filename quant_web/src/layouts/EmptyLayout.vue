<template>
  <div class="empty-layout">
    <router-view />
  </div>
</template>

<script>
export default {
  name: "EmptyLayout",
};
</script>

<style scoped>
.empty-layout {
  min-height: var(--vh-full);
  overflow: hidden;
}
</style>
