"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Sparkles, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";

export function InsightActions() {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setBusy("monthly");
    setError(null);
    try {
      await api.post("/insights/monthly", {});
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't generate.");
    } finally {
      setBusy(null);
    }
  }

  async function scan() {
    setBusy("scan");
    setError(null);
    try {
      await api.post("/insights/anomalies/scan");
      router.refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't scan.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <Button onClick={generate} disabled={busy !== null} size="sm">
          {busy === "monthly" ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Sparkles className="size-4" />
          )}
          Generate last-month summary
        </Button>
        <Button onClick={scan} disabled={busy !== null} variant="outline" size="sm">
          {busy === "scan" ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Search className="size-4" />
          )}
          Scan for anomalies
        </Button>
      </div>
      {error && (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md px-3 py-2">
          {error}
        </div>
      )}
    </div>
  );
}
