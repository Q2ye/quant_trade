<template>
  <div class="stock-announcements">
    <div v-if="announcements.length === 0" class="empty">暂无公告数据</div>
    <div v-else class="timeline">
      <div
        v-for="(item, index) in announcements"
        :key="index"
        class="timeline-item"
      >
        <div class="timeline-dot"></div>
        <div class="timeline-content">
          <div class="timeline-time">{{ item.time }}</div>
          <NCard size="small">
            <div class="announcement-header">
              <span class="symbol">{{ item.symbol }}</span>
              <NTag :type="getTagType(item.type)" size="small">
                {{ item.type }}
              </NTag>
            </div>
            <p class="title">{{ item.title }}</p>
            <div class="actions">
              <NButton text size="small">查看详情</NButton>
              <NButton text size="small">加入收藏</NButton>
            </div>
          </NCard>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { NCard, NTag, NButton } from "naive-ui";

defineProps<{
  announcements: Array<{
    symbol: string;
    type: string;
    title: string;
    time: string;
  }>;
}>();

const getTagType = (type: string) => {
  switch (type) {
    case "利好":
      return "error";
    case "利空":
      return "success";
    default:
      return "info";
  }
};
</script>

<style scoped>
.stock-announcements {
  height: 250px;
  overflow-y: auto;
  padding: 10px 5px;
}

.empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--n-text-color-3);
}

.timeline {
  position: relative;
  padding-left: 24px;
}

.timeline::before {
  content: "";
  position: absolute;
  left: 8px;
  top: 4px;
  bottom: 4px;
  width: 2px;
  background: var(--n-border-color);
}

.timeline-item {
  position: relative;
  padding-bottom: 16px;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-dot {
  position: absolute;
  left: -16px;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--n-color-target);
  border: 2px solid var(--n-body-color);
  z-index: 1;
}

.timeline-time {
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-bottom: 4px;
}

.announcement-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.symbol {
  font-weight: bold;
  color: var(--n-color-target);
}

.title {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--n-text-color-2);
}

.actions {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}
</style>
