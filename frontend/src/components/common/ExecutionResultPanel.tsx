import React, { useState } from "react";
import { ChevronDown, ChevronRight, Cpu, FileCheck, ShieldAlert, Sparkles } from "lucide-react";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const ExecutionResultPanel: React.FC<{
  result: UnifiedExecuteResponse | null;
  errorMsg?: string | null;
  title?: string;
}> = ({ result, errorMsg, title }) => {
  const [traceOpen, setTraceOpen] = useState(false);

  if (!result && !errorMsg) return null;

  if (errorMsg) {
    return (
      <div className="hf-claim contradicted mt-4">
        <div className="bar" />
        <div className="pr-2">
          <div className="flex items-start gap-2.5 text-sm">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-[var(--block)]" />
            <div>
              <div className="font-semibold text-[var(--ink)]">Execution Blocked / Error</div>
              <p className="mt-1 text-xs leading-relaxed text-[var(--ink-2)]">{errorMsg}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const isDeclined =
    result.execution_status === "rejected" || result.execution_status === "blocked";
  const isPaused = result.execution_status === "paused_hitl";

  const statusChipClass = isDeclined
    ? "hf-chip hf-chip-block"
    : isPaused
      ? "hf-chip hf-chip-escalate"
      : "hf-chip hf-chip-pass";

  const claimStateClass = isDeclined
    ? "contradicted"
    : isPaused
      ? "escalated"
      : "supported";

  const totalTokens = result.input_tokens + result.output_tokens;
  const completedSteps = result.trace_steps.length;

  return (
    <div className="space-y-4">
      <div className="hf-verdict">
        <div>
          <div className="hf-score">
            {totalTokens > 0 ? totalTokens : `${result.latency_ms}ms`}
            <small>
              {totalTokens > 0 ? `${result.latency_ms}ms latency` : "execution timing"}
            </small>
          </div>
        </div>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="hf-chip hf-chip-plain">
              <Sparkles className="h-3 w-3" />
              {title || result.routed_workflow_name}
            </span>
            <span className={statusChipClass}>{result.execution_status}</span>
            <span className="font-mono text-xs text-[var(--muted)]">
              {result.classifier_result}
            </span>
          </div>

          <div className="mt-2.5 flex flex-wrap items-center gap-2 font-mono text-[11.5px] text-[var(--muted)]">
            {result.intent_analysis?.risk_level && (
              <span className="hf-chip hf-chip-plain">
                risk:{result.intent_analysis.risk_level}
              </span>
            )}
            <span className="inline-flex items-center gap-1 text-[var(--ink-2)]">
              <Cpu className="h-3.5 w-3.5" />
              {result.model_used}
            </span>
            <span>
              &bull; {result.input_tokens} in / {result.output_tokens} out tok
              {typeof result.tokens_saved === "number" && result.tokens_saved > 0
                ? ` • ${result.tokens_saved} saved (${result.reduction_percent ?? 0}%)`
                : ""}
            </span>
          </div>

          {(result.guardrail_flags?.length || result.optimization_methods_used?.length) ? (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {result.guardrail_flags?.map((flag) => (
                <span key={flag} className="hf-chip hf-chip-escalate">
                  guardrail: {flag}
                </span>
              ))}
              {result.optimization_methods_used?.map((m) => (
                <span key={m} className="hf-chip hf-chip-plain">
                  {m}
                </span>
              ))}
            </div>
          ) : null}

          <div className="hf-meter" aria-hidden="true">
            <i
              style={{
                flexGrow: isDeclined ? 0 : Math.max(1, completedSteps),
                background: isDeclined
                  ? "var(--field-hover)"
                  : isPaused
                    ? "var(--esc)"
                    : "var(--pass)",
              }}
            />
            <i
              style={{
                flexGrow: isDeclined ? 1 : 0.15,
                background: isDeclined ? "var(--block)" : "var(--field-hover)",
              }}
            />
          </div>
        </div>
      </div>

      <div className={`hf-claim ${claimStateClass}`}>
        <div className="bar" />
        <div className="min-w-0 pr-2">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
              Agent Output
            </span>
            <span
              className="text-xs font-semibold"
              style={{
                color: isDeclined
                  ? "var(--block)"
                  : isPaused
                    ? "var(--esc)"
                    : "var(--pass)",
              }}
            >
              {isDeclined ? "blocked / refused" : isPaused ? "awaiting approval" : "completed"}
            </span>
          </div>

          <div className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink)]">
            {result.final_response_text}
          </div>

          {result.citations.length > 0 && (
            <div className="hf-quote">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                <FileCheck className="h-3.5 w-3.5 text-[var(--pass)]" />
                Grounded Citations
              </div>
              <ul className="mt-1.5 space-y-1 text-xs text-[var(--ink-2)]">
                {result.citations.map((cite, idx) => (
                  <li key={idx}>&bull; {cite}</li>
                ))}
              </ul>
            </div>
          )}

          {result.hitl_requests.length > 0 && (
            <div className="mt-3 rounded-xl border border-dashed border-[var(--esc)] bg-[var(--esc-soft)] p-3 text-xs text-[var(--ink)]">
              <div className="font-semibold text-[var(--esc)]">
                Human-in-the-Loop Approval Queued ({result.hitl_requests.length})
              </div>
              <ul className="mt-1 space-y-1 text-[var(--ink-2)]">
                {result.hitl_requests.map((h, i) => (
                  <li key={i}>
                    &bull; <strong className="text-[var(--ink)]">{h.title}</strong> ({h.action_type}) &mdash; review in
                    Agent Execution Monitor or operational tab.
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.trace_steps.length > 0 && (
            <div className="mt-3.5 border-t border-[var(--line)] pt-2.5">
              <button
                type="button"
                onClick={() => setTraceOpen((o) => !o)}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--ink-2)] hover:text-[var(--ink)]"
              >
                {traceOpen ? (
                  <ChevronDown className="h-3.5 w-3.5" />
                ) : (
                  <ChevronRight className="h-3.5 w-3.5" />
                )}
                LangGraph Execution Trace ({result.trace_steps.length} nodes)
              </button>
              {traceOpen && (
                <div className="mt-2.5 grid gap-1.5 sm:grid-cols-2">
                  {result.trace_steps.map((step, i) => (
                    <div
                      key={`${step.step}-${i}`}
                      className="flex items-center justify-between rounded-lg border border-[var(--line)] bg-[var(--field)] px-2.5 py-1.5 text-[11px]"
                    >
                      <span className="font-mono font-semibold text-[var(--ink)]">{step.step}</span>
                      <span className="truncate px-2 text-[var(--muted)]">{step.detail}</span>
                      <span className="font-mono text-[var(--muted)]">{step.duration_ms}ms</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
