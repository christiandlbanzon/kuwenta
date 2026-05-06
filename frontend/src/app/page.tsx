import Link from "next/link";
import { ArrowRight, Receipt, Sparkles, Wallet, MessagesSquare, BarChart3 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 relative overflow-hidden">
      {/* Decorative gradient blobs */}
      <div className="absolute top-0 -left-40 w-96 h-96 bg-primary/20 rounded-full blur-3xl" />
      <div className="absolute top-1/3 -right-40 w-[500px] h-[500px] bg-accent/10 rounded-full blur-3xl" />

      <header className="relative container mx-auto pt-8 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-primary to-accent flex items-center justify-center font-bold text-primary-foreground">
            ₱
          </div>
          <span className="text-xl font-bold tracking-tight">Kuwenta</span>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="ghost">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link href="/signup">
              Get started <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </header>

      <section className="relative container mx-auto pt-24 pb-32 text-center max-w-4xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/60 px-4 py-1.5 text-sm text-muted-foreground mb-8">
          <Sparkles className="size-3.5 text-accent" />
          AI-powered. ₱0/month to operate. Built for the Philippines.
        </div>
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight leading-tight">
          Personal finance,
          <br />
          <span className="gradient-text">in your own language.</span>
        </h1>
        <p className="mt-8 text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto">
          Type{" "}
          <code className="rounded-md bg-secondary/60 px-2 py-0.5 font-mono text-base text-foreground">
            180 jollibee lunch yesterday gcash
          </code>{" "}
          and Kuwenta parses, categorizes, and tracks it. Snap a receipt — same thing.
          Ask &quot;magkano nagastos ko sa food last month?&quot; and get an answer.
        </p>
        <div className="mt-10 flex items-center justify-center gap-3">
          <Button asChild size="lg" className="text-base">
            <Link href="/signup">
              Start tracking free <ArrowRight className="size-4" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="text-base">
            <Link href="/login">Sign in</Link>
          </Button>
        </div>
        <p className="mt-6 text-sm text-muted-foreground">
          Free forever for personal use • No credit card • Your data stays yours
        </p>
      </section>

      <section className="relative container mx-auto pb-24">
        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {[
            {
              icon: Wallet,
              title: "Quick-add in plain text",
              body:
                'Type "350 grab to ortigas" — amount, category, account, and date all parsed for you. Taglish welcome.',
            },
            {
              icon: Receipt,
              title: "Snap any receipt",
              body:
                "Drag a Jollibee, SM, or Mercury Drug receipt — Gemini Vision extracts merchant, line items, total, and category.",
            },
            {
              icon: MessagesSquare,
              title: "Ask anything",
              body:
                '"How much did I spend on Grab this month?" "Compare my food spending Oct vs Nov." "Top categories this year."',
            },
            {
              icon: BarChart3,
              title: "Monthly insights",
              body:
                "On the 1st of every month, a summary lands. Anomalies flagged, wins celebrated, one gentle suggestion.",
            },
            {
              icon: Sparkles,
              title: "PH-first categories",
              body:
                "Palengke, jeepney, GCash, Pag-IBIG, padala, tithe — built around how Filipinos actually spend, not borrowed from US apps.",
            },
            {
              icon: Wallet,
              title: "Function-calling Q&A",
              body:
                "Whitelisted query primitives instead of LLM-generated SQL. Auditable, eval'd, and your data stays scoped to you.",
            },
          ].map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl border border-border/60 bg-card/40 p-6 backdrop-blur transition-colors hover:bg-card"
            >
              <div className="size-10 rounded-lg bg-primary/15 flex items-center justify-center text-primary mb-4">
                <Icon className="size-5" />
              </div>
              <h3 className="font-semibold mb-2">{title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="relative container mx-auto pb-8 pt-12 border-t border-border/40 text-sm text-muted-foreground flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>Kuwenta — built in the Philippines, for the Philippines.</div>
        <div className="flex items-center gap-4">
          <Link href="/login" className="hover:text-foreground">
            Sign in
          </Link>
          <Link href="/signup" className="hover:text-foreground">
            Sign up
          </Link>
        </div>
      </footer>
    </div>
  );
}
