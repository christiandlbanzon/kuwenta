"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus } from "lucide-react";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/lib/api";
import type { AccountType } from "@/lib/types";

const TYPES: { value: AccountType; label: string }[] = [
  { value: "ewallet", label: "E-wallet (GCash, Maya)" },
  { value: "bank", label: "Bank (BDO, BPI, UnionBank...)" },
  { value: "cash", label: "Cash" },
  { value: "credit_card", label: "Credit card" },
];

export function AddAccountDialog({ trigger }: { trigger?: React.ReactNode }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("ewallet");
  const [institution, setInstitution] = useState("");
  const [balance, setBalance] = useState("0");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/accounts", {
        name,
        type,
        institution: institution || null,
        current_balance: balance || "0",
      });
      setOpen(false);
      setName("");
      setInstitution("");
      setBalance("0");
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger ?? (
          <Button variant="outline" size="sm">
            <Plus className="size-4" /> Add account
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New account</DialogTitle>
          <DialogDescription>
            Track a wallet, bank account, or cash. You can add more later.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="acc-name">Name</Label>
            <Input
              id="acc-name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="GCash"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="acc-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as AccountType)}>
              <SelectTrigger id="acc-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="acc-institution">Institution (optional)</Label>
            <Input
              id="acc-institution"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="GCash, BDO, BPI..."
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="acc-balance">Current balance (₱)</Label>
            <Input
              id="acc-balance"
              type="number"
              step="0.01"
              min="0"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
            />
          </div>
          <DialogFooter className="gap-2">
            <DialogClose asChild>
              <Button type="button" variant="ghost">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={loading}>
              {loading ? <Loader2 className="size-4 animate-spin" /> : "Create account"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
