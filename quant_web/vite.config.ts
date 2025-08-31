/* eslint-env node */
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueJsx from "@vitejs/plugin-vue-jsx";
import { visualizer } from "rollup-plugin-visualizer";
import { resolve } from "path";

export default defineConfig({
  plugins: [
    vue(),
    vueJsx(),
    visualizer(),
  ],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
      path: "path-browserify",
    },
  },
  server: {
    port: 8081,
    proxy: {
      "/api": {
        target: "http://localhost:8080",
        changeOrigin: true,
        rewrite: (path) => path,
        // rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
    open: false,
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `
         @use "sass:color";
         @use "@/assets/scss/_variables.scss" as *;
         @use "@/assets/scss/_mixins" as mix;`,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          monaco: ["monaco-editor"],
          echarts: ["echarts"],
          element: ["element-plus"],
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