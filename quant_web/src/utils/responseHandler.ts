import { AxiosResponse } from 'axios';

interface ApiResponse {
  code: number;
  message?: string;
  data?: any;
}

export function handleResponse(response: AxiosResponse<ApiResponse>): any {
  const apiResponse = response.data;

  if (apiResponse.code === 0) {
    return apiResponse;
  } else {
    throw new Error(apiResponse.message || 'Unknown error');
  }
}
