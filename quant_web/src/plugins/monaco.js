// Monaco编辑器加载插件
import * as monaco from 'monaco-editor';
// 配置Monaco编辑器
monaco.languages.register({id: 'quant-strategy'});
monaco.languages.setMonarchTokensProvider('quant-strategy', {
    tokenizer: {
        root: [
            [/def|return|if|else|for|while|break|continue/, 'keyword'],
            [/(context|data|order_target_percent|history|log)/, 'predefined'],
            [/#.*$/, 'comment'],
            [/".*?"/, 'string'],
            [/\d+\.\d+|\d+/, 'number'],
            [/[a-zA-Z_]\w*/, 'identifier'],
        ]
    }
});
export default {
    install(app) {
        app.config.globalProperties.$monaco = monaco;
    }
};