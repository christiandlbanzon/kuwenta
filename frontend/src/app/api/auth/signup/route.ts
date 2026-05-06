import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, getApiBase } from "@/lib/auth.server";

export async function POST(req: Request) {
  const body = await req.json();
  const signupRes = await fetch(`${getApiBase()}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const signupData = await signupRes.json();
  if (!signupRes.ok) {
    return NextResponse.json(signupData, { status: signupRes.status });
  }
  // Auto-login the new user so they hit the dashboard immediately
  const loginRes = await fetch(`${getApiBase()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
  });
  const loginData = await loginRes.json();
  if (!loginRes.ok) {
    return NextResponse.json(loginData, { status: loginRes.status });
  }
  cookies().set(SESSION_COOKIE, loginData.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return NextResponse.json({ ok: true, user: signupData });
}
