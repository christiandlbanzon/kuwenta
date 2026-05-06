/**
 * Client-side API helpers.
 * The browser never talks to the FastAPI backend directly. All requests go through
 * Next.js route handlers under /api/proxy/* which read the httpOnly JWT cookie and
 * forward to the backend with Authorization: Bearer ... headers.
 */

export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `/api/proxy${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    const detail =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(res.status, body, detail);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "POST", body: json !== undefined ? JSON.stringify(json) : undefined }),
  patch: <T>(path: string, json?: unknown) =>
    request<T>(path, { method: "PATCH", body: json !== undefined ? JSON.stringify(json) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  formData: <T>(path: string, form: FormData) =>
    fetch(`/api/proxy${path}`, { method: "POST", body: form, cache: "no-store" }).then(async (res) => {
      const text = await res.text();
      const body = text ? JSON.parse(text) : null;
      if (!res.ok) {
        throw new ApiError(res.status, body, body?.detail ?? res.statusText);
      }
      return body as T;
    }),
};
