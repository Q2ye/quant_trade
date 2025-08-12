// jest.config.js
module.exports = {
  preset: '@vue/cli-plugin-unit-jest',
  moduleFileExtensions: ['js', 'jsx', 'json', 'vue'],
  transform: {
    '^.+\\.vue$': '@vue/vue3-jest',
    '^.+\\.js$': 'babel-jest',
    '^.+\\.ts$': 'ts-jest'
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
    '^echarts$': '<rootDir>/node_modules/echarts/dist/echarts.min.js',
    '\\.(css|less|scss)$': 'identity-obj-proxy'
  },
  testEnvironment: 'jsdom',
  testMatch: [
    '**/tests/unit/**/*.spec.[jt]s?(x)',
    '**/__tests__/*.[jt]s?(x)'
  ],
  collectCoverage: true,
  collectCoverageFrom: [
    'src/**/*.{js,vue}',
    '!src/main.js',
    '!src/App.vue',
    '!src/router/index.js',
    '!src/store/index.js',
    '!src/utils/request.js',
    '!src/api/**'
  ],
  coverageReporters: ['html', 'text-summary'],
  setupFilesAfterEnv: ['<rootDir>/tests/unit/setup.js'],
  transformIgnorePatterns: [
    '/node_modules/(?!echarts|zrender)'
  ]
}