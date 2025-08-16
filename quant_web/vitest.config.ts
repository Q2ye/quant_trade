import {defineConfig} from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import path from 'path' // 添加 path 模块导入

// 获取当前目录路径
const __dirname = path.resolve();

export default defineConfig({
    plugins: [
        vue(),
        vueJsx(),
    ],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src'),
            'path': 'path-browserify'
        }
    },
    test: {
        // 测试环境配置
        environment: 'jsdom',
        globals: true, // 启用全局API (describe, it, expect)

        // 测试文件匹配规则
        include: [
            'src/**/*.spec.{ts,tsx}',
            'tests/unit/**/*.spec.{ts,tsx}'
        ],
        exclude: [
            'node_modules',
            'dist',
            '**/node_modules/**'
        ],

        // 覆盖率配置
        coverage: {
            provider: 'v8', // 使用v8引擎计算覆盖率
            reporter: ['text', 'json', 'html'], // 多种格式报告
            reportsDirectory: './tests/coverage', // 报告输出目录
            all: true, // 包含所有文件而不仅是测试覆盖的文件
            include: ['src/**/*.{ts,vue}'], // 包含的文件
            exclude: [ // 排除的文件
                '**/*.d.ts',
                'src/main.ts',
                'src/router/**',
                'src/i18n/**',
                '**/__mocks__/**'
            ],
            thresholds: { // 覆盖率阈值
                lines: 80,
                functions: 75,
                branches: 70,
                statements: 80
            }
        },

        // 模拟与存根配置
        setupFiles: [
            './tests/setup.ts' // 全局测试设置文件
        ],

        // 别名解析（确保测试中也能正确解析路径别名）
        alias: [
            {find: /^~/, replacement: ''} // 解决scss中~导入问题
        ],

        // 测试类型配置
        typecheck: {
            checker: 'tsc', // 使用TypeScript检查器
            include: ['src/**/*.{ts,tsx}']
        },

        // 测试输出配置
        outputFile: './tests/results.xml', // JUnit格式测试结果
        reporters: ['default', 'junit'], // 多种报告格式

        // 性能优化
        // threads: true, // 启用多线程
        isolate: true, // 隔离测试环境
        clearMocks: true, // 每次测试后清除mock
        restoreMocks: true, // 恢复模拟状态
        mockReset: true, // 重置模拟

        // 浏览器模拟配置
        browser: {
            enabled: true, // 启用浏览器环境
            name: 'chrome', // 指定浏览器
            headless: true // 无头模式
        }
    }
})