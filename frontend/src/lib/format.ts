/**
 * Peso + date formatting helpers used everywhere in the UI.
 * Always Asia/Manila timezone, always PHP currency.
 */
import { format, formatDistanceToNow, parseISO } from "date-fns";

const phpFormatter = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const phpCompact = new Intl.NumberFormat("en-PH", {
  style: "currency",
  currency: "PHP",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

/** ₱1,234.56 */
export function formatPeso(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "₱0.00";
  const n = typeof value === "string" ? Number.parseFloat(value) : value;
  if (Number.isNaN(n)) return "₱0.00";
  return phpFormatter.format(n);
}

/** ₱1,234 (no decimals) — for dashboards where precision isn't useful */
export function formatPesoCompact(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "₱0";
  const n = typeof value === "string" ? Number.parseFloat(value) : value;
  if (Number.isNaN(n)) return "₱0";
  return phpCompact.format(n);
}

/** "Apr 15, 2026" */
export function formatDate(iso: string): string {
  return format(parseISO(iso), "MMM d, yyyy");
}

/** "Apr 15" (no year) */
export function formatDateShort(iso: string): string {
  return format(parseISO(iso), "MMM d");
}

/** "3 days ago", "in 2 hours" */
export function formatRelative(iso: string): string {
  return formatDistanceToNow(parseISO(iso), { addSuffix: true });
}

/** "April 2026" */
export function formatMonth(iso: string): string {
  return format(parseISO(iso), "MMMM yyyy");
}

/** Pretty number with thousands separator: 1,234 */
export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-PH").format(n);
}

/** "+12.3%" or "-5.0%" */
export function formatPercentChange(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}
