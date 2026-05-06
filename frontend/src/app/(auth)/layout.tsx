import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-primary/5 overflow-hidden">
      <div className="absolute top-0 -left-40 w-96 h-96 bg-primary/20 rounded-full blur-3xl" />
      <div className="absolute bottom-0 -right-40 w-[500px] h-[500px] bg-accent/10 rounded-full blur-3xl" />
      <div className="relative w-full max-w-md p-8">
        <Link href="/" className="flex items-center gap-2 mb-8 justify-center">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center font-bold text-primary-foreground">
            ₱
          </div>
          <span className="text-xl font-bold tracking-tight">Kuwenta</span>
        </Link>
        {children}
      </div>
    </div>
  );
}
