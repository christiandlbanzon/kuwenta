/**
 * Server-side auth helpers — read the httpOnly JWT cookie set by /api/auth/login.
 * Never run on the client.
 */
import { cookies } from "next/headers";

export const SESSION_COOKIE = "kuwenta_session";

export function getApiBase(): string {
  return process.env.KUWENTA_API_URL ?? "http://localhost:8000";
}

export function getSessionToken(): string | null {
  return cookies().get(SESSION_COOKIE)?.value ?? null;
}

export function authHeaders(): HeadersInit {
  const token = getSessionToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Server-side fetch to the FastAPI backend with the user's JWT attached.
 * Use this from server components and route handlers.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}
