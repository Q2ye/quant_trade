export function lazy(componentPath: string): () => Promise<any> {
  return () => import(/* webpackChunkName: "[request]" */ `@/${componentPath}.vue`);
}