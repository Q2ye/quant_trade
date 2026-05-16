// quant_web/src/utils/responseHandler.ts
/**
 * 统一响应处理器
 */
export const handleResponse = (response: any) => {
  // 如果响应已经是处理过的数据，直接返回
  if (response && typeof response === "object") {
    return response;
  }

  // 如果是Axios响应对象，提取data
  if (response && response.data) {
    return response.data;
  }

  // 如果是字符串，尝试解析为JSON
  if (typeof response === "string") {
    try {
      return JSON.parse(response);
    } catch {
      return response;
    }
  }

  // 其他情况返回原响应
  return response;
};
