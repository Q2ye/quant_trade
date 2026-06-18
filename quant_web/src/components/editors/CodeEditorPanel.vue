<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { NButton } from "naive-ui";
import MonacoEditor from "./MonacoEditor.vue";

interface Props {
  code: string;
  language?: string;
  readOnly?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  language: "python",
  readOnly: false,
});

const emit = defineEmits(["update:code", "save"]);

const localCode = ref(props.code);

// 外部 prop.code 变化时同步到编辑器（如从 API 加载已有策略后）
watch(() => props.code, (newVal) => {
  localCode.value = newVal;
});

const onCodeChange = (value: string) => {
  localCode.value = value;
  emit("update:code", value);
};

const onSave = () => {
  emit("save", localCode.value);
};

// 代码验证状态
const validationErrors = ref<any[]>([]);
const hasErrors = computed(() => validationErrors.value.length > 0);
</script>

<template>
  <div class="code-editor-panel">
    <div class="editor-header">
      <div class="title">策略代码编辑器</div>
      <div class="actions">
        <span class="language-tag">{{ language.toUpperCase() }}</span>
        <NButton size="small" @click="onSave">保存</NButton>
      </div>
    </div>

    <div class="editor-container">
      <MonacoEditor
        v-model="localCode"
        :language="language"
        :read-only="readOnly"
        height="100%"
        @change="onCodeChange"
      />
    </div>

    <div v-if="hasErrors" class="validation-panel">
      <div class="validation-header">
        <span class="error-count">{{ validationErrors.length }} 个错误</span>
      </div>
      <div class="error-list">
        <div
          v-for="error in validationErrors"
          :key="error.line"
          class="error-item"
        >
          <span class="line">第{{ error.line }}行:</span>
          <span class="message">{{ error.message }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.code-editor-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--n-body-color);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--n-border-color);
}

.title {
  font-weight: bold;
  color: var(--n-text-color-1);
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.language-tag {
  background: var(--n-color-target);
  color: white;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.editor-container {
  flex: 1;
  min-height: 0;
}

.validation-panel {
  border-top: 1px solid var(--n-border-color);
  max-height: 120px;
  overflow-y: auto;
}

.validation-header {
  padding: 8px 16px;
  background: var(--n-color-embedded);
  font-size: 12px;
  font-weight: bold;
}

.error-count {
  color: #f56c6c;
}

.error-list {
  padding: 8px 16px;
}

.error-item {
  font-size: 12px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.line {
  color: #e6a23c;
  font-weight: bold;
}

.message {
  color: var(--n-text-color-2);
}
</style>
