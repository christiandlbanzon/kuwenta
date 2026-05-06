import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, getApiBase } from "@/lib/auth.server";

export async function POST(req: Request) {
  const body = await req.json();
  const res = await fetch(`${getApiBase()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    return NextResponse.json(data, { status: res.status });
  }
  cookies().set(SESSION_COOKIE, data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7, // 7 days, matches backend JWT TTL
  });
  return NextResponse.json({ ok: true });
}
