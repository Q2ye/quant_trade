<!--策略代码编辑器（Monaco集成）-->
<template>
  <div ref="editor" class="monaco-editor"></div>
</template>

<script>
import * as monaco from 'monaco-editor';
import { onMounted, ref, watch } from 'vue';

export default {
  props: {
    code: {
      type: String,
      default: ''
    },
    language: {
      type: String,
      default: 'python'
    },
    readOnly: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:code'],
  setup(props, { emit }) {
    const editor = ref(null);
    let monacoEditor = null;

    // 初始化策略API的自动补全
    const setupIntellisense = () => {
      monaco.languages.registerCompletionItemProvider('python', {
        provideCompletionItems: () => {
          return {
            suggestions: [
              {
                label: 'order_target_percent',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'order_target_percent(symbol, percent)',
                documentation: '按目标百分比调整持仓'
              },
              {
                label: 'history',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'history(field, count, frequency="1d")',
                documentation: '获取历史数据'
              },
              {
                label: 'get_current_price',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'get_current_price(symbol)',
                documentation: '获取当前价格'
              },
              {
                label: 'log',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'log(message, level="info")',
                documentation: '记录日志'
              },
              {
                label: 'set_commission',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'set_commission(commission=0.0003)',
                documentation: '设置交易手续费'
              },
              {
                label: 'set_slippage',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'set_slippage(slippage=0.001)',
                documentation: '设置交易滑点'
              },
              {
                label: 'get_position',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'get_position(symbol)',
                documentation: '获取当前持仓'
              },
              {
                label: 'get_portfolio_value',
                kind: monaco.languages.CompletionItemKind.Function,
                insertText: 'get_portfolio_value()',
                documentation: '获取当前投资组合价值'
              }
            ]
          };
        }
      });
    };

    onMounted(() => {
      setupIntellisense();

      monacoEditor = monaco.editor.create(editor.value, {
        value: props.code,
        language: props.language,
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        fontSize: 14,
        lineNumbers: 'on',
        roundedSelection: false,
        scrollbar: {
          vertical: 'auto',
          horizontal: 'auto'
        },
        readOnly: props.readOnly
      });

      // 监听内容变化
      monacoEditor.onDidChangeModelContent(() => {
        const value = monacoEditor.getValue();
        emit('update:code', value);
      });
    });

    watch(() => props.code, (newVal) => {
      if (monacoEditor && newVal !== monacoEditor.getValue()) {
        monacoEditor.setValue(newVal);
      }
    });

    return {
      editor
    };
  }
}
</script>

<style scoped>
.monaco-editor {
  width: 100%;
  height: 100%;
  min-height: 500px;
}
</style>