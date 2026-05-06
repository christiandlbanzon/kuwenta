import { cn } from "@/lib/utils";
import { formatPeso, formatDateShort } from "@/lib/format";
import type { Category, Transaction } from "@/lib/types";

const CATEGORY_EMOJI: Record<string, string> = {
  "Food & Dining": "🍱",
  Groceries: "🛒",
  Transportation: "🚗",
  "Bills & Utilities": "⚡",
  Shopping: "🛍️",
  Healthcare: "💊",
  Entertainment: "🎬",
  "Government Contributions": "🏛️",
  "Family Support": "👨‍👩‍👧",
  "Tithing & Donations": "🙏",
  Savings: "🏦",
  Investments: "📈",
  Education: "🎓",
  "Personal Care": "💅",
  Travel: "✈️",
  Salary: "💼",
  Freelance: "💻",
  Business: "🧾",
  Refund: "↩️",
  Gift: "🎁",
  Others: "📦",
  "Other Income": "💰",
};

export function TransactionRow({
  txn,
  category,
}: {
  txn: Transaction;
  category?: Category | null;
}) {
  const emoji = (category && CATEGORY_EMOJI[category.name]) || "📦";
  const isIncome = txn.type === "income";

  return (
    <div className="flex items-center gap-3 py-3 px-2 rounded-lg hover:bg-secondary/40 transition-colors">
      <div className="size-10 shrink-0 rounded-full bg-secondary/60 flex items-center justify-center text-lg">
        {emoji}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">
            {txn.merchant || txn.description}
          </span>
          {txn.source !== "manual" && (
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground bg-secondary/60 px-1.5 py-0.5 rounded">
              {txn.source.replace("_", " ")}
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
          <span className="truncate">{category?.name ?? "Uncategorized"}</span>
          <span>•</span>
          <span>{formatDateShort(txn.occurred_at)}</span>
        </div>
      </div>
      <div
        className={cn(
          "tabular-nums text-sm font-semibold shrink-0",
          isIncome ? "text-success" : "text-foreground",
        )}
      >
        {isIncome ? "+" : ""}
        {formatPeso(txn.amount)}
      </div>
    </div>
  );
}
