/* eslint-env node */
import {defineConfig} from 'vite'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import eslintPlugin from 'vite-plugin-eslint'
import {visualizer} from 'rollup-plugin-visualizer'
import path from 'path'

const __dirname = path.resolve();

export default defineConfig({
    plugins: [
        vue(),
        vueJsx(),
        eslintPlugin({
            fix: true,
            include: ['src/**/*.ts', 'src/**/*.vue', 'src/**/*.tsx'],
            cache: false,
            emitError: true,
            emitWarning: true,
            failOnError: false,
            overrideConfigFile: path.resolve(__dirname, '.eslintrc.cjs')
        }),
        visualizer()
    ],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
            'path': 'path-browserify'
        }
    },
    server: {
        port: 8080,
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                rewrite: (p) => p.replace(/^\/api/, '')
            }
        },
        open: false,
    },
    css: {
        preprocessorOptions: {
            scss: {
                additionalData: `@use "@/assets/scss/_variables.scss" as *;`
            }
        }
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    monaco: ['monaco-editor'],
                    echarts: ['echarts'],
                    element: ['element-plus']
                }
            }
        }
    }
})