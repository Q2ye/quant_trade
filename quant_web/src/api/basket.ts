// quant_web/src/api/basket.ts
import request from "@/utils/request";
import { handleResponse } from "@/utils/responseHandler";
import {
  Basket,
  BasketPerformance,
  RealtimeBasketData,
  CreateBasketRequest,
  UpdateBasketRequest,
  BasketQueryParams,
} from "@/types";
import {
  BasketListResponse,
  BasketPerformanceResponse,
  BasketResponse,
} from "@/types";

// 创建API对象
const basketApi = {
  /**
   * 获取篮子列表
   * @param params 分页和查询参数
   * @returns 篮子列表和总数
   */
  async getBaskets(
    params?: BasketQueryParams,
  ): Promise<{ baskets: Basket[]; total: number }> {
    // 修复：去掉重复的 /api，使用正确的路径
    return request
      .get("/quantTrade/basket", { params })
      .then(handleResponse)
      .then((data: BasketListResponse) => ({
        baskets: data.data.items,
        total: data.data.total,
      }));
  },

  /**
   * 创建新篮子
   * @param basketData 篮子数据
   * @returns 创建的篮子信息
   */
  async createBasket(basketData: CreateBasketRequest): Promise<Basket> {
    return request
      .post("/quantTrade/basket", basketData)
      .then(handleResponse)
      .then((data: BasketResponse) => data.data);
  },

  /**
   * 获取篮子详情
   * @param id 篮子ID
   * @returns 篮子详细信息
   */
  async getBasket(id: string): Promise<Basket> {
    return request
      .get(`/quantTrade/basket/${id}`)
      .then(handleResponse)
      .then((data: BasketResponse) => data.data);
  },

  /**
   * 更新篮子信息
   * @param id 篮子ID
   * @param updateData 更新数据
   * @returns 更新后的篮子信息
   */
  async updateBasket(
    id: string,
    updateData: UpdateBasketRequest,
  ): Promise<Basket> {
    return request
      .put(`/quantTrade/basket/${id}`, updateData)
      .then(handleResponse)
      .then((data: BasketResponse) => data.data);
  },

  /**
   * 删除篮子
   * @param id 篮子ID
   * @returns 无返回值
   */
  async deleteBasket(id: string): Promise<void> {
    return request.delete(`/quantTrade/basket/${id}`).then(handleResponse);
  },

  /**
   * 获取篮子绩效分析
   * @param id 篮子ID
   * @param params 时间范围参数
   * @returns 篮子绩效数据
   */
  async getBasketPerformance(
    id: string,
    params: {
      start_date: string;
      end_date: string;
      benchmark?: string;
    },
  ): Promise<BasketPerformance> {
    return request
      .get(`/quantTrade/basket/${id}/performance`, { params })
      .then(handleResponse)
      .then((data: BasketPerformanceResponse) => data.data);
  },

  /**
   * 获取篮子实时数据
   * @param id 篮子ID
   * @returns 篮子实时行情数据
   */
  async getBasketRealtimeData(id: string): Promise<RealtimeBasketData> {
    return request
      .get(`/quantTrade/basket/${id}/realtime`)
      .then(handleResponse)
      .then((data: { data: RealtimeBasketData }) => data.data);
  },

  /**
   * 添加股票到篮子
   * @param basketId 篮子ID
   * @param item 股票数据
   * @returns 更新后的篮子信息
   */
  async addStockToBasket(
    basketId: string,
    item: { symbol: string; weight: number },
  ): Promise<Basket> {
    return request
      .post(`/quantTrade/basket/${basketId}/items`, item)
      .then(handleResponse)
      .then((data: BasketResponse) => data.data);
  },

  /**
   * 调整股票权重
   * @param basketId 篮子ID
   * @param symbol 股票代码
   * @param weight 新权重
   * @returns 更新后的篮子信息
   */
  async adjustStockWeight(
    basketId: string,
    symbol: string,
    weight: number,
  ): Promise<Basket> {
    return request
      .put(`/quantTrade/basket/${basketId}/items/${symbol}`, { weight })
      .then(handleResponse)
      .then((data: BasketResponse) => data.data);
  },

  /**
   * 从篮子中移除股票
   * @param basketId 篮子ID
   * @param symbol 股票代码
   * @returns 无返回值
   */
  async removeStockFromBasket(basketId: string, symbol: string): Promise<void> {
    return request
      .delete(`/quantTrade/basket/${basketId}/items/${symbol}`)
      .then(handleResponse);
  },

  /**
   * 批量删除篮子
   * @param ids 篮子ID数组
   * @returns 删除结果
   */
  async deleteBaskets(ids: string[]): Promise<{ deleted: number }> {
    return request
      .delete("/quantTrade/basket/batch", {
        data: { ids },
      })
      .then(handleResponse);
  },

  /**
   * 复制篮子
   * @param id 原篮子ID
   * @param newName 新篮子名称
   * @returns 新篮子信息
   */
  async duplicateBasket(id: string, newName: string): Promise<Basket> {
    return request
      .post(`/quantTrade/basket/${id}/duplicate`, {
        new_name: newName,
      })
      .then(handleResponse)
      .then((data: BasketResponse) => data.data);
  },

  /**
   * 导出篮子数据
   * @param id 篮子ID
   * @param format 导出格式（csv/json）
   * @returns 导出文件URL
   */
  async exportBasket(
    id: string,
    format: "csv" | "json" = "csv",
  ): Promise<{ url: string }> {
    return request
      .get(`/quantTrade/basket/${id}/export`, {
        params: { format },
      })
      .then(handleResponse);
  },

  /**
   * 获取篮子列表（兼容旧版本）
   * @param params 查询参数
   * @returns 篮子列表响应
   */
  async fetchBasketList(
    params?: BasketQueryParams,
  ): Promise<{ data: { items: Basket[]; total: number } }> {
    const result = await this.getBaskets(params);
    return {
      data: {
        items: result.baskets,
        total: result.total,
      },
    };
  },
};

// 具名导出所有方法
export const {
  getBaskets,
  createBasket,
  getBasket,
  updateBasket,
  deleteBasket,
  getBasketPerformance,
  getBasketRealtimeData,
  addStockToBasket,
  adjustStockWeight,
  removeStockFromBasket,
  deleteBaskets,
  duplicateBasket,
  exportBasket,
  fetchBasketList,
} = basketApi;

// 默认导出
export default basketApi;
