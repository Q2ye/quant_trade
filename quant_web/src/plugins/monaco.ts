import * as monaco from "monaco-editor";
import { App } from "vue";

// 配置Monaco编辑器
monaco.languages.register({ id: "quant-events" });
monaco.languages.setMonarchTokensProvider("quant-events", {
  tokenizer: {
    root: [
      [/def|return|if|else|for|while|break|continue/, "keyword"],
      [/(context|data|order_target_percent|history|log)/, "predefined"],
      [/#.*$/, "comment"],
      [/".*?"/, "string"],
      [/\d+\.\d+|\d+/, "number"],
      [/[a-zA-Z_]\w*/, "identifier"],
    ],
  },
});

export default {
  install(app: App) {
    app.config.globalProperties.$monaco = monaco;
  },
};
