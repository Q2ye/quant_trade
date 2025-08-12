// vue.config.js
const {defineConfig} = require('@vue/cli-service')
const MonacoEditorPlugin = require('monaco-editor-webpack-plugin')
const {resolve} = require("node:path");

module.exports = defineConfig({
    transpileDependencies: true,
    lintOnSave: false, // 关闭eslint检查
    configureWebpack: {
        plugins: [
            new MonacoEditorPlugin({
                languages: ['python', 'json', 'javascript'],
                features: [
                    'bracketMatching',
                    'folding',
                    'lineNumbers',
                    'suggest'
                ]
            })
        ],
        resolve: {
            alias: {
                '@': resolve(__dirname, 'src')
            },
            fallback: {
                path: require.resolve('path-browserify')
            }
        }
    },
    devServer: {
        port: 8080,
        proxy: {
            '/api': {
                target: 'http://localhost:8000', // 后端API地址
                changeOrigin: true,
                pathRewrite: {
                    '^/api': ''
                }
            }
        },
        client: {
            overlay: {
                warnings: false,
                errors: true
            }
        }
    },
    css: {
        loaderOptions: {
            sass: {
                additionalData: `@import "@/assets/scss/_variables.scss";`
            }
        }
    }
})