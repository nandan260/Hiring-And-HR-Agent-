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
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-900">
        <div className="flex items-start gap-2.5">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          <div>
            <div className="font-semibold">Execution Blocked / Error</div>
            <p className="mt-1 leading-relaxed">{errorMsg}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const isDeclined =
    result.execution_status === "rejected" || result.execution_status === "blocked";

  return (
    <div
      className={`rounded-2xl border p-5 ${
        isDeclined
          ? "border-rose-200 bg-rose-50/70"
          : result.execution_status === "paused_hitl"
            ? "border-amber-200 bg-amber-50/40"
            : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-700">
            <Sparkles className="h-3 w-3" />
            {title || result.routed_workflow_name}
          </span>
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
              result.execution_status === "completed"
                ? "bg-emerald-50 text-emerald-700"
                : result.execution_status === "paused_hitl"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-rose-100 text-rose-800"
            }`}
          >
            {result.execution_status}
          </span>
          <span className="font-mono text-[11px] text-slate-500">
            {result.classifier_result}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3 font-mono text-[11px] text-slate-500">
          {result.intent_analysis?.risk_level && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
              risk:{result.intent_analysis.risk_level}
            </span>
          )}
          <span className="inline-flex items-center gap-1">
            <Cpu className="h-3 w-3" />
            {result.model_used}
          </span>
          <span>
            {result.input_tokens + result.output_tokens} tok ({result.latency_ms}ms)
            {typeof result.tokens_saved === "number" && result.tokens_saved > 0
              ? ` • -${result.tokens_saved} (${result.reduction_percent ?? 0}% saved)`
              : ""}
          </span>
        </div>
      </div>

      {((result.guardrail_flags && result.guardrail_flags.length > 0) ||
        (result.optimization_methods_used && result.optimization_methods_used.length > 0)) && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {result.guardrail_flags?.map((flag) => (
            <span
              key={flag}
              className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800"
            >
              guardrail: {flag}
            </span>
          ))}
          {result.optimization_methods_used?.map((m) => (
            <span
              key={m}
              className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700"
            >
              {m}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
        {result.final_response_text}
      </div>

      {result.citations.length > 0 && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            <FileCheck className="h-3.5 w-3.5 text-emerald-600" />
            Grounded Citations
          </div>
          <ul className="mt-1.5 space-y-1 text-xs text-slate-700">
            {result.citations.map((cite, idx) => (
              <li key={idx}>• {cite}</li>
            ))}
          </ul>
        </div>
      )}

      {result.hitl_requests.length > 0 && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950">
          <div className="font-semibold">
            Human-in-the-Loop Approval Queued ({result.hitl_requests.length})
          </div>
          <ul className="mt-1 space-y-1">
            {result.hitl_requests.map((h, i) => (
              <li key={i}>
                • <strong>{h.title}</strong> ({h.action_type}) — review in Agent Execution Monitor
                or operational tab.
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.trace_steps.length > 0 && (
        <div className="mt-3 border-t border-slate-200/70 pt-2.5">
          <button
            type="button"
            onClick={() => setTraceOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-500"
          >
            {traceOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            LangGraph Execution Trace ({result.trace_steps.length} nodes)
          </button>
          {traceOpen && (
            <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
              {result.trace_steps.map((step, i) => (
                <div
                  key={`${step.step}-${i}`}
                  className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-[11px]"
                >
                  <span className="font-mono font-semibold text-slate-800">{step.step}</span>
                  <span className="truncate px-2 text-slate-500">{step.detail}</span>
                  <span className="font-mono text-slate-400">{step.duration_ms}ms</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
