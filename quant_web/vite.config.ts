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
        // 只把「不依赖 Vue」的叶子库单独分块。
        // 任何 import vue 的库（naive-ui / @iconify/vue / vue-router / pinia …）都必须
        // 与入口同块：一旦被拆成独立 chunk，入口与它会形成循环 chunk 依赖，
        // 生产构建下表现为 "Cannot access 'x' before initialization"（TDZ）。
        manualChunks(id) {
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
