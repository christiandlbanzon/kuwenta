/**
 * Backend proxy. Forwards every method to FastAPI with the user's JWT attached
 * from the httpOnly cookie. This is how every client-side fetch gets to the API.
 */
import { NextRequest, NextResponse } from "next/server";
import { authHeaders, getApiBase } from "@/lib/auth.server";

async function proxy(req: NextRequest, params: { path: string[] }) {
  const path = "/" + params.path.join("/");
  const url = new URL(req.url);
  const search = url.search;
  const target = `${getApiBase()}${path}${search}`;

  const init: RequestInit = {
    method: req.method,
    headers: {
      ...authHeaders(),
    },
    cache: "no-store",
  };

  const contentType = req.headers.get("content-type") ?? "";
  if (req.method !== "GET" && req.method !== "HEAD") {
    if (contentType.startsWith("multipart/form-data")) {
      // Pass through form data (file uploads) — DO NOT set content-type, let fetch
      // generate the multipart boundary.
      init.body = await req.formData();
    } else if (contentType) {
      const text = await req.text();
      init.body = text;
      (init.headers as Record<string, string>)["Content-Type"] = contentType;
    }
  }

  const res = await fetch(target, init);
  const buf = await res.arrayBuffer();
  return new NextResponse(buf, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") ?? "application/json",
    },
  });
}

export const GET = (req: NextRequest, ctx: { params: { path: string[] } }) =>
  proxy(req, ctx.params);
export const POST = (req: NextRequest, ctx: { params: { path: string[] } }) =>
  proxy(req, ctx.params);
export const PATCH = (req: NextRequest, ctx: { params: { path: string[] } }) =>
  proxy(req, ctx.params);
export const PUT = (req: NextRequest, ctx: { params: { path: string[] } }) =>
  proxy(req, ctx.params);
export const DELETE = (req: NextRequest, ctx: { params: { path: string[] } }) =>
  proxy(req, ctx.params);
