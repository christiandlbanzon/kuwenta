import { redirect } from "next/navigation";
import { Sidebar, MobileNav } from "@/components/app/sidebar";
import { apiFetch, getSessionToken } from "@/lib/auth.server";
import type { User } from "@/lib/types";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  if (!getSessionToken()) {
    redirect("/login");
  }
  let me: User;
  try {
    me = await apiFetch<User>("/auth/me");
  } catch {
    redirect("/login");
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar userEmail={me.email} />
      <main className="flex-1 min-w-0 pb-20 md:pb-0">
        <div className="container mx-auto px-4 md:px-8 py-6 md:py-10 max-w-7xl">
          {children}
        </div>
      </main>
      <MobileNav />
    </div>
  );
}
