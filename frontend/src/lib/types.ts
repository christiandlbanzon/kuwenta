/** TypeScript types matching the FastAPI response schemas. */

export type AccountType = "cash" | "bank" | "ewallet" | "credit_card";
export type TransactionType = "expense" | "income" | "transfer";
export type CategoryType = "expense" | "income";
export type BudgetPeriod = "monthly" | "weekly";
export type InsightType = "monthly_summary" | "anomaly" | "recurring_detected";
export type PaymentMethod =
  | "cash"
  | "gcash"
  | "credit_card"
  | "debit_card"
  | "maya"
  | "paymaya"
  | "bank_transfer"
  | "other";

export interface User {
  id: string;
  email: string;
  display_name: string;
  currency: string;
  timezone: string;
  created_at: string;
}

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  institution: string | null;
  current_balance: string;
  created_at: string;
}

export interface Category {
  id: string;
  name: string;
  type: CategoryType;
  parent_id: string | null;
  icon: string | null;
  color: string | null;
  is_default: boolean;
}

export interface Transaction {
  id: string;
  account_id: string;
  category_id: string | null;
  amount: string;
  type: TransactionType;
  description: string;
  merchant: string | null;
  notes: string | null;
  occurred_at: string;
  created_at: string;
  source: string;
  raw_input: string | null;
  ai_confidence: number | null;
}

export interface QuickAddDraft {
  amount: string;
  type: TransactionType;
  account_id: string;
  category_id: string | null;
  description: string;
  merchant: string | null;
  occurred_at: string;
  ai_confidence: number | null;
  raw_input: string;
}

export interface Budget {
  id: string;
  category_id: string;
  amount: string;
  period: BudgetPeriod;
  start_date: string;
  is_active: boolean;
}

export interface BudgetProgress {
  budget_id: string;
  category_id: string;
  category_name: string;
  period: BudgetPeriod;
  period_start: string;
  period_end: string;
  budgeted: string;
  spent: string;
  remaining: string;
  percent_used: number;
  projected_end_of_period: string;
  on_track: boolean;
}

export interface Insight {
  id: string;
  type: InsightType;
  title: string;
  content: string;
  insight_metadata: Record<string, unknown>;
  period_start: string;
  period_end: string;
  created_at: string;
}

export interface ToolCallTrace {
  tool: string;
  args: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface QAResponse {
  answer: string;
  tool_calls: ToolCallTrace[];
  cannot_answer: boolean;
}

export interface ReceiptExtraction {
  merchant: string | null;
  line_items: { name: string; quantity: number | null; amount: string }[];
  subtotal: string | null;
  tax: string | null;
  total: string | null;
  occurred_at: string | null;
  payment_method: PaymentMethod | null;
  category_guess: string | null;
}

export interface ReceiptUploadResponse {
  receipt_id: string;
  image_path: string;
  extracted: ReceiptExtraction;
  suggested_category_id: string | null;
  suggested_account_id: string | null;
}

export interface LLMStats {
  period_start: string;
  period_end: string;
  total_calls: number;
  by_provider: {
    provider: string;
    model: string;
    total_calls: number;
    success_calls: number;
    error_calls: number;
    p50_latency_ms: number;
    p95_latency_ms: number;
    total_input_tokens: number;
    total_output_tokens: number;
  }[];
  by_purpose: {
    purpose: string;
    total_calls: number;
    success_rate: number;
    p50_latency_ms: number;
    total_input_tokens: number;
    total_output_tokens: number;
  }[];
  total_input_tokens: number;
  total_output_tokens: number;
  projected_monthly_cost_usd: number;
}
