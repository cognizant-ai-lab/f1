import { useState } from "react";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import ReactMarkdown from "react-markdown";
import { Bot, Loader2, Maximize2, Radio, MessageSquare } from "lucide-react";

export interface ReportEntry {
  text: string;
  time: string;
  source?: "driver" | "engineer" | "alert" | "radio";
}

interface ExpandableReportPanelProps {
  title: string;
  responses: ReportEntry[];
  emptyMessage: string;
  className?: string;
}

export function ExpandableReportPanel({ title, responses, emptyMessage, className }: ExpandableReportPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useAutoScroll<HTMLDivElement>(responses.length);
  const expandedScrollRef = useAutoScroll<HTMLDivElement>(responses.length);

  const content = (scrollRefProp: React.RefObject<HTMLDivElement>, heightClass: string) => (
    <div ref={scrollRefProp} className={`${heightClass} overflow-y-auto`}>
      {responses.map((r, i) => {
        const isRadio = r.source === "radio";
        const isDriver = r.source === "driver";
        const bgClass = isDriver ? "bg-accent/10 border-l-2 border-l-accent"
          : isRadio ? "bg-primary/10 border-l-2 border-l-primary"
          : r.source === "alert" ? "bg-warning/5" : "";
        return (
          <div key={i} className={`flex items-start gap-2 px-3 py-2 border-b last:border-b-0 border-border/20 ${bgClass}`}>
            {isDriver
              ? <Radio className="h-3.5 w-3.5 text-accent shrink-0 mt-0.5" />
              : isRadio
              ? <Radio className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
              : r.source === "alert"
              ? <MessageSquare className="h-3.5 w-3.5 text-warning shrink-0 mt-0.5" />
              : <Bot className="h-3.5 w-3.5 text-info shrink-0 mt-0.5" />}
            <div className={`prose prose-xs prose-invert max-w-none text-[11px] leading-tight [&>p]:m-0 flex-1 ${isDriver ? "text-accent font-semibold" : isRadio ? "text-primary font-semibold" : "text-card-foreground"}`}>
              {isDriver
                ? <span><span className="font-display text-[9px] font-bold tracking-wider text-accent/60">FERNANDO &gt; </span>{r.text}</span>
                : <ReactMarkdown>{r.text}</ReactMarkdown>}
            </div>
            <span className="text-[9px] text-muted-foreground tracking-wider shrink-0">{r.time}</span>
          </div>
        );
      })}
      {responses.length === 0 && (
        <div className="flex items-center gap-2 px-3 py-3">
          <Loader2 className="h-3.5 w-3.5 text-muted-foreground animate-spin" />
          <span className="text-[11px] text-muted-foreground">{emptyMessage}</span>
        </div>
      )}
    </div>
  );

  const header = (onDoubleClick?: () => void) => (
    <div
      className="flex items-center gap-1.5 px-3 py-2 border-b border-border/50 bg-secondary/30 select-none cursor-pointer"
      onDoubleClick={onDoubleClick}
    >
      <Bot className="h-4 w-4 text-primary" />
      <span className="font-display text-sm font-bold tracking-widest uppercase text-foreground">
        {title}
      </span>
      {!expanded && <Maximize2 className="h-2.5 w-2.5 text-muted-foreground/50 ml-1" />}
      <span className="ml-auto font-display text-[10px] text-muted-foreground">{responses.length}</span>
    </div>
  );

  return (
    <>
      {/* Inline panel */}
      <div className={`bg-card border border-border/50 rounded-md overflow-hidden flex flex-col ${className ?? ""}`}>
        {header(() => setExpanded(true))}
        {content(scrollRef, className ? "flex-1" : "h-36")}
      </div>

      {/* Expanded overlay */}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setExpanded(false)}
        >
          <div
            className="bg-card border border-border/50 rounded-md overflow-hidden w-[90vw] max-w-3xl shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {header()}
            <div
              ref={expandedScrollRef}
              className="max-h-[70vh] overflow-y-auto"
            >
              {responses.map((r, i) => {
                const isRadio = r.source === "radio";
                const isDriver = r.source === "driver";
                const bgClass = isDriver ? "bg-accent/10 border-l-2 border-l-accent"
                  : isRadio ? "bg-primary/10 border-l-2 border-l-primary"
                  : r.source === "alert" ? "bg-warning/5" : "";
                return (
                  <div key={i} className={`flex items-start gap-2 px-4 py-3 border-b last:border-b-0 border-border/20 ${bgClass}`}>
                    {isDriver
                      ? <Radio className="h-4 w-4 text-accent shrink-0 mt-0.5" />
                      : isRadio
                      ? <Radio className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                      : r.source === "alert"
                      ? <MessageSquare className="h-4 w-4 text-warning shrink-0 mt-0.5" />
                      : <Bot className="h-4 w-4 text-info shrink-0 mt-0.5" />}
                    <div className={`prose prose-sm prose-invert max-w-none text-sm leading-relaxed [&>p]:m-0 flex-1 ${isDriver ? "text-accent font-semibold" : isRadio ? "text-primary font-semibold" : "text-card-foreground"}`}>
                      {isDriver
                        ? <span><span className="font-display text-[10px] font-bold tracking-wider text-accent/60">FERNANDO &gt; </span>{r.text}</span>
                        : <ReactMarkdown>{r.text}</ReactMarkdown>}
                    </div>
                    <span className="text-[10px] text-muted-foreground tracking-wider shrink-0">{r.time}</span>
                  </div>
                );
              })}
              {responses.length === 0 && (
                <div className="flex items-center gap-2 px-4 py-4">
                  <Loader2 className="h-4 w-4 text-muted-foreground animate-spin" />
                  <span className="text-sm text-muted-foreground">{emptyMessage}</span>
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
