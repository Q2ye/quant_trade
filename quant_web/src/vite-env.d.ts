// src/vite-plugin-eslint.d.ts
declare module "vite-plugin-eslint" {
  import { Plugin } from "vite";
  interface Options {
    include?: string | string[];
    exclude?: string | string[];
    fix?: boolean;
    cache?: boolean;
    emitError?: boolean;
    emitWarning?: boolean;
    failOnError?: boolean;
    failOnWarning?: boolean;
    overrideConfigFile?: string;
  }
  export function createEsLintPlugin(options?: Options): Plugin;
  export default function eslintPlugin(options?: Options): Plugin;
}

interface ImportMetaEnv {
  // 环境变量的类型定义，根据实际使用的变量添加
  readonly VITE_API_BASE_URL: string;
  readonly VITE_WS_URL: string;
  readonly BASE_URL: string;
  readonly VITE_APP_ENV: string;
  // 其他环境变量...
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}