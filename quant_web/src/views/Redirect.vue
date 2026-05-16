<template>
  <div></div>
</template>

<script>
import { onMounted } from "vue";
import { useRouter } from "vue-router";

export default {
  name: "Redirect",
  setup() {
    const router = useRouter();

    onMounted(() => {
      // 立即返回上一页
      router.go(-1);
    });

    return {};
  },
};
</script>
