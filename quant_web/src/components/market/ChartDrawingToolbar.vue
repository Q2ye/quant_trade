<script setup lang="ts">
// ChartDrawingToolbar.vue — 图上作业工具条（包 B）
//
// 定位：只负责 UI 与交互提示，不含任何绘制/持久化逻辑（全部在 useChartDrawings）。
// 四态：Loading（禁用）/ Empty（count=0）/ Error（保存失败 toast + 读取失败可重试）/ Data。
import { computed, ref, watch } from "vue";
import { Icon } from "@iconify/vue";
import { NButton, NButtonGroup, NInput, NModal, NTooltip, useMessage } from "naive-ui";
import type { DrawingTool } from "@/composables/useChartDrawings";

const props = withDefaults(
  defineProps<{
    active: DrawingTool | null;
    count: number;
    hasSelection: boolean;
    /** 数据加载中 → 工具条禁用 */
    loading?: boolean;
    /** 只读（非交易时段 / 无权限） */
    disabled?: boolean;
    saving?: boolean;
    saveError?: boolean;
    loadError?: boolean;
    /** 文本标注等待输入 */
    textPending?: boolean;
  }>(),
  {
    loading: false,
    disabled: false,
    saving: false,
    saveError: false,
    loadError: false,
    textPending: false,
  },
);

const emit = defineEmits<{
  select: [tool: DrawingTool];
  delete: [];
  clear: [];
  textSubmit: [text: string];
  textCancel: [];
  retryLoad: [];
}>();

const message = useMessage();

const TOOLS: Array<{ tool: DrawingTool; icon: string; label: string }> = [
  { tool: "trendLine", icon: "mdi:vector-line", label: "趋势线（拖拽两点）" },
  { tool: "horizontalLine", icon: "mdi:minus", label: "水平线（单击落点）" },
  { tool: "verticalLine", icon: "mdi:format-vertical-align-center", label: "垂直线（单击落点）" },
  { tool: "annotationLabel", icon: "mdi:format-text", label: "文本标注（单击后输入）" },
];

const isDisabled = computed(() => props.disabled || props.loading);
const hint = computed(() => {
  if (props.disabled) return "非交易时段 · 只读";
  if (props.active) return "Esc 取消当前工具";
  if (props.hasSelection) return "已选中标注，可删除";
  return "在 K 线上单击选中已有标注";
});

// 保存/读取失败提示（沿四态纪律：不静默）
watch(
  () => props.saveError,
  (v) => {
    if (v) message.error("标注保存失败，已保留在本地，可再次编辑重试");
  },
);
watch(
  () => props.loadError,
  (v) => {
    if (v) message.warning("标注读取失败，当前显示为空（不影响继续绘制）");
  },
);

// ---- 文本标注输入 ----
const textDraft = ref("");

watch(
  () => props.textPending,
  (v) => {
    if (v) textDraft.value = "";
  },
);

function submitText() {
  emit("textSubmit", textDraft.value);
}
</script>

<template>
  <div class="draw-toolbar">
    <n-button-group size="tiny">
      <n-tooltip v-for="t in TOOLS" :key="t.tool" trigger="hover" :delay="400">
        <template #trigger>
          <n-button
            :type="active === t.tool ? 'primary' : 'default'"
            :disabled="isDisabled"
            @click="emit('select', t.tool)"
          >
            <Icon :icon="t.icon" :style="{ fontSize: '14px' }" />
          </n-button>
        </template>
        {{ t.label }}
      </n-tooltip>
    </n-button-group>

    <n-button-group size="tiny" style="margin-left: 8px">
      <n-button
        :disabled="isDisabled || !hasSelection"
        :title="hasSelection ? '删除选中标注' : '先单击选中一条标注'"
        @click="emit('delete')"
      >
        <Icon icon="mdi:delete-outline" :style="{ fontSize: '14px' }" />
      </n-button>
      <n-button
        :disabled="isDisabled || count === 0"
        title="清空当前周期全部标注"
        @click="emit('clear')"
      >
        <Icon icon="mdi:broom" :style="{ fontSize: '14px' }" />
      </n-button>
    </n-button-group>

    <span class="draw-count">
      <Icon
        v-if="saving"
        icon="mdi:content-save-outline"
        :style="{ fontSize: '13px' }"
      />
      {{ count }} 条标注
    </span>

    <n-button
      v-if="loadError"
      size="tiny"
      quaternary
      type="warning"
      @click="emit('retryLoad')"
    >
      <Icon icon="mdi:reload" :style="{ fontSize: '13px' }" />
      读取失败，重试
    </n-button>
    <span v-else class="draw-hint">{{ hint }}</span>

    <n-modal
      :show="textPending"
      preset="dialog"
      title="文本标注"
      positive-text="确定"
      negative-text="取消"
      @positive-click="submitText"
      @negative-click="emit('textCancel')"
      @close="emit('textCancel')"
    >
      <n-input
        v-model:value="textDraft"
        type="text"
        placeholder="输入标注文字（≤50 字）"
        :maxlength="50"
        autofocus
        @keyup.enter="submitText"
      />
    </n-modal>
  </div>
</template>

<style scoped>
.draw-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0 6px;
  flex-wrap: wrap;
}

.draw-count {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--n-text-color-3);
  margin-left: 4px;
}

.draw-hint {
  font-size: 12px;
  color: var(--n-text-color-3);
}
</style>
