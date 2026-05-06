import Link from "next/link";
import { Wallet } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { QuickAdd } from "@/components/app/quick-add";
import { TransactionRow } from "@/components/app/transaction-row";
import { AddAccountDialog } from "@/components/app/add-account-dialog";
import { apiFetch } from "@/lib/auth.server";
import { formatPesoCompact } from "@/lib/format";
import type { Account, Category, Transaction } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function TransactionsPage() {
  const [accounts, categories, transactions] = await Promise.all([
    apiFetch<Account[]>("/accounts"),
    apiFetch<Category[]>("/categories"),
    apiFetch<Transaction[]>("/transactions?limit=200"),
  ]);
  const categoryById = new Map(categories.map((c) => [c.id, c]));

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Transactions</h1>
          <p className="text-muted-foreground mt-1">
            {transactions.length} record{transactions.length === 1 ? "" : "s"}
          </p>
        </div>
        <AddAccountDialog />
      </div>

      <QuickAdd accounts={accounts} categories={categories} />

      {/* Accounts strip */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center justify-between">
            <span>Accounts</span>
            <span className="text-xs font-normal text-muted-foreground">
              {accounts.length} account{accounts.length === 1 ? "" : "s"}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4 text-center">
              No accounts yet. Add a GCash, BDO, or cash account to start tracking.
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {accounts.map((a) => (
                <div
                  key={a.id}
                  className="rounded-lg border border-border/60 bg-secondary/20 p-4"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Wallet className="size-4 text-muted-foreground" />
                    <span className="text-sm font-medium truncate">{a.name}</span>
                    <Badge variant="outline" className="ml-auto text-[10px]">
                      {a.type}
                    </Badge>
                  </div>
                  <div className="text-xl font-bold tabular-nums">
                    {formatPesoCompact(a.current_balance)}
                  </div>
                  {a.institution && (
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {a.institution}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Transactions list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">All transactions</CardTitle>
          <CardDescription>Most recent first</CardDescription>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No transactions yet — try the quick-add above.
            </div>
          ) : (
            <div className="divide-y divide-border/40 -mx-2">
              {transactions.map((t) => (
                <TransactionRow
                  key={t.id}
                  txn={t}
                  category={t.category_id ? categoryById.get(t.category_id) : null}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
