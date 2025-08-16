interface ApiResponse {
  code: number;
  message?: string;
  data?: any;
}

export function handleResponse(response: ApiResponse): any {
  if (response.code === 0) {
    return response.data;
  } else {
    throw new Error(response.message || 'Unknown error');
  }
}