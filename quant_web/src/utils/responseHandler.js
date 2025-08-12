// 响应处理
export function handleResponse(response) {
  if (response.code === 0) {
    return response.data;
  } else {
    throw new Error(response.message || 'Unknown error');
  }
}