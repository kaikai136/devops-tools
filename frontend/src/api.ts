const JSON_HEADERS = { 'Content-Type': 'application/json' };

export class ApiUnauthorizedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiUnauthorizedError';
  }
}

export async function apiGet<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { credentials: 'include', ...options });
  return readResponse<T>(response);
}

export async function apiPost<T>(url: string, payload: unknown, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
    credentials: 'include',
    ...options,
  });
  return readResponse<T>(response);
}

export async function apiPut<T>(url: string, payload: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PUT',
    headers: JSON_HEADERS,
    body: JSON.stringify(payload),
    credentials: 'include',
  });
  return readResponse<T>(response);
}

export async function apiDelete<T>(url: string): Promise<T> {
  const response = await fetch(url, { method: 'DELETE', credentials: 'include' });
  return readResponse<T>(response);
}

async function readResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: unknown = null;

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      if (response.ok) {
        throw new Error('后端返回了非 JSON 数据');
      }
      const contentType = response.headers.get('content-type') ?? '';
      const looksLikeHtml = contentType.includes('text/html') || /^\s*<!doctype html/i.test(text) || /^\s*<html/i.test(text);
      throw new Error(looksLikeHtml ? '后端服务异常，请确认数据库迁移已完成并查看后端日志。' : text.slice(0, 240));
    }
  }

  if (!response.ok) {
    const error = typeof payload === 'object' && payload && 'error' in payload ? String(payload.error) : '请求失败，请确认后端服务已启动';
    if (response.status === 401) {
      throw new ApiUnauthorizedError(error);
    }
    throw new Error(error);
  }

  if (payload === null) {
    throw new Error('后端返回为空，请稍后重试');
  }

  return payload as T;
}
