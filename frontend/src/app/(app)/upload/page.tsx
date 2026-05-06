"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Loader2, ImageIcon, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import { formatPeso, formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Account, Category, ReceiptUploadResponse } from "@/lib/types";

export default function UploadPage() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [draft, setDraft] = useState<ReceiptUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([api.get<Account[]>("/accounts"), api.get<Category[]>("/categories")])
      .then(([a, c]) => {
        setAccounts(a);
        setCategories(c);
      })
      .catch(() => {});
  }, []);

  const accountById = new Map(accounts.map((a) => [a.id, a]));
  const categoryById = new Map(categories.map((c) => [c.id, c]));

  async function upload(file: File) {
    setError(null);
    setSaved(false);
    setDraft(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api.formData<ReceiptUploadResponse>("/receipts/upload", form);
      setDraft(result);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function confirm() {
    if (!draft) return;
    const ext = draft.extracted;
    if (!ext.total) {
      setError("Couldn't read a total off this receipt — adjust manually below.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api.post("/transactions", {
        account_id: draft.suggested_account_id ?? accounts[0]?.id,
        category_id: draft.suggested_category_id,
        amount: ext.total,
        type: "expense",
        description: ext.merchant ?? "receipt",
        merchant: ext.merchant,
        occurred_at: ext.occurred_at ?? new Date().toISOString(),
        source: "receipt_ocr",
      });
      setSaved(true);
      setDraft(null);
      setTimeout(() => router.push("/transactions"), 800);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Upload receipt</h1>
        <p className="text-muted-foreground mt-1">
          Snap a photo or drag a file. Gemini Vision extracts the merchant, total, and category.
        </p>
      </div>

      <Card
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files?.[0];
          if (file) upload(file);
        }}
        className={cn(
          "border-2 border-dashed transition-colors",
          dragOver ? "border-primary bg-primary/5" : "border-border/60",
        )}
      >
        <CardContent className="py-12 text-center">
          <div className="size-14 rounded-full bg-primary/15 flex items-center justify-center mx-auto mb-4 text-primary">
            <ImageIcon className="size-7" />
          </div>
          <h3 className="text-lg font-semibold mb-1">Drop a receipt photo</h3>
          <p className="text-sm text-muted-foreground mb-4">
            JPG, PNG, WebP, or HEIC — up to 8 MB
          </p>
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/heic"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
            }}
          />
          <Button onClick={() => fileInput.current?.click()} disabled={uploading}>
            {uploading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            Choose a file
          </Button>
        </CardContent>
      </Card>

      {error && (
        <div className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {saved && (
        <Card className="border-success/40 bg-success/5">
          <CardContent className="py-6 flex items-center gap-3">
            <Check className="size-6 text-success" />
            <div>
              <div className="font-medium">Saved to transactions</div>
              <div className="text-sm text-muted-foreground">Redirecting...</div>
            </div>
          </CardContent>
        </Card>
      )}

      {draft && (
        <Card className="border-primary/30 bg-primary/5 animate-fade-in">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="text-lg">
                  {draft.extracted.merchant ?? "Receipt"}
                </CardTitle>
                <CardDescription>
                  {draft.extracted.occurred_at
                    ? formatRelative(draft.extracted.occurred_at)
                    : "no date detected"}
                  {" • "}
                  {draft.extracted.payment_method ?? "payment unknown"}
                </CardDescription>
              </div>
              {draft.extracted.total !== null && (
                <div className="text-right shrink-0">
                  <div className="text-3xl font-bold tabular-nums">
                    {formatPeso(draft.extracted.total)}
                  </div>
                  <div className="text-xs text-muted-foreground">total</div>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {draft.extracted.line_items.length > 0 && (
              <div>
                <div className="text-sm font-medium mb-2">Line items</div>
                <ul className="space-y-1 text-sm divide-y divide-border/40">
                  {draft.extracted.line_items.map((li, i) => (
                    <li key={i} className="flex justify-between py-1.5">
                      <span className="text-muted-foreground">
                        {li.quantity ? `${li.quantity}× ` : ""}
                        {li.name}
                      </span>
                      <span className="tabular-nums">{formatPeso(li.amount)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-sm">
              {draft.extracted.subtotal !== null && (
                <div className="rounded-md bg-secondary/40 p-3">
                  <div className="text-xs text-muted-foreground">Subtotal</div>
                  <div className="font-semibold tabular-nums">
                    {formatPeso(draft.extracted.subtotal)}
                  </div>
                </div>
              )}
              {draft.extracted.tax !== null && (
                <div className="rounded-md bg-secondary/40 p-3">
                  <div className="text-xs text-muted-foreground">VAT/Tax</div>
                  <div className="font-semibold tabular-nums">
                    {formatPeso(draft.extracted.tax)}
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              {draft.suggested_category_id &&
                categoryById.get(draft.suggested_category_id) && (
                  <Badge variant="default">
                    {categoryById.get(draft.suggested_category_id)?.name}
                  </Badge>
                )}
              {draft.suggested_account_id &&
                accountById.get(draft.suggested_account_id) && (
                  <Badge variant="outline">
                    {accountById.get(draft.suggested_account_id)?.name}
                  </Badge>
                )}
            </div>

            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={() => setDraft(null)} disabled={saving}>
                <X className="size-4" /> Discard
              </Button>
              <Button onClick={confirm} disabled={saving} className="flex-1">
                {saving ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Check className="size-4" />
                )}
                Save as transaction
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
