import React, { useState } from "react";
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
      <div className="hf-claim contradicted">
        <div className="bar" />
        <div className="pr-2 text-xs">
          <div className="font-semibold text-[var(--fg)]">Execution Blocked</div>
          <p className="mt-1 text-[var(--muted)]">{errorMsg}</p>
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

  return (
    <div className="space-y-3">
      <div className="hf-verdict">
        <div>
          <div className="hf-score">
            {totalTokens > 0 ? totalTokens : `${result.latency_ms}ms`}
            <small>{totalTokens > 0 ? `${result.latency_ms}ms` : "latency"}</small>
          </div>
        </div>

        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="hf-chip hf-chip-plain">{title || result.routed_workflow_name}</span>
            <span className={statusChipClass}>{result.execution_status}</span>
            <span className="font-mono text-[11px] text-[var(--muted)]">
              {result.classifier_result}
            </span>
            <span className="font-mono text-[11px] text-[var(--muted)]">{result.model_used}</span>
          </div>

          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-[var(--muted)]">
            {result.intent_analysis?.risk_level && (
              <span>risk:{result.intent_analysis.risk_level}</span>
            )}
            <span>
              {result.input_tokens} in / {result.output_tokens} out
              {typeof result.tokens_saved === "number" && result.tokens_saved > 0
                ? ` / ${result.tokens_saved} saved`
                : ""}
            </span>
            {result.guardrail_flags?.map((flag) => (
              <span key={flag} className="hf-chip hf-chip-escalate">
                {flag}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className={`hf-claim ${claimStateClass}`}>
        <div className="bar" />
        <div className="min-w-0 pr-2">
          <div className="flex items-center justify-between gap-2 text-xs">
            <span className="font-semibold uppercase tracking-wider text-[var(--muted)]">
              Agent Output
            </span>
            <span className="font-mono text-[11px] font-semibold text-[var(--fg)]">
              {isDeclined ? "blocked" : isPaused ? "awaiting approval" : "completed"}
            </span>
          </div>

          <div className="mt-1.5 whitespace-pre-wrap text-[13px] leading-relaxed text-[var(--fg)]">
            {result.final_response_text}
          </div>

          {result.citations.length > 0 && (
            <div className="hf-quote">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                Citations
              </div>
              <ul className="mt-1 space-y-0.5 text-xs text-[var(--fg)]">
                {result.citations.map((cite, idx) => (
                  <li key={idx}>- {cite}</li>
                ))}
              </ul>
            </div>
          )}

          {result.hitl_requests.length > 0 && (
            <div className="mt-2.5 rounded-[var(--r-field)] border border-dashed border-[var(--border)] bg-[var(--surface)] p-2.5 text-xs text-[var(--fg)]">
              <div className="font-semibold">
                Approval Queued ({result.hitl_requests.length})
              </div>
              <ul className="mt-1 space-y-0.5 text-[var(--muted)]">
                {result.hitl_requests.map((h, i) => (
                  <li key={i}>
                    - <strong className="text-[var(--fg)]">{h.title}</strong> ({h.action_type})
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.trace_steps.length > 0 && (
            <div className="mt-2.5 border-t border-[var(--border)] pt-2">
              <button
                type="button"
                onClick={() => setTraceOpen((o) => !o)}
                className="text-xs font-medium text-[var(--muted)] hover:text-[var(--fg)]"
              >
                {traceOpen ? "Hide Trace" : `Show Trace (${result.trace_steps.length})`}
              </button>
              {traceOpen && (
                <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                  {result.trace_steps.map((step, i) => (
                    <div
                      key={`${step.step}-${i}`}
                      className="flex items-center justify-between rounded-[var(--r-field)] border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-[11px]"
                    >
                      <span className="font-mono font-semibold text-[var(--fg)]">{step.step}</span>
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
