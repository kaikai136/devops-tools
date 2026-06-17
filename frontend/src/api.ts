const JSON_HEADERS = { 'Content-Type': 'application/json' };

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
      throw new Error(response.ok ? '后端返回了非 JSON 数据' : text);
    }
  }

  if (!response.ok) {
    const error = typeof payload === 'object' && payload && 'error' in payload ? String(payload.error) : '请求失败，请确认后端服务已启动';
    throw new Error(error);
  }

  if (payload === null) {
    throw new Error('后端返回为空，请稍后重试');
  }

  return payload as T;
}
