// Cypress配置
const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:8080',
    viewportWidth: 1920,
    viewportHeight: 1080,
    video: false,
    experimentalStudio: true,
    setupNodeEvents(on, config) {
      // 实现节点事件监听器
    },
  },
  component: {
    devServer: {
      framework: 'vue',
      bundler: 'webpack',
    },
  },
})