interface ApiResponse {
  code: number;
  message?: string;
  data?: any;
}

// 假设AxiosResponse类型结构
interface AxiosResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
  headers: any;
  config: any;
  request?: any;
}

export function handleResponse(response: AxiosResponse<ApiResponse>): any {
  // 将AxiosResponse转换为ApiResponse
  const apiResponse = response.data as ApiResponse;

  if (apiResponse.code === 0) {
    return apiResponse.data;
  } else {
    throw new Error(apiResponse.message || 'Unknown error');
  }
}