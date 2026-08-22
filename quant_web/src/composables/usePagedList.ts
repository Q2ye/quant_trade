// composables/usePagedList.ts
// 客户端分页组合式函数：给「已全量加载、在客户端切片」的列表提供统一的分页状态与切片数据。
// 用法：
//   const { page: currentPage, pageSize, itemCount, pagedData } = usePagedList(filteredRules, 20);
//   <n-pagination v-model:page="currentPage" v-model:page-size="pageSize" :item-count="itemCount" />
//   <n-data-table :data="pagedData" ... />
import { computed, ref, watch, type ComputedRef, type Ref } from "vue";

export interface PagedList<T> {
  /** 当前页码（1 起） */
  page: Ref<number>;
  /** 每页条数 */
  pageSize: Ref<number>;
  /** 总条数（= 源数据长度） */
  itemCount: ComputedRef<number>;
  /** 按 page/pageSize 切片后的当前页数据 */
  pagedData: ComputedRef<T[]>;
}

/**
 * @param source 全量数据源（ref 或 computed）
 * @param initialPageSize 初始每页条数
 */
export function usePagedList<T>(
  source: Ref<T[]> | ComputedRef<T[]>,
  initialPageSize = 20,
): PagedList<T> {
  const page = ref(1);
  const pageSize = ref(initialPageSize);

  const itemCount = computed(() => source.value.length);
  const pageCount = computed(() =>
    Math.max(1, Math.ceil(itemCount.value / pageSize.value)),
  );

  const pagedData = computed(() => {
    const start = (page.value - 1) * pageSize.value;
    return source.value.slice(start, start + pageSize.value);
  });

  // 数据总量或每页条数变化时，将页码钳制到有效范围内（如筛选后数据变少）
  watch([itemCount, pageSize], () => {
    if (page.value > pageCount.value) page.value = pageCount.value;
  });

  return { page, pageSize, itemCount, pagedData };
}
