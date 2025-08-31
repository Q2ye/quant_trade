// src/shims-vue.d.ts
declare module "*.vue" {
  import { DefineComponent } from "vue";
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module "vuex" {
  import { Store } from "vuex";

  // 导出所有类型
  export * from "vuex/types/index.d.ts";

  // 默认导出
  export default Store;

  // 常用导出
  export {
    createStore,
    useStore,
    mapState,
    mapGetters,
    mapActions,
    mapMutations,
    createNamespacedHelpers,
  } from "vuex";
}
