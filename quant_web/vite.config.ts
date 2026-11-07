/* eslint-env node */
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueJsx from "@vitejs/plugin-vue-jsx";
import { visualizer } from "rollup-plugin-visualizer";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue(), vueJsx(), visualizer()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
      path: "path-browserify",
    },
  },
  server: {
    port: 8081,
    proxy: {
      "/quantTrade": {
        target: "http://localhost:8080",
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
    open: false,
  },
  css: {
    preprocessorOptions: {
      scss: {
        api: "modern-compiler",
        additionalData: `
         @use "sass:color";
         @use "@/styles/_variables.scss" as *;
         @use "@/styles/_mixins" as mix;`,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          // vendor — Vue 生态必须同块：vue 包与 @vue/* 运行时被拆到不同 chunk 时，
          // 会出现跨 chunk 的 TDZ（Cannot access 'x' before initialization）
          if (
            id.includes("node_modules/vue") ||
            id.includes("node_modules/@vue/") ||
            id.includes("node_modules/vuex") ||
            id.includes("node_modules/vue-router") ||
            id.includes("node_modules/pinia") ||
            id.includes("node_modules/vue-demi")
          ) {
            return "vendor-vue";
          }
          // UI framework
          if (id.includes("node_modules/naive-ui")) {
            return "vendor-naive";
          }
          // icons
          if (id.includes("node_modules/@iconify")) {
            return "vendor-icons";
          }
          // charts
          if (
            id.includes("node_modules/echarts") ||
            id.includes("node_modules/zrender")
          ) {
            return "vendor-echarts";
          }
          // monaco editor
          if (id.includes("node_modules/monaco-editor")) {
            return "vendor-monaco";
          }
          // @antv
          if (id.includes("node_modules/@antv")) {
            return "vendor-antv";
          }
          // three.js — already lazy-loaded per page, but keep separate for shared refs
          if (id.includes("node_modules/three")) {
            return "vendor-three";
          }
        },
      },
    },
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: {
        ".ts": "ts",
      },
    },
  },
});
