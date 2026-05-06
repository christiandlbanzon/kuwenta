"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, Loader2, MessagesSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { QAResponse, ToolCallTrace } from "@/lib/types";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallTrace[];
  cannotAnswer?: boolean;
  error?: string;
}

const SUGGESTIONS = [
  "How much did I spend on food this month?",
  "What's my biggest expense category this year?",
  "Compare my Grab spending this month vs last",
  "Show me transactions over ₱1000 last week",
  "Magkano nagastos ko sa Lazada this year?",
  "Who are my top 5 merchants this month?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function send(text: string) {
    if (!text.trim() || loading) return;
    const id = crypto.randomUUID();
    const userMsg: ChatMessage = { id, role: "user", content: text };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);
    try {
      const resp = await api.post<QAResponse>("/qa", { question: text });
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: resp.answer,
          toolCalls: resp.tool_calls,
          cannotAnswer: resp.cannot_answer,
        },
      ]);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong.";
      setMessages((m) => [
        ...m,
        { id: crypto.randomUUID(), role: "assistant", content: "", error: msg },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)] md:h-[calc(100vh-7rem)] max-w-3xl mx-auto">
      <div className="mb-4">
        <h1 className="text-3xl font-bold tracking-tight">Ask Kuwenta</h1>
        <p className="text-muted-foreground mt-1">
          Plain English or Taglish. Powered by 7 typed query primitives — never raw SQL.
        </p>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-4 pr-2 -mr-2"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="size-14 rounded-full bg-primary/15 flex items-center justify-center text-primary mb-4">
              <MessagesSquare className="size-7" />
            </div>
            <h2 className="text-lg font-semibold mb-1">Ask anything about your money</h2>
            <p className="text-sm text-muted-foreground max-w-md mb-6">
              Categories, merchants, periods, comparisons, budget status — all answered with peso-formatted prose grounded in your real data.
            </p>
            <div className="grid sm:grid-cols-2 gap-2 w-full max-w-xl">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm px-4 py-3 rounded-lg border border-border/60 bg-card/40 hover:bg-card hover:border-primary/40 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <ChatBubble key={m.id} message={m} />
        ))}
        {loading && (
          <div className="flex gap-3 animate-fade-in">
            <div className="size-8 shrink-0 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-primary-foreground">
              <Sparkles className="size-4" />
            </div>
            <div className="rounded-2xl rounded-tl-sm bg-card border border-border/60 px-4 py-3 flex items-center gap-2">
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Planning, querying, summarizing...
              </span>
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-4 flex gap-2 sticky bottom-0 bg-background/80 backdrop-blur pt-2"
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything — magkano, compare, top categories..."
          disabled={loading}
          autoFocus
        />
        <Button type="submit" disabled={!input.trim() || loading} size="lg">
          <Send className="size-4" />
        </Button>
      </form>
    </div>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-3 animate-fade-in", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "size-8 shrink-0 rounded-full flex items-center justify-center text-xs font-semibold",
          isUser
            ? "bg-secondary text-foreground"
            : "bg-gradient-to-br from-primary to-accent text-primary-foreground",
        )}
      >
        {isUser ? "You" : <Sparkles className="size-4" />}
      </div>
      <div className={cn("flex-1 min-w-0", isUser && "flex justify-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 max-w-[85%] text-sm leading-relaxed",
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-sm"
              : "bg-card border border-border/60 rounded-tl-sm",
          )}
        >
          {message.error ? (
            <span className="text-destructive">{message.error}</span>
          ) : (
            <div className="whitespace-pre-wrap">{message.content}</div>
          )}
        </div>
        {message.toolCalls && message.toolCalls.length > 0 && (
          <details className="mt-2 text-xs text-muted-foreground group">
            <summary className="cursor-pointer hover:text-foreground transition-colors flex items-center gap-2">
              <Badge variant="secondary" className="text-[10px]">
                {message.toolCalls.length} tool call
                {message.toolCalls.length === 1 ? "" : "s"}
              </Badge>
              <span>view trace</span>
            </summary>
            <div className="mt-2 space-y-2">
              {message.toolCalls.map((tc, i) => (
                <Card key={i} className="bg-secondary/40">
                  <CardContent className="p-3 font-mono text-[11px] space-y-1">
                    <div>
                      <span className="text-accent">{tc.tool}</span>
                      <span className="text-muted-foreground">(</span>
                      <span>{JSON.stringify(tc.args)}</span>
                      <span className="text-muted-foreground">)</span>
                    </div>
                    {tc.error && (
                      <div className="text-destructive">{tc.error}</div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
