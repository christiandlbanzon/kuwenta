import { Sparkles, AlertTriangle, BookOpen } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { InsightActions } from "@/components/app/insight-actions";
import { apiFetch } from "@/lib/auth.server";
import { formatRelative, formatMonth } from "@/lib/format";
import type { Insight } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function InsightsPage() {
  const insights = await apiFetch<Insight[]>("/insights");

  const summaries = insights.filter((i) => i.type === "monthly_summary");
  const anomalies = insights.filter((i) => i.type === "anomaly");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Insights</h1>
        <p className="text-muted-foreground mt-1">
          Monthly summaries land on the 1st. Anomalies surface daily.
        </p>
      </div>

      <Card className="bg-gradient-to-br from-primary/5 via-card to-accent/5 border-primary/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Generate on demand</CardTitle>
          <CardDescription>
            Don&apos;t want to wait for the cron — trigger now.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <InsightActions />
        </CardContent>
      </Card>

      {insights.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <div className="size-14 rounded-full bg-accent/15 flex items-center justify-center mx-auto mb-4 text-accent">
              <Sparkles className="size-7" />
            </div>
            <h3 className="text-lg font-semibold mb-1">Nothing yet</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Insights appear automatically once you have transaction history. Try the
              Generate buttons above to preview.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {anomalies.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <AlertTriangle className="size-4 text-warning" />
                Anomalies
              </h2>
              <div className="grid md:grid-cols-2 gap-4">
                {anomalies.slice(0, 4).map((i) => (
                  <AnomalyCard key={i.id} insight={i} />
                ))}
              </div>
            </section>
          )}

          {summaries.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <BookOpen className="size-4 text-primary" />
                Monthly summaries
              </h2>
              <div className="space-y-4">
                {summaries.map((i) => (
                  <SummaryCard key={i.id} insight={i} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function AnomalyCard({ insight }: { insight: Insight }) {
  const z = insight.insight_metadata?.z_score as number | undefined;
  return (
    <Card className="border-warning/30 bg-gradient-to-br from-warning/5 to-card">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{insight.title}</CardTitle>
          {z !== undefined && (
            <Badge variant="warning" className="shrink-0 text-[10px]">
              {z.toFixed(1)}σ
            </Badge>
          )}
        </div>
        <CardDescription>{formatRelative(insight.created_at)}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-muted-foreground">{insight.content}</p>
      </CardContent>
    </Card>
  );
}

function SummaryCard({ insight }: { insight: Insight }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">{insight.title}</CardTitle>
            <CardDescription>
              {formatMonth(insight.period_start)} • {formatRelative(insight.created_at)}
            </CardDescription>
          </div>
          <Badge variant="default" className="shrink-0">
            <Sparkles className="size-3 mr-1" /> Summary
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <article className="prose prose-sm prose-invert max-w-none [&>h2]:text-base [&>h2]:font-semibold [&>h2]:mt-4 [&>h2]:mb-2 [&>h3]:text-sm [&>h3]:font-medium [&>h3]:mt-3 [&>h3]:mb-1.5 [&>p]:text-sm [&>p]:text-muted-foreground [&>p]:leading-relaxed [&>ul]:text-sm [&>ul]:text-muted-foreground [&>ul>li]:my-0.5">
          <RenderMarkdown text={insight.content} />
        </article>
      </CardContent>
    </Card>
  );
}

/** Tiny markdown renderer — handles ## headings, ### subheadings, - bullets, **bold**.
 *  Avoids pulling in a full markdown lib for one component. */
function RenderMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];

  function flushList() {
    if (listBuffer.length === 0) return;
    out.push(
      <ul key={`ul-${out.length}`}>
        {listBuffer.map((l, i) => (
          <li key={i} dangerouslySetInnerHTML={{ __html: inline(l) }} />
        ))}
      </ul>,
    );
    listBuffer = [];
  }

  function inline(s: string): string {
    return s
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground">$1</strong>')
      .replace(/`(.+?)`/g, '<code class="bg-secondary px-1 rounded text-xs">$1</code>');
  }

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushList();
      continue;
    }
    if (line.startsWith("## ")) {
      flushList();
      out.push(<h2 key={out.length}>{line.slice(3)}</h2>);
    } else if (line.startsWith("### ")) {
      flushList();
      out.push(<h3 key={out.length}>{line.slice(4)}</h3>);
    } else if (line.startsWith("- ")) {
      listBuffer.push(line.slice(2));
    } else {
      flushList();
      out.push(<p key={out.length} dangerouslySetInnerHTML={{ __html: inline(line) }} />);
    }
  }
  flushList();
  return <>{out}</>;
}
