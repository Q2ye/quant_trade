// 懒加载工具
export function lazy(componentPath) {
  return () => import(`@/${componentPath}.vue`);
}