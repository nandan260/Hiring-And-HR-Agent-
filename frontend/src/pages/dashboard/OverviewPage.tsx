import React, { useState } from "react";
import { Link } from "react-router-dom";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const OverviewPage: React.FC = () => {
  const { workspace, executeWorkflow, executions } = useApp();
  const [quickPrompt, setQuickPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const metrics = workspace?.metrics;
  const quota = workspace?.quota;

  const kpis: Array<{ label: string; value: string }> = [
    { label: "Total Jobs", value: String(metrics?.total_jobs_count ?? 0) },
    { label: "Total Candidates", value: String(metrics?.candidate_count ?? 0) },
    { label: "Resumes Analyzed", value: String(metrics?.resumes_analyzed_count ?? 0) },
    {
      label: "Interviews Scheduled",
      value: String(metrics?.scheduled_interviews_count ?? metrics?.interview_count ?? 0),
    },
    { label: "Pending Onboarding", value: String(metrics?.pending_onboarding_count ?? 0) },
    { label: "Completed Executions", value: String(metrics?.completed_executions ?? 0) },
    { label: "Failed Executions", value: String(metrics?.failed_executions ?? 0) },
    {
      label: "Token Consumption",
      value: (quota?.tokens_used_this_month ?? 0).toLocaleString(),
    },
    {
      label: "Estimated AI Costs",
      value: `$${(metrics?.estimated_ai_cost_usd ?? 0).toFixed(4)}`,
    },
  ];

  const handleQuickRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickPrompt.trim()) return;
    setRunning(true);
    setErrorMsg(null);
    const res = await executeWorkflow({ prompt: quickPrompt.trim() });
    setRunning(false);
    if (res.ok && res.data) {
      setResult(res.data);
    } else {
      setErrorMsg(res.error || "Execution failed.");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Dashboard</h1>
        <form onSubmit={handleQuickRun} className="flex w-full max-w-xl items-center gap-2">
          <input
            type="text"
            value={quickPrompt}
            onChange={(e) => setQuickPrompt(e.target.value)}
            placeholder="Run any HR task..."
            className="hf-input flex-1"
          />
          <button
            type="submit"
            disabled={running || !quickPrompt.trim()}
            className="hf-btn hf-btn-primary whitespace-nowrap"
          >
            {running ? "Running..." : "Execute"}
          </button>
        </form>
      </div>

      <div className="grid flex-none grid-cols-3 gap-2.5 sm:grid-cols-5">
        {kpis.map((item) => (
          <div
            key={item.label}
            className="rounded-[var(--r-field)] border border-[var(--border)] px-3 py-2"
          >
            <div className="text-[11px] font-medium text-[var(--muted)]">{item.label}</div>
            <div className="mt-1 font-mono text-lg font-bold leading-none tabular-nums text-[var(--fg)]">
              {item.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
        <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-7">
          <div className="mb-2 flex flex-none items-center justify-between">
            <h2 className="hf-h2">Execution Log</h2>
            <Link
              to="/dashboard/monitor"
              className="text-xs font-medium text-[var(--muted)] hover:text-[var(--fg)]"
            >
              Open Monitor
            </Link>
          </div>
          {executions.length === 0 ? (
            <div className="hf-empty my-auto">No runs recorded yet.</div>
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <table className="hf-rows">
                <thead>
                  <tr>
                    <th>Workflow</th>
                    <th>Status</th>
                    <th>Model Tier</th>
                    <th className="num">Tokens</th>
                    <th className="num">Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {executions.slice(0, 12).map((exec) => {
                    const tok =
                      exec.token_usage?.total_tokens ??
                      (exec.token_usage?.input_tokens ?? 0) + (exec.token_usage?.output_tokens ?? 0);
                    return (
                      <tr key={exec.id}>
                        <td className="font-medium text-[var(--fg)]">{exec.workflow_slug}</td>
                        <td>
                          <span
                            className={`hf-chip ${
                              exec.status === "completed"
                                ? "hf-chip-pass"
                                : exec.status === "paused_hitl"
                                  ? "hf-chip-escalate"
                                  : "hf-chip-block"
                            }`}
                          >
                            {exec.status}
                          </span>
                        </td>
                        <td className="font-mono text-xs text-[var(--muted)]">
                          {exec.model_tier_used}
                        </td>
                        <td className="num text-[var(--fg)]">{tok}</td>
                        <td className="num text-[var(--muted)]">{exec.latency_ms}ms</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-5">
          <h2 className="hf-h2 mb-2 flex-none">Output</h2>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {result || errorMsg ? (
              <ExecutionResultPanel result={result} errorMsg={errorMsg} />
            ) : (
              <div className="hf-empty">Submit a command above to inspect output.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
