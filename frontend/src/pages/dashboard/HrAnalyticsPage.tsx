import React, { useState } from "react";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { OptimizationComparisonResult, UnifiedExecuteResponse } from "../../types/agent";

export const HrAnalyticsPage: React.FC = () => {
  const { workspace, usageStats, executeWorkflow, refreshWorkspaceData } = useApp();
  const [tab, setTab] = useState<"reports" | "ab" | "usage">("reports");
  const [question, setQuestion] = useState(
    "Show hiring funnel conversion rates, candidate pipeline metrics, and AI token cost breakdown"
  );
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [comparePrompt, setComparePrompt] = useState(
    "Summarize hiring bottlenecks, open roles, and onboarding KYC completion status."
  );
  const [comparing, setComparing] = useState(false);
  const [compareRes, setCompareRes] = useState<OptimizationComparisonResult | null>(null);
  const [compareErr, setCompareErr] = useState<string | null>(null);

  const metrics = workspace?.metrics;
  const quota = workspace?.quota;

  const handleRunAnalytics = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    const res = await executeWorkflow({
      prompt: question.trim(),
      workflow_hint: "hr-analytics",
    });
    setRunning(false);
    if (res.ok && res.data) {
      setResult(res.data);
    } else {
      setErrorMsg(res.error || "Analytics query failed.");
    }
  };

  const handleCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comparePrompt.trim()) return;
    setComparing(true);
    setCompareErr(null);
    try {
      const data = await apiClient.compareOptimization({
        prompt: comparePrompt.trim(),
        record_telemetry: true,
      });
      setCompareRes(data);
      await refreshWorkspaceData();
    } catch (err) {
      setCompareErr(err instanceof Error ? err.message : "Comparison failed.");
    } finally {
      setComparing(false);
    }
  };

  const byWorkflow = usageStats?.by_workflow || [];
  const maxWorkflowTokens = Math.max(1, ...byWorkflow.map((a) => a.total_tokens));

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">HR Analytics</h1>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("reports")}
            className={`hf-tab ${tab === "reports" ? "active" : ""}`}
          >
            Reports
          </button>
          <button
            type="button"
            onClick={() => setTab("ab")}
            className={`hf-tab ${tab === "ab" ? "active" : ""}`}
          >
            Optimization A/B
          </button>
          <button
            type="button"
            onClick={() => setTab("usage")}
            className={`hf-tab ${tab === "usage" ? "active" : ""}`}
          >
            Token Log
          </button>
        </div>
      </div>

      <div className="hf-stats">
        <div className="hf-stat">
          <div className="hf-stat-k">Candidates</div>
          <div className="hf-stat-v">{metrics?.candidate_count ?? 0}</div>
        </div>
        <div className="hf-stat">
          <div className="hf-stat-k">Interviews</div>
          <div className="hf-stat-v">{metrics?.interview_count ?? 0}</div>
        </div>
        <div className="hf-stat">
          <div className="hf-stat-k">Tokens Used</div>
          <div className="hf-stat-v">{(quota?.tokens_used_this_month ?? 0).toLocaleString()}</div>
        </div>
        <div className="hf-stat">
          <div className="hf-stat-k">Estimated Cost</div>
          <div className="hf-stat-v">
            ${(usageStats?.optimization_summary?.total_estimated_cost_usd ?? 0).toFixed(4)}
          </div>
        </div>
      </div>

      {tab === "reports" && (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <form onSubmit={handleRunAnalytics} className="hf-card flex flex-none items-center gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask HR analytics question..."
              required
              className="hf-input flex-1"
            />
            <button type="submit" disabled={running} className="hf-btn hf-btn-primary whitespace-nowrap">
              {running ? "Analyzing..." : "Run Analytics"}
            </button>
          </form>

          <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
            <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-5">
              <h2 className="hf-h2 mb-2 flex-none">Usage by Workflow</h2>
              {byWorkflow.length === 0 ? (
                <div className="hf-empty my-auto">No workflow token data.</div>
              ) : (
                <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto">
                  {byWorkflow.map((item) => {
                    const pct = Math.round((item.total_tokens / maxWorkflowTokens) * 100);
                    return (
                      <div key={item.workflow_slug} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-mono text-[var(--fg)]">{item.workflow_slug}</span>
                          <span className="font-mono text-[var(--muted)]">
                            {item.total_tokens.toLocaleString()} tok / {item.runs} runs
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full border border-[var(--border)]">
                          <div className="h-full bg-[var(--fg)]" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="hf-card col-span-12 flex min-h-0 flex-col overflow-y-auto lg:col-span-7">
              {result || errorMsg ? (
                <ExecutionResultPanel result={result} errorMsg={errorMsg} title="HR Analytics" />
              ) : (
                <div className="hf-empty my-auto">Run Analytics to inspect query output.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === "ab" && (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <form onSubmit={handleCompare} className="hf-card flex flex-none items-center gap-2">
            <input
              type="text"
              value={comparePrompt}
              onChange={(e) => setComparePrompt(e.target.value)}
              placeholder="Prompt to benchmark optimized vs raw baseline..."
              className="hf-input flex-1"
            />
            <button type="submit" disabled={comparing} className="hf-btn hf-btn-primary whitespace-nowrap">
              {comparing ? "Comparing..." : "Run A/B Benchmark"}
            </button>
          </form>

          <div className="hf-card min-h-0 flex-1 overflow-y-auto">
            {compareErr ? (
              <div className="text-xs text-[var(--fg)]">{compareErr}</div>
            ) : !compareRes ? (
              <div className="hf-empty">Run A/B benchmark to measure real token reduction.</div>
            ) : (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="hf-subcard space-y-1">
                  <div className="text-xs font-semibold text-[var(--muted)]">Unoptimized Baseline</div>
                  <div className="font-mono text-2xl font-bold text-[var(--fg)]">
                    {compareRes.unoptimized.total_tokens} tok
                  </div>
                  <div className="text-xs text-[var(--muted)]">
                    ${compareRes.unoptimized.estimated_cost_usd.toFixed(6)} / {compareRes.unoptimized.model_used}
                  </div>
                </div>

                <div className="hf-subcard space-y-1">
                  <div className="text-xs font-semibold text-[var(--muted)]">Optimized Execution</div>
                  <div className="font-mono text-2xl font-bold text-[var(--fg)]">
                    {compareRes.optimized.total_tokens} tok ({compareRes.measured_diff.input_reduction_percent}% saved)
                  </div>
                  <div className="text-xs text-[var(--muted)]">
                    ${compareRes.optimized.estimated_cost_usd.toFixed(6)} / {compareRes.optimized.model_used}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "usage" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col">
          {byWorkflow.length === 0 ? (
            <div className="hf-empty my-auto">No usage telemetry yet.</div>
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <table className="hf-rows">
                <thead>
                  <tr>
                    <th>Workflow</th>
                    <th className="num">Executions</th>
                    <th className="num">Input</th>
                    <th className="num">Output</th>
                    <th className="num">Total Tokens</th>
                    <th className="num">Cost USD</th>
                  </tr>
                </thead>
                <tbody>
                  {byWorkflow.map((a) => (
                    <tr key={a.workflow_slug}>
                      <td className="font-mono font-medium text-[var(--fg)]">{a.workflow_slug}</td>
                      <td className="num">{a.runs}</td>
                      <td className="num">{a.input_tokens.toLocaleString()}</td>
                      <td className="num">{a.output_tokens.toLocaleString()}</td>
                      <td className="num font-semibold">{a.total_tokens.toLocaleString()}</td>
                      <td className="num font-mono">${a.estimated_cost_usd.toFixed(5)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
