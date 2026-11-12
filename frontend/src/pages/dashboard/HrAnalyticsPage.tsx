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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">HR Analytics</h1>
          <p className="mt-1 text-sm text-slate-600">
            Live tenant workforce telemetry, workflow token accounting, and sqlglot-validated
            analytics reports.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
          <Database className="h-3.5 w-3.5" />
          Read-Only SQL Validation
        </span>
      </div>

      {/* Live Workspace KPIs */}
      <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Total Executions</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-slate-900">
            {workspace?.metrics.total_executions ?? 0}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Candidates Tracked</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-indigo-700">
            {workspace?.metrics.candidate_count ?? 0}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Tokens Used (Month)</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-slate-900">
            {(usageStats?.tokens_used_this_month ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Remaining Quota</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-emerald-700">
            {(usageStats?.remaining_tokens ?? 0).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Token Breakdown by Workflow */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Token Consumption by HR Workflow
          </h2>
        </div>

        {byWf.length === 0 ? (
          <p className="mt-3 text-xs text-slate-500">No token usage recorded yet this month.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {byWf.map((row) => (
              <div key={row.workflow_slug} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800">
                    {row.workflow_name} ({row.runs} runs)
                  </span>
                  <span className="font-mono text-slate-600">
                    {row.total_tokens.toLocaleString()} tok • ${row.estimated_cost_usd.toFixed(4)}
                  </span>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-600"
                    style={{ width: `${Math.max(4, Math.round((row.total_tokens / maxWfTokens) * 100))}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Measured Optimization Telemetry & Real A/B Comparison */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Gauge className="h-4 w-4 text-indigo-600" />
            <h2 className="font-display text-base font-bold text-slate-900">
              Measured Token Optimization &amp; Cost Telemetry
            </h2>
          </div>
          <span className="text-xs text-slate-500">
            Real logged counters across {optSum?.total_runs_measured ?? 0} measured execution(s)
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="text-[11px] font-medium text-slate-500">Unoptimized Baseline Input</div>
            <div className="mt-1 font-display text-lg font-bold text-slate-900">
              {(optSum?.total_baseline_input_tokens ?? 0).toLocaleString()} tok
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="text-[11px] font-medium text-slate-500">Actual Sent Input Tokens</div>
            <div className="mt-1 font-display text-lg font-bold text-indigo-700">
              {(optSum?.total_actual_input_tokens ?? 0).toLocaleString()} tok
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="text-[11px] font-medium text-slate-500">Measured Reduction</div>
            <div className="mt-1 font-display text-lg font-bold text-emerald-700">
              {(optSum?.total_measured_tokens_saved ?? 0).toLocaleString()} tok (
              {optSum?.measured_reduction_percent ?? 0}%)
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="text-[11px] font-medium text-slate-500">Total Estimated Cost</div>
            <div className="mt-1 font-display text-lg font-bold text-slate-900">
              ${(optSum?.total_estimated_cost_usd ?? 0).toFixed(4)}
            </div>
          </div>
        </div>

        {/* Side-by-Side Real Comparison Benchmark */}
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 space-y-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-900">
            <Sparkles className="h-3.5 w-3.5 text-indigo-600" />
            Live Unoptimized vs. Optimized Comparison (Measured A/B Run)
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              value={comparePrompt}
              onChange={(e) => setComparePrompt(e.target.value)}
              className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-indigo-400"
            />
            <button
              type="button"
              onClick={handleRunComparison}
              disabled={comparing}
              className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
            >
              {comparing ? "Benchmarking..." : "Run A/B Benchmark"}
            </button>
          </div>
          {compareErr && (
            <p className="text-xs font-medium text-rose-700">{compareErr}</p>
          )}
          {compareResult && (
            <div className="grid gap-3 pt-1 sm:grid-cols-3 text-xs">
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="font-semibold text-slate-600">Unoptimized Run</div>
                <div className="mt-1 font-mono text-slate-900">
                  In: {compareResult.unoptimized.input_tokens} | Out: {compareResult.unoptimized.output_tokens}
                </div>
                <div className="text-[11px] text-slate-500">
                  Model: {compareResult.unoptimized.model_used} ({compareResult.unoptimized.latency_ms}ms)
                </div>
              </div>
              <div className="rounded-lg border border-indigo-200 bg-white p-3">
                <div className="font-semibold text-indigo-700">Optimized Run</div>
                <div className="mt-1 font-mono text-slate-900">
                  In: {compareResult.optimized.input_tokens} | Out: {compareResult.optimized.output_tokens}
                </div>
                <div className="text-[11px] text-slate-500">
                  Techniques: {compareResult.optimized.methods_used.join(", ") || "none"}
                </div>
              </div>
              <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-3">
                <div className="font-semibold text-emerald-800">Measured Delta</div>
                <div className="mt-1 font-mono text-emerald-900">
                  Saved: {compareResult.measured_diff.input_tokens_saved} input tok (
                  {compareResult.measured_diff.input_reduction_percent}%)
                </div>
                <div className="text-[11px] text-emerald-700">
                  Cost diff: ${compareResult.measured_diff.cost_saved_usd.toFixed(6)}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Recent Token Telemetry Table */}
        {recentEntries.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Workflow</th>
                  <th className="py-2 pr-3">Model</th>
                  <th className="py-2 pr-3">Baseline In</th>
                  <th className="py-2 pr-3">Actual In</th>
                  <th className="py-2 pr-3">Out / Cache</th>
                  <th className="py-2 pr-3">Tools / Time</th>
                  <th className="py-2">Optimizations</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recentEntries.slice(0, 12).map((entry) => (
                  <tr key={entry.id}>
                    <td className="py-2 pr-3 font-medium text-slate-800">{entry.workflow_name}</td>
                    <td className="py-2 pr-3 font-mono text-[11px] text-slate-600">{entry.model_id}</td>
                    <td className="py-2 pr-3 font-mono text-slate-500">
                      {entry.baseline_input_tokens ?? entry.input_tokens}
                    </td>
                    <td className="py-2 pr-3 font-mono font-semibold text-indigo-700">
                      {entry.input_tokens}
                    </td>
                    <td className="py-2 pr-3 font-mono text-slate-600">
                      {entry.output_tokens} / {entry.cached_tokens}
                    </td>
                    <td className="py-2 pr-3 font-mono text-slate-500">
                      {entry.tool_calls_count ?? 0} calls • {entry.duration_ms ?? 0}ms
                    </td>
                    <td className="py-2 text-[11px] text-slate-600">
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
      <form
        onSubmit={handleRunAnalytics}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="text-sm font-bold text-slate-900">Run HR Analytics Report</div>
        <div className="flex flex-wrap gap-2">
          {PRESET_QUERIES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => setQueryPrompt(q)}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 hover:border-indigo-300"
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
            className="flex-1 rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400"
          />
          <button
            type="submit"
            disabled={running}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
          >
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
              <div
                key={chart.chart_id || cIdx}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"
              >
                <h3 className="font-display text-sm font-bold text-slate-900">{chart.title}</h3>
                <div className="mt-4 space-y-2.5">
                  {chart.data.map((pt, pIdx) => (
                    <div key={pIdx} className="space-y-1 text-xs">
                      <div className="flex justify-between text-slate-700">
                        <span>{pt.label}</span>
                        <span className="font-mono font-semibold">{pt.value}</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-blue-600"
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
