"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles, Send, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { formatPeso, formatRelative } from "@/lib/format";
import type { Account, Category, QuickAddDraft, TransactionType } from "@/lib/types";

interface QuickAddProps {
  accounts: Account[];
  categories: Category[];
}

const EXAMPLES = [
  "180 jollibee lunch yesterday gcash",
  "350 grab to ortigas",
  "3200 meralco bill",
  "2300 sm hypermarket grocery",
];

export function QuickAdd({ accounts, categories }: QuickAddProps) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [draft, setDraft] = useState<QuickAddDraft | null>(null);
  const [parsing, setParsing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const accountById = new Map(accounts.map((a) => [a.id, a]));
  const categoryById = new Map(categories.map((c) => [c.id, c]));

  async function parse() {
    if (!text.trim()) return;
    setParsing(true);
    setError(null);
    setDraft(null);
    try {
      const d = await api.post<QuickAddDraft>("/transactions/quick-add/parse", { text });
      setDraft(d);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't parse — try again.");
    } finally {
      setParsing(false);
    }
  }

  async function confirm() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      await api.post("/transactions", {
        account_id: draft.account_id,
        category_id: draft.category_id,
        amount: draft.amount,
        type: draft.type,
        description: draft.description,
        merchant: draft.merchant,
        occurred_at: draft.occurred_at,
        source: "manual",
      });
      setDraft(null);
      setText("");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save — try again.");
    } finally {
      setSaving(false);
    }
  }

  if (accounts.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border/60 bg-card/40 p-6 text-center">
        <p className="text-sm text-muted-foreground mb-3">
          Add an account first (GCash, BDO, cash) and you can start quick-adding transactions.
        </p>
        <Button asChild size="sm">
          <a href="/transactions">Add account</a>
        </Button>
      </div>
    );
  }

  const accountName =
    draft && accountById.get(draft.account_id)?.name;
  const categoryName =
    draft && draft.category_id ? categoryById.get(draft.category_id)?.name : "Uncategorized";

  return (
    <div className="rounded-xl border border-border/60 bg-gradient-to-br from-card to-card/60 p-5 shadow-lg">
      <div className="flex items-center gap-2 mb-3 text-sm text-muted-foreground">
        <Sparkles className="size-4 text-accent" />
        <span>Quick add — type naturally, AI handles the rest</span>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          parse();
        }}
        className="flex gap-2"
      >
        <Input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="180 jollibee lunch yesterday gcash"
          className="text-base"
          disabled={parsing || saving}
          autoFocus
        />
        <Button type="submit" disabled={!text.trim() || parsing || saving}>
          {parsing ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          <span className="hidden sm:inline">Parse</span>
        </Button>
      </form>

      {!draft && !error && (
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setText(ex)}
              disabled={parsing}
              className="text-xs px-2.5 py-1 rounded-md bg-secondary/60 text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-3 text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {draft && (
        <div className="mt-4 rounded-lg border border-primary/30 bg-primary/5 p-4 animate-fade-in">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-2 flex-1 min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight">
                  {formatPeso(draft.amount)}
                </span>
                <span className="text-xs uppercase text-muted-foreground tracking-wider">
                  {draft.type}
                </span>
              </div>
              <div className="text-sm text-foreground">{draft.description}</div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                {draft.merchant && <span>{draft.merchant}</span>}
                <span>{accountName}</span>
                <span>{categoryName}</span>
                <span>{formatRelative(draft.occurred_at)}</span>
                {draft.ai_confidence !== null && (
                  <span className="text-accent">
                    {Math.round((draft.ai_confidence ?? 0) * 100)}% confident
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-2 shrink-0">
              <Button variant="outline" size="sm" onClick={() => setDraft(null)} disabled={saving}>
                Cancel
              </Button>
              <Button size="sm" onClick={confirm} disabled={saving}>
                {saving ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <>
                    <Check className="size-4" />
                    Save
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
