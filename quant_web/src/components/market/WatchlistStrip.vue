<script setup lang="ts">
// 自选股条（v5）—— 移出首屏的通栏折叠条，默认收起
import { ref } from "vue";
import { useRouter } from "vue-router";
import { NTag, NSkeleton } from "naive-ui";

defineProps<{
  items: any[];
  loading: boolean;
}>();

const router = useRouter();
const expanded = ref(false);

const pctColor = (v: number | null) => ((v ?? 0) >= 0 ? "#ef5350" : "#26a69a");
</script>

<template>
  <div class="watchlist-strip">
    <div class="ws-bar" @click="expanded = !expanded">
      <span class="ws-title">⭐ 自选 {{ items.length }} 只</span>
      <span class="ws-toggle">{{ expanded ? "收起 ▲" : "点击展开 ▼" }}</span>
    </div>
    <div v-if="expanded" class="ws-body">
      <n-skeleton v-if="loading && !items.length" :text="true" :repeat="1" />
      <n-tag v-else-if="!items.length" size="small" :bordered="false">暂无自选</n-tag>
      <template v-else>
        <n-tag
          v-for="w in items"
          :key="w.ts_code"
          size="small"
          style="cursor: pointer"
          @click="router.push('/market/stock/' + w.ts_code)"
        >
          {{ w.name }}
          <span :style="{ color: pctColor(w.pct_chg) }">
            {{ (w.pct_chg ?? 0) > 0 ? "+" : "" }}{{ w.pct_chg?.toFixed(2) ?? "-" }}%
          </span>
        </n-tag>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.watchlist-strip {
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  .ws-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 14px;
    cursor: pointer;
    user-select: none;
  }
  .ws-title {
    font-size: 12px;
    color: var(--n-text-color-2);
  }
  .ws-toggle {
    font-size: 11px;
    color: var(--n-text-color-3);
  }
  .ws-body {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    padding: 0 14px 10px;
  }
}
</style>
