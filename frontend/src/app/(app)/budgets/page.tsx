import { Target, TrendingDown, TrendingUp, Sparkles } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AddBudgetDialog } from "@/components/app/add-budget-dialog";
import { apiFetch } from "@/lib/auth.server";
import { formatPeso, formatPesoCompact, formatDateShort } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { BudgetProgress, Category } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function BudgetsPage() {
  const [progress, categories] = await Promise.all([
    apiFetch<BudgetProgress[]>("/budgets/progress").catch(() => [] as BudgetProgress[]),
    apiFetch<Category[]>("/categories"),
  ]);

  const totalBudgeted = progress.reduce((s, b) => s + Number(b.budgeted), 0);
  const totalSpent = progress.reduce((s, b) => s + Number(b.spent), 0);
  const onTrackCount = progress.filter((b) => b.on_track).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Budgets</h1>
          <p className="text-muted-foreground mt-1">
            Set monthly or weekly limits per category
          </p>
        </div>
        <AddBudgetDialog categories={categories} />
      </div>

      {progress.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <div className="size-14 rounded-full bg-primary/15 flex items-center justify-center mx-auto mb-4 text-primary">
              <Target className="size-7" />
            </div>
            <h3 className="text-lg font-semibold mb-1">No budgets yet</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto mb-6">
              Set spending limits per category to see live progress and projected
              end-of-period totals.
            </p>
            <AddBudgetDialog categories={categories} />
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-5">
                <div className="text-xs text-muted-foreground mb-2">Total budgeted</div>
                <div className="text-2xl font-bold tabular-nums">
                  {formatPesoCompact(totalBudgeted)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                  <TrendingDown className="size-3" /> Spent
                </div>
                <div className="text-2xl font-bold tabular-nums">
                  {formatPesoCompact(totalSpent)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {totalBudgeted ? Math.round((totalSpent / totalBudgeted) * 100) : 0}% of budget
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-5">
                <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                  <Sparkles className="size-3" /> On track
                </div>
                <div className="text-2xl font-bold tabular-nums">
                  {onTrackCount}/{progress.length}
                </div>
                <div className="text-xs text-muted-foreground mt-1">budgets</div>
              </CardContent>
            </Card>
          </div>

          {/* Budget list */}
          <div className="grid md:grid-cols-2 gap-4">
            {progress.map((b) => (
              <BudgetCard key={b.budget_id} progress={b} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function BudgetCard({ progress }: { progress: BudgetProgress }) {
  const overspent = progress.percent_used >= 100;
  const warning = progress.percent_used >= 80 && !overspent;
  const color = overspent
    ? "bg-destructive"
    : warning
      ? "bg-warning"
      : progress.on_track
        ? "bg-primary"
        : "bg-warning";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{progress.category_name}</CardTitle>
            <CardDescription className="capitalize">
              {progress.period} • {formatDateShort(progress.period_start)} →{" "}
              {formatDateShort(progress.period_end)}
            </CardDescription>
          </div>
          <Badge variant={overspent ? "destructive" : warning ? "warning" : "success"}>
            {Math.round(progress.percent_used)}%
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-2xl font-bold tabular-nums">
              {formatPeso(progress.spent)}
            </span>
            <span className="text-sm text-muted-foreground tabular-nums">
              of {formatPeso(progress.budgeted)}
            </span>
          </div>
          <div className="h-2 rounded-full bg-secondary overflow-hidden">
            <div
              className={cn("h-full transition-all", color)}
              style={{ width: `${Math.min(100, progress.percent_used)}%` }}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-md bg-secondary/40 p-3">
            <div className="text-muted-foreground mb-1">Remaining</div>
            <div className="font-semibold tabular-nums">
              {formatPeso(progress.remaining)}
            </div>
          </div>
          <div className="rounded-md bg-secondary/40 p-3">
            <div className="text-muted-foreground mb-1 flex items-center gap-1">
              <TrendingUp className="size-3" /> Projected EOP
            </div>
            <div
              className={cn(
                "font-semibold tabular-nums",
                progress.on_track ? "text-foreground" : "text-warning",
              )}
            >
              {formatPeso(progress.projected_end_of_period)}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
