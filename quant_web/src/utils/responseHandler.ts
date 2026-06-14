// quant_web/src/utils/responseHandler.ts
/**
 * 统一响应处理器
 *
 * 注意：部分浏览器扩展（如 highlight-manager、翻译插件等）会拦截并篡改
 * JSON 响应中的 data 字段。本函数检测这种注入并在控制台打印明确警告。
 */

/** 被浏览器扩展污染的响应特征：data 是 {code, highlights} 而非业务字段 */
function isExtensionCorrupted(data: any): boolean {
  if (!data || typeof data !== "object") return false;
  // 扩展注入特征：data 包含 code（HTTP 状态码）+ highlights，但没有实际的业务字段
  if (data.code !== undefined && data.highlights !== undefined) {
    // 如果 data 同时有这些常见业务字段 → 可能不是注入
    const bizKeys = ["basic", "quotes", "indices", "items", "total", "stocks"];
    const hasBizField = bizKeys.some((k) => k in data);
    if (!hasBizField) return true;
  }
  return false;
}

export const handleResponse = (response: any) => {
  // axios 拦截器已提取 response.data，这里收到的就是 API 响应体
  if (response && typeof response === "object") {
    // 检测浏览器扩展注入
    if (response.success && isExtensionCorrupted(response.data)) {
      console.warn(
        "⚠️ [响应被篡改] 浏览器扩展（如 highlight-manager）修改了 API 响应。\n" +
          "   原始业务数据已被替换为 {code, highlights}。\n" +
          "   请禁用相关扩展或将 localhost 加入扩展白名单。\n" +
          "   被篡改的 data 字段：",
        response.data,
      );
    }
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
