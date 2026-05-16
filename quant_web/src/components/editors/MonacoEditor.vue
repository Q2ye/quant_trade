<script setup lang="ts">
import { ref, onMounted, watch } from "vue";

interface Props {
  modelValue: string;
  language?: string;
  readOnly?: boolean;
  height?: string;
}

const props = withDefaults(defineProps<Props>(), {
  language: "python",
  readOnly: false,
  height: "400px",
});

const emit = defineEmits(["update:modelValue", "change"]);

const editorRef = ref<HTMLDivElement>();
let editor: any = null;
let monaco: any = null;

onMounted(async () => {
  if (!editorRef.value) return;

  // 动态加载Monaco Editor
  monaco = await import("monaco-editor");

  editor = monaco.editor.create(editorRef.value, {
    value: props.modelValue,
    language: props.language,
    theme: "vs-dark",
    readOnly: props.readOnly,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    fontSize: 14,
    lineNumbers: "on",
    roundedSelection: true,
    automaticLayout: true,
  });

  // 监听内容变化
  editor.onDidChangeModelContent(() => {
    const value = editor.getValue();
    emit("update:modelValue", value);
    emit("change", value);
  });
});

watch(
  () => props.modelValue,
  (newValue) => {
    if (editor && editor.getValue() !== newValue) {
      editor.setValue(newValue);
    }
  },
);

watch(
  () => props.language,
  (newLanguage) => {
    if (editor) {
      const model = editor.getModel();
      monaco.editor.setModelLanguage(model, newLanguage);
    }
  },
);

// 暴露编辑器实例方法
defineExpose({
  getValue: () => editor?.getValue(),
  setValue: (value: string) => editor?.setValue(value),
  focus: () => editor?.focus(),
});
</script>

<template>
  <div ref="editorRef" class="monaco-editor" :style="{ height }"></div>
</template>

<style scoped>
.monaco-editor {
  border: 1px solid var(--n-border-color);
  border-radius: 4px;
  overflow: hidden;
}
</style>
