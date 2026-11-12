import React, { useState } from "react";
import { BarChart3, Database, Gauge, Play, Sparkles } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { apiClient } from "../../services/apiClient";
import type { OptimizationComparisonResult, UnifiedExecuteResponse } from "../../types/agent";

const PRESET_QUERIES = [
  "Generate hiring pipeline metrics, candidate stage counts, and average time-to-hire report.",
  "Analyze token usage and cost breakdown across all active HR workflows this month.",
  "Summarize interview conversion and employee onboarding completion rates.",
];

export const HrAnalyticsPage: React.FC = () => {
  const { workspace, usageStats, executeWorkflow, refreshWorkspaceData } = useApp();
  const [queryPrompt, setQueryPrompt] = useState(PRESET_QUERIES[0]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);
  const [comparePrompt, setComparePrompt] = useState(
    "What is our employee parental leave and remote work reimbursement policy?"
  );
  const [compareResult, setCompareResult] = useState<OptimizationComparisonResult | null>(null);
  const [compareErr, setCompareErr] = useState<string | null>(null);

  const handleRunAnalytics = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!queryPrompt.trim()) return;
    setRunning(true);
    setErrorMsg(null);
    setResult(null);

    const res = await executeWorkflow({
      prompt: queryPrompt.trim(),
      workflow_hint: "hr-analytics",
    });
    setRunning(false);
    if (!res.ok) {
      setErrorMsg(res.error || "HR Analytics query blocked or failed");
    } else if (res.data) {
      setResult(res.data);
    }
  };

  const handleRunComparison = async () => {
    if (!comparePrompt.trim()) return;
    setComparing(true);
    setCompareErr(null);
    try {
      const data = await apiClient.compareOptimization({
        prompt: comparePrompt.trim(),
        record_telemetry: true,
      });
      setCompareResult(data);
      await refreshWorkspaceData();
    } catch (err) {
      setCompareErr(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setComparing(false);
    }
  };

  const charts = result?.charts || [];
  const byWf = usageStats?.by_workflow || [];
  const optSum = usageStats?.optimization_summary;
  const recentEntries = usageStats?.recent_entries || [];
  const maxWfTokens = Math.max(1, ...byWf.map((w) => w.total_tokens));

  return (
    <div className="space-y-6">
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">HR Analytics</h1>
          <p className="hf-lede">
            Live tenant workforce telemetry, workflow token accounting, and sqlglot-validated
            analytics reports.
          </p>
        </div>
        <span className="hf-chip hf-chip-pass">
          <Database className="h-3.5 w-3.5" />
          Read-Only SQL Validation
        </span>
      </div>

      {/* Live Workspace KPIs */}
      <div className="hf-stats">
        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Total Executions</div>
          <div className="hf-stat-v">{workspace?.metrics.total_executions ?? 0}</div>
        </div>
        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Candidates Tracked</div>
          <div className="hf-stat-v">{workspace?.metrics.candidate_count ?? 0}</div>
        </div>
        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Tokens Used (Month)</div>
          <div className="hf-stat-v">
            {(usageStats?.tokens_used_this_month ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="hf-stat border-b-0 border-r-0">
          <div className="hf-stat-k">Remaining Quota</div>
          <div className="hf-stat-v text-[var(--pass)]">
            {(usageStats?.remaining_tokens ?? 0).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Token Breakdown by Workflow */}
      <div className="hf-card">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-[var(--muted)]" />
          <h2 className="hf-h2 mb-0">Token Consumption by HR Workflow</h2>
        </div>

        {byWf.length === 0 ? (
          <p className="mt-3 text-xs text-[var(--muted)]">No token usage recorded yet this month.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {byWf.map((row) => (
              <div key={row.workflow_slug} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-[var(--ink)]">
                    {row.workflow_name} ({row.runs} runs)
                  </span>
                  <span className="font-mono text-[var(--muted)]">
                    {row.total_tokens.toLocaleString()} tok &bull; $
                    {row.estimated_cost_usd.toFixed(4)}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--field)]">
                  <div
                    className="h-full rounded-full bg-[var(--action)]"
                    style={{
                      width: `${Math.max(4, Math.round((row.total_tokens / maxWfTokens) * 100))}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Measured Optimization Telemetry & Real A/B Comparison */}
      <div className="hf-card space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-[var(--muted)]" />
            <h2 className="hf-h2 mb-0">Measured Token Optimization &amp; Cost Telemetry</h2>
          </div>
          <span className="text-xs text-[var(--muted)]">
            Real logged counters across {optSum?.total_runs_measured ?? 0} measured execution(s)
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <div className="hf-subcard">
            <div className="text-[11px] font-medium text-[var(--muted)]">
              Unoptimized Baseline Input
            </div>
            <div className="mt-1 text-lg font-bold text-[var(--ink)] tabular-nums">
              {(optSum?.total_baseline_input_tokens ?? 0).toLocaleString()} tok
            </div>
          </div>
          <div className="hf-subcard">
            <div className="text-[11px] font-medium text-[var(--muted)]">
              Actual Sent Input Tokens
            </div>
            <div className="mt-1 text-lg font-bold text-[var(--ink)] tabular-nums">
              {(optSum?.total_actual_input_tokens ?? 0).toLocaleString()} tok
            </div>
          </div>
          <div className="hf-subcard">
            <div className="text-[11px] font-medium text-[var(--muted)]">Measured Reduction</div>
            <div className="mt-1 text-lg font-bold text-[var(--pass)] tabular-nums">
              {(optSum?.total_measured_tokens_saved ?? 0).toLocaleString()} tok (
              {optSum?.measured_reduction_percent ?? 0}%)
            </div>
          </div>
          <div className="hf-subcard">
            <div className="text-[11px] font-medium text-[var(--muted)]">Total Estimated Cost</div>
            <div className="mt-1 text-lg font-bold text-[var(--ink)] tabular-nums">
              ${(optSum?.total_estimated_cost_usd ?? 0).toFixed(4)}
            </div>
          </div>
        </div>

        {/* Side-by-Side Real Comparison Benchmark */}
        <div className="hf-subcard space-y-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--ink)]">
            <Sparkles className="h-3.5 w-3.5 text-[var(--pass)]" />
            Live Unoptimized vs. Optimized Comparison (Measured A/B Run)
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={comparePrompt}
              onChange={(e) => setComparePrompt(e.target.value)}
              className="hf-input flex-1 bg-[var(--panel)]"
            />
            <button
              type="button"
              onClick={handleRunComparison}
              disabled={comparing}
              className="hf-btn hf-btn-primary hf-btn-sm shrink-0"
            >
              {comparing ? "Benchmarking..." : "Run A/B Benchmark"}
            </button>
          </div>
          {compareErr && <p className="text-xs font-medium text-[var(--block)]">{compareErr}</p>}
          {compareResult && (
            <div className="grid gap-3 pt-1 text-xs sm:grid-cols-3">
              <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
                <div className="font-semibold text-[var(--muted)]">Unoptimized Run</div>
                <div className="mt-1 font-mono text-[var(--ink)]">
                  In: {compareResult.unoptimized.input_tokens} | Out:{" "}
                  {compareResult.unoptimized.output_tokens}
                </div>
                <div className="text-[11px] text-[var(--muted)]">
                  Model: {compareResult.unoptimized.model_used} (
                  {compareResult.unoptimized.latency_ms}ms)
                </div>
              </div>
              <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
                <div className="font-semibold text-[var(--ink)]">Optimized Run</div>
                <div className="mt-1 font-mono text-[var(--ink)]">
                  In: {compareResult.optimized.input_tokens} | Out:{" "}
                  {compareResult.optimized.output_tokens}
                </div>
                <div className="text-[11px] text-[var(--muted)]">
                  Techniques: {compareResult.optimized.methods_used.join(", ") || "none"}
                </div>
              </div>
              <div className="rounded-xl border border-[color:var(--pass-soft)] bg-[var(--pass-soft)] p-3">
                <div className="font-semibold text-[var(--pass)]">Measured Delta</div>
                <div className="mt-1 font-mono text-[var(--ink)]">
                  Saved: {compareResult.measured_diff.input_tokens_saved} input tok (
                  {compareResult.measured_diff.input_reduction_percent}%)
                </div>
                <div className="text-[11px] text-[var(--ink-2)]">
                  Cost diff: ${compareResult.measured_diff.cost_saved_usd.toFixed(6)}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Recent Token Telemetry Table */}
        {recentEntries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Workflow</th>
                  <th>Model</th>
                  <th className="num">Baseline In</th>
                  <th className="num">Actual In</th>
                  <th className="num">Out / Cache</th>
                  <th className="num">Tools / Time</th>
                  <th>Optimizations</th>
                </tr>
              </thead>
              <tbody>
                {recentEntries.slice(0, 12).map((entry) => (
                  <tr key={entry.id}>
                    <td className="font-semibold text-[var(--ink)]">{entry.workflow_name}</td>
                    <td className="font-mono text-xs">{entry.model_id}</td>
                    <td className="num font-mono text-xs dim">
                      {entry.baseline_input_tokens ?? entry.input_tokens}
                    </td>
                    <td className="num font-mono text-xs">{entry.input_tokens}</td>
                    <td className="num font-mono text-xs">
                      {entry.output_tokens} / {entry.cached_tokens}
                    </td>
                    <td className="num font-mono text-xs dim">
                      {entry.tool_calls_count ?? 0} calls &bull; {entry.duration_ms ?? 0}ms
                    </td>
                    <td className="text-xs text-[var(--muted)]">
                      {entry.optimization_enabled === false
                        ? "unoptimized"
                        : (entry.optimization_methods || []).slice(0, 3).join(", ") || "standard"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Live Analytics Report Generator */}
      <form onSubmit={handleRunAnalytics} className="hf-card space-y-4">
        <div className="text-sm font-bold text-[var(--ink)]">Run HR Analytics Report</div>
        <div className="flex flex-wrap gap-2">
          {PRESET_QUERIES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQueryPrompt(q)}
              className="hf-btn hf-btn-sm text-left"
            >
              {q}
            </button>
          ))}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={queryPrompt}
            onChange={(e) => setQueryPrompt(e.target.value)}
            className="hf-input flex-1"
          />
          <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
            <Play className="h-4 w-4" />
            {running ? "Generating..." : "Run Analytics"}
          </button>
        </div>
      </form>

      {charts.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {charts.map((chart, cIdx) => {
            const maxVal = Math.max(1, ...chart.data.map((d) => Number(d.value || 0)));
            return (
              <div key={chart.chart_id || cIdx} className="hf-card">
                <h3 className="text-sm font-bold text-[var(--ink)]">{chart.title}</h3>
                <div className="mt-4 space-y-2.5">
                  {chart.data.map((pt, pIdx) => (
                    <div key={pIdx} className="space-y-1 text-xs">
                      <div className="flex justify-between text-[var(--ink-2)]">
                        <span>{pt.label}</span>
                        <span className="font-mono font-semibold text-[var(--ink)]">{pt.value}</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--field)]">
                        <div
                          className="h-full rounded-full bg-[var(--pass)]"
                          style={{
                            width: `${Math.max(4, Math.round((Number(pt.value || 0) / maxVal) * 100))}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
