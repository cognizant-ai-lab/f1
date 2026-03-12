import { useState } from "react";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import ReactMarkdown from "react-markdown";
import { AlertTriangle, Info, CheckCircle, Bot, Loader2, Maximize2, Wind } from "lucide-react";
import type { Alert } from "@/components/AlertBox";
import type { DamageReportEntry } from "@/hooks/useAeroTelemetry";

type UnifiedItem =
  | { kind: "alert"; level: Alert["level"]; message: string; time: string; sortKey: string }
  | { kind: "engineer"; text: string; time: string; sortKey: string };

function extractSortKey(time: string): string {
  return time.slice(0, 5);
}

function mergeItems(alerts: Alert[], responses: DamageReportEntry[]): UnifiedItem[] {
  const alertItems: UnifiedItem[] = alerts.map((a) => ({
    kind: "alert" as const,
    level: a.level,
    message: a.message,
    time: a.time,
    sortKey: extractSortKey(a.time),
  }));
  const engineerItems: UnifiedItem[] = responses.map((r) => ({
    kind: "engineer" as const,
    text: r.text,
    time: r.time,
    sortKey: extractSortKey(r.time),
  }));

  const result: UnifiedItem[] = [];
  let ai = 0;
  let ei = 0;
  while (ai < alertItems.length && ei < engineerItems.length) {
    if (alertItems[ai].sortKey <= engineerItems[ei].sortKey) {
      result.push(alertItems[ai++]);
    } else {
      result.push(engineerItems[ei++]);
    }
  }
  while (ai < alertItems.length) result.push(alertItems[ai++]);
  while (ei < engineerItems.length) result.push(engineerItems[ei++]);
  return result;
}

const alertIcons = {
  info: <Info className="h-3.5 w-3.5 text-info shrink-0" />,
  warning: <AlertTriangle className="h-3.5 w-3.5 text-warning shrink-0" />,
  critical: <AlertTriangle className="h-3.5 w-3.5 text-accent shrink-0" />,
};

const expandedAlertIcons = {
  info: <Info className="h-4 w-4 text-info shrink-0" />,
  warning: <AlertTriangle className="h-4 w-4 text-warning shrink-0" />,
  critical: <AlertTriangle className="h-4 w-4 text-accent shrink-0" />,
};

const rowStyles = {
  info: "border-info/20",
  warning: "border-warning/20",
  critical: "border-accent/20 bg-accent/5",
};

interface DamageAlertPanelProps {
  alerts: Alert[];
  activeCount: number;
  engineerResponses: DamageReportEntry[];
}

export function DamageAlertPanel({ alerts, activeCount, engineerResponses }: DamageAlertPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const items = mergeItems(alerts, engineerResponses);
  const scrollRef = useAutoScroll<HTMLDivElement>(items.length);
  const expandedScrollRef = useAutoScroll<HTMLDivElement>(items.length);
  const hasCritical = alerts.some((a) => a.level === "critical");
  const counterColor = activeCount === 0 ? "text-primary" : hasCritical ? "text-accent" : "text-warning";

  const renderItem = (item: UnifiedItem, i: number, isExpanded: boolean) => {
    if (item.kind === "alert") {
      return (
        <div key={`a-${i}`} className={`flex items-start gap-2 ${isExpanded ? "px-4 py-3" : "px-3 py-2"} border-b last:border-b-0 ${rowStyles[item.level]}`}>
          {isExpanded ? expandedAlertIcons[item.level] : alertIcons[item.level]}
          <span className={`${isExpanded ? "text-sm leading-relaxed" : "text-[11px] leading-tight"} text-card-foreground flex-1`}>{item.message}</span>
          <span className={`${isExpanded ? "text-[10px]" : "text-[9px]"} text-muted-foreground tracking-wider shrink-0`}>{item.time}</span>
        </div>
      );
    }
    return (
      <div key={`e-${i}`} className={`flex items-start gap-2 ${isExpanded ? "px-4 py-3" : "px-3 py-2"} border-b last:border-b-0 border-border/20`}>
        {isExpanded
          ? <Bot className="h-4 w-4 text-info shrink-0 mt-0.5" />
          : <Bot className="h-3.5 w-3.5 text-info shrink-0 mt-0.5" />
        }
        <div className={`prose ${isExpanded ? "prose-sm" : "prose-xs"} prose-invert max-w-none ${isExpanded ? "text-sm leading-relaxed" : "text-[11px] leading-tight"} text-card-foreground flex-1 [&>p]:m-0`}>
          <ReactMarkdown>{item.text}</ReactMarkdown>
        </div>
        <span className={`${isExpanded ? "text-[10px]" : "text-[9px]"} text-muted-foreground tracking-wider shrink-0`}>{item.time}</span>
      </div>
    );
  };

  const hasAnalysis = engineerResponses.length > 0;

  return (
    <>
      <div className="bg-card border border-border/50 rounded-md overflow-hidden flex flex-col flex-1 min-h-36">
        <div
          className="flex items-center gap-1.5 px-3 py-2 border-b border-border/50 bg-secondary/30 select-none cursor-pointer shrink-0"
          onDoubleClick={() => setExpanded(true)}
        >
          <Wind className="h-4 w-4 text-primary" />
          <span className="font-display text-sm font-bold tracking-widest uppercase text-foreground">Damage Agent</span>
          <Maximize2 className="h-2.5 w-2.5 text-muted-foreground/50 ml-1" />
          {hasAnalysis && <Bot className="h-4 w-4 text-info ml-1" />}
          <span className={`ml-auto font-display text-[10px] font-bold ${counterColor}`}>{activeCount}</span>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {items.map((item, i) => renderItem(item, i, false))}
          {items.length === 0 && (
            <div className="flex items-center gap-2 px-3 py-3">
              <CheckCircle className="h-3.5 w-3.5 text-primary" />
              <span className="text-[11px] text-muted-foreground">No alerts</span>
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setExpanded(false)}
        >
          <div
            className="bg-card border border-border/50 rounded-md overflow-hidden w-[90vw] max-w-3xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border/50 bg-secondary/30">
              <AlertTriangle className="h-3 w-3 text-muted-foreground" />
              <span className="font-display text-sm font-bold tracking-widest uppercase text-foreground">Damage Agent</span>
              {hasAnalysis && <Bot className="h-4 w-4 text-info ml-1" />}
              <span className={`ml-auto font-display text-[10px] font-bold ${counterColor}`}>{activeCount}</span>
            </div>
            <div ref={expandedScrollRef} className="max-h-[70vh] overflow-y-auto">
              {items.map((item, i) => renderItem(item, i, true))}
              {items.length === 0 && (
                <div className="flex items-center gap-2 px-4 py-4">
                  <CheckCircle className="h-4 w-4 text-primary" />
                  <span className="text-sm text-muted-foreground">No alerts</span>
                </div>
              )}
            </div>
            <div
              className="px-4 py-2 border-t border-border/50 bg-secondary/30 text-center cursor-pointer"
              onClick={() => setExpanded(false)}
            >
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-display">
                Click to close
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
