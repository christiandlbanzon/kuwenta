import Link from "next/link";
import { ArrowUpRight, Plus, TrendingUp, TrendingDown, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { QuickAdd } from "@/components/app/quick-add";
import { CategoryDonut, CategoryLegend } from "@/components/app/category-donut";
import { TransactionRow } from "@/components/app/transaction-row";
import { apiFetch } from "@/lib/auth.server";
import { formatPesoCompact, formatPeso } from "@/lib/format";
import type {
  Account,
  BudgetProgress,
  Category,
  Insight,
  Transaction,
} from "@/lib/types";

export const dynamic = "force-dynamic";

async function getDashboardData() {
  const [accounts, categories, transactions, budgetProgress, insights] = await Promise.all([
    apiFetch<Account[]>("/accounts"),
    apiFetch<Category[]>("/categories"),
    apiFetch<Transaction[]>("/transactions?limit=10"),
    apiFetch<BudgetProgress[]>("/budgets/progress").catch(() => [] as BudgetProgress[]),
    apiFetch<Insight[]>("/insights").catch(() => [] as Insight[]),
  ]);
  return { accounts, categories, transactions, budgetProgress, insights };
}

export default async function DashboardPage() {
  const { accounts, categories, transactions, budgetProgress, insights } =
    await getDashboardData();

  const categoryById = new Map(categories.map((c) => [c.id, c]));

  // Compute this-month totals from the recent transactions list
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const monthTxns = transactions.filter(
    (t) => new Date(t.occurred_at) >= monthStart,
  );
  const monthExpense = monthTxns
    .filter((t) => t.type === "expense")
    .reduce((s, t) => s + Number(t.amount), 0);
  const monthIncome = monthTxns
    .filter((t) => t.type === "income")
    .reduce((s, t) => s + Number(t.amount), 0);
  const netWorth = accounts.reduce((s, a) => s + Number(a.current_balance), 0);

  // Group expenses by category for donut
  const byCategory = new Map<string, number>();
  for (const t of transactions.filter((x) => x.type === "expense")) {
    const cat = t.category_id ? categoryById.get(t.category_id) : null;
    const name = cat?.name ?? "Uncategorized";
    byCategory.set(name, (byCategory.get(name) ?? 0) + Number(t.amount));
  }
  const donutData = [...byCategory.entries()]
    .map(([category, total]) => ({ category, total }))
    .sort((a, b) => b.total - a.total);

  const recentInsight = insights[0];
  const monthLabel = now.toLocaleDateString("en-PH", {
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">{monthLabel}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/transactions">
            View all transactions <ArrowUpRight className="size-4" />
          </Link>
        </Button>
      </div>

      {/* Quick add */}
      <QuickAdd accounts={accounts} categories={categories} />

      {/* Top stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Net worth"
          value={formatPesoCompact(netWorth)}
          hint={`${accounts.length} account${accounts.length === 1 ? "" : "s"}`}
        />
        <StatCard
          label="Spent this month"
          value={formatPesoCompact(monthExpense)}
          icon={<TrendingDown className="size-4 text-destructive" />}
        />
        <StatCard
          label="Income this month"
          value={formatPesoCompact(monthIncome)}
          icon={<TrendingUp className="size-4 text-success" />}
        />
        <StatCard
          label="Savings rate"
          value={
            monthIncome > 0
              ? `${(((monthIncome - monthExpense) / monthIncome) * 100).toFixed(0)}%`
              : "—"
          }
          hint={monthIncome > 0 ? "this month" : "add income"}
        />
      </div>

      {/* Two-column: chart + recent + insight */}
      <div className="grid lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Spending by category</CardTitle>
              <CardDescription>Last {transactions.length} transactions</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="grid sm:grid-cols-2 gap-6 items-center">
            <CategoryDonut data={donutData} />
            <CategoryLegend data={donutData} />
          </CardContent>
        </Card>

        {/* Insight + budgets */}
        <div className="space-y-4">
          {recentInsight && (
            <Card className="border-accent/30 bg-gradient-to-br from-accent/5 to-card">
              <CardHeader className="pb-3">
                <Badge variant="accent" className="w-fit mb-1.5">
                  <Sparkles className="size-3 mr-1" /> Insight
                </Badge>
                <CardTitle className="text-base">{recentInsight.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <p className="line-clamp-4">{recentInsight.content}</p>
                <Button asChild variant="link" className="px-0 h-auto mt-2">
                  <Link href="/insights">Read more</Link>
                </Button>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Budgets</CardTitle>
              <CardDescription>
                {budgetProgress.length === 0 ? "Set monthly limits per category" : "This period"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {budgetProgress.length === 0 ? (
                <Button asChild variant="outline" size="sm" className="w-full">
                  <Link href="/budgets">
                    <Plus className="size-4" />
                    Create your first budget
                  </Link>
                </Button>
              ) : (
                <ul className="space-y-3">
                  {budgetProgress.slice(0, 3).map((b) => (
                    <li key={b.budget_id}>
                      <div className="flex items-baseline justify-between text-sm mb-1.5">
                        <span className="truncate">{b.category_name}</span>
                        <span
                          className={
                            b.on_track
                              ? "text-muted-foreground"
                              : "text-warning font-medium"
                          }
                        >
                          {Math.round(b.percent_used)}%
                        </span>
                      </div>
                      <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                        <div
                          className={
                            b.on_track
                              ? "h-full bg-primary transition-all"
                              : "h-full bg-warning transition-all"
                          }
                          style={{ width: `${Math.min(100, b.percent_used)}%` }}
                        />
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground mt-1 tabular-nums">
                        <span>{formatPeso(b.spent)} spent</span>
                        <span>{formatPeso(b.budgeted)} budget</span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Recent transactions */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-base">Recent activity</CardTitle>
            <CardDescription>Your last few transactions</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No transactions yet — try the quick-add above.
            </div>
          ) : (
            <div className="divide-y divide-border/40 -mx-2">
              {transactions.slice(0, 8).map((t) => (
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

function StatCard({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
          <span>{label}</span>
          {icon}
        </div>
        <div className="text-2xl font-bold tracking-tight tabular-nums">
          {value}
        </div>
        {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
      </CardContent>
    </Card>
  );
}
