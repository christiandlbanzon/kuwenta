"use client";

import { useMemo } from "react";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { formatPesoCompact } from "@/lib/format";

interface CategorySpend {
  category: string;
  total: number;
}

const PALETTE = [
  "hsl(217 91% 60%)", // primary blue
  "hsl(45 95% 60%)", // peso gold
  "hsl(142 71% 45%)", // success green
  "hsl(280 85% 65%)", // purple
  "hsl(15 85% 60%)", // orange
  "hsl(190 80% 50%)", // teal
  "hsl(340 75% 60%)", // pink
  "hsl(60 70% 55%)", // yellow-green
];

export function CategoryDonut({ data }: { data: CategorySpend[] }) {
  const total = useMemo(() => data.reduce((s, d) => s + d.total, 0), [data]);

  if (data.length === 0 || total === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
        No spending yet this period.
      </div>
    );
  }

  return (
    <div className="relative h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="total"
            nameKey="category"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={95}
            paddingAngle={2}
            stroke="hsl(var(--card))"
            strokeWidth={2}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--popover))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value: number) => formatPesoCompact(value)}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <div className="text-xs text-muted-foreground">Total spent</div>
        <div className="text-2xl font-bold tracking-tight">
          {formatPesoCompact(total)}
        </div>
      </div>
    </div>
  );
}

export function CategoryLegend({ data }: { data: CategorySpend[] }) {
  const total = data.reduce((s, d) => s + d.total, 0);
  return (
    <ul className="space-y-2">
      {data.slice(0, 8).map((d, i) => {
        const pct = total ? (d.total / total) * 100 : 0;
        return (
          <li key={d.category} className="flex items-center gap-3 text-sm">
            <span
              className="size-2.5 rounded-full shrink-0"
              style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
            />
            <span className="flex-1 truncate text-foreground">{d.category}</span>
            <span className="text-muted-foreground tabular-nums">
              {formatPesoCompact(d.total)}
            </span>
            <span className="text-xs text-muted-foreground tabular-nums w-12 text-right">
              {pct.toFixed(1)}%
            </span>
          </li>
        );
      })}
    </ul>
  );
}
