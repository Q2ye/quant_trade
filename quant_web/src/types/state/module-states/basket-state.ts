// 篮子状态管理
// 负责管理股票篮子的创建、编辑、删除和查看等操作的状态

import { Basket, BasketItem } from "@/types/entities/basket";

export interface BasketState {
  // 当前选中的篮子ID
  currentBasketId: string | null;

  // 篮子列表数据
  basketList: Basket[];

  // 当前篮子详情（包含成分股信息）
  currentBasket: Basket | null;

  // 篮子成分股数据
  basketItems: BasketItem[];

  // 加载状态
  loading: {
    list: boolean; // 篮子列表加载状态
    detail: boolean; // 篮子详情加载状态
    items: boolean; // 成分股加载状态
    create: boolean; // 创建篮子加载状态
    update: boolean; // 更新篮子加载状态
    delete: boolean; // 删除篮子加载状态
  };

  // 错误信息
  error: {
    list: string | null; // 列表加载错误
    detail: string | null; // 详情加载错误
    create: string | null; // 创建错误
    update: string | null; // 更新错误
    delete: string | null; // 删除错误
  };

  // 分页信息
  pagination: {
    page: number; // 当前页码
    pageSize: number; // 每页大小
    total: number; // 总记录数
  };

  // 搜索和筛选条件
  filters: {
    keyword: string; // 搜索关键词
    sortField: string; // 排序字段
    sortOrder: "asc" | "desc"; // 排序方向
  };
}
