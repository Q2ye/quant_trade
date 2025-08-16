// tests/setup.ts
import { config } from '@vue/test-utils'
import { afterEach, expect} from 'vitest'
import {cleanup} from '@testing-library/vue'
import matchers from '@testing-library/jest-dom/matchers'


// 扩展Vitest的expect方法
expect.extend(matchers)

// 全局组件模拟
config.global.components = {
  'RouterLink': {
    template: '<a href="#"><slot /></a>'
  },
  'FontAwesomeIcon': {
    template: '<i />'
  }
}

// 全局插件模拟
config.global.plugins = [
  // 添加全局使用的插件
]

// 全局指令模拟
config.global.directives = {
  // 添加全局指令
}

// 全局混入
config.global.mixins = [
  // 添加全局混入
]

// 全局属性
config.global.provide = {
  // 添加全局provide
}

// 每次测试后清理DOM
afterEach(() => {
  cleanup()
})

// 全局模拟
vi.mock('axios', () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
      create: vi.fn(() => ({
        get: vi.fn(),
        post: vi.fn(),
        put: vi.fn(),
        delete: vi.fn()
      }))
    }
  }
})

// 环境变量设置
import.meta.env.VITE_API_BASE_URL = '/api'