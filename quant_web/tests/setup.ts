// tests/setup.ts — 全局测试配置
import { config } from "@vue/test-utils";

config.global.components = {
  RouterLink: {
    template: '<a href="#"><slot /></a>',
  },
};

config.global.provide = {};
