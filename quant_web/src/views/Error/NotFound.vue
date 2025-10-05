<script setup lang="ts">
import { useRouter } from 'vue-router'
import { HomeOutlined, ArrowLeftOutlined } from '@ant-design/icons-vue'

const router = useRouter()

const goHome = () => {
  router.push('/')
}

const goBack = () => {
  router.back()
}
</script>

<template>
  <div class="not-found-page">
    <a-result
      status="404"
      title="404"
      sub-title="抱歉，您访问的页面不存在。"
    >
      <template #extra>
        <a-space>
          <a-button type="primary" @click="goHome" :icon="HomeOutlined">
            返回首页
          </a-button>
          <a-button @click="goBack" :icon="ArrowLeftOutlined">
            返回上页
          </a-button>
        </a-space>
      </template>
    </a-result>
  </div>
</template>

<style scoped>
.not-found-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}
</style>