<script setup lang="ts">
import { useRouter } from "vue-router";
import { NResult, NButton, NSpace } from "naive-ui";
import SmartIcon from "@/components/common/SmartIcon.vue";

const router = useRouter();

const goHome = () => {
  router.push("/");
};

const goBack = () => {
  router.back();
};
</script>

<template>
  <div class="not-found-page">
    <n-result status="404" title="404" description="抱歉，您访问的页面不存在。">
      <template #footer>
        <n-space justify="center">
          <n-button type="primary" @click="goHome">
            <template #icon>
              <SmartIcon name="Home" />
            </template>
            返回首页
          </n-button>
          <n-button @click="goBack">
            <template #icon>
              <SmartIcon name="ArrowLeft" />
            </template>
            返回上页
          </n-button>
        </n-space>
      </template>
    </n-result>
  </div>
</template>

<style scoped>
.not-found-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--n-card-color);
}
</style>
