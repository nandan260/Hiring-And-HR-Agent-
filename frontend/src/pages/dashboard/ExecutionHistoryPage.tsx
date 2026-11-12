import React, { useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  Globe,
  Play,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  Square,
  Trash2,
  Wrench,
  XCircle,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import { HR_WORKFLOW_CATALOG } from "../../data/catalogData";
import { apiClient } from "../../services/apiClient";

export const ExecutionHistoryPage: React.FC = () => {
  const {
    executions,
    approvals,
    usageStats,
    resolveHitlApproval,
    monitorSnapshot,
    runtimesInfo,
    refreshRuntimeData,
    refreshWorkspaceData,
    session,
    setLastActionError,
  } = useApp();

  const [workflowFilter, setWorkflowFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busyRuntimeId, setBusyRuntimeId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const canManageRuntimes =
    session.role === "business_owner" ||
    session.role === "business_admin" ||
    session.role === "platform_admin";

  useEffect(() => {
    refreshRuntimeData();
  }, [refreshRuntimeData]);

  const handleRefreshNow = async () => {
    setRefreshing(true);
    await Promise.all([refreshWorkspaceData(), refreshRuntimeData()]);
    setRefreshing(false);
  };

  const handleCreateRuntime = async () => {
    setBusyRuntimeId("create");
    try {
      await apiClient.createRuntime({ auto_start: true });
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to create sandbox runtime");
    } finally {
      setBusyRuntimeId(null);
    }
  };

  const handleRuntimeAction = async (runtimeId: string, action: "start" | "stop" | "restart") => {
    setBusyRuntimeId(runtimeId);
    try {
      await apiClient.performRuntimeAction(runtimeId, action);
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : `Failed to ${action} runtime`);
    } finally {
      setBusyRuntimeId(null);
    }
  };

  const handleDestroyRuntime = async (runtimeId: string) => {
    setBusyRuntimeId(runtimeId);
    try {
      await apiClient.destroyRuntime(runtimeId);
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to destroy runtime");
    } finally {
      setBusyRuntimeId(null);
    }
  };

  const pendingApprovals = approvals.filter((a) => a.status === "pending");
  const filteredExecs = executions.filter((ex) => {
    if (workflowFilter !== "all" && ex.workflow_slug !== workflowFilter) return false;
    if (statusFilter !== "all" && ex.status !== statusFilter) return false;
    return true;
  });

  const activeRuns = monitorSnapshot?.active_runs || [];
  const activeRuntimes = (runtimesInfo?.runtimes || []).filter((r) => r.status !== "destroyed");

  return (
    <div className="space-y-6">
      {/* Header & Quota */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Agent Execution Monitor
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Real-time task telemetry, isolated sandbox runtimes, browser safety checks, tool calls,
            HITL approvals, and token usage.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {usageStats && (
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs">
              <span className="text-slate-500">Monthly Quota: </span>
              <strong className="font-mono text-slate-900">
                {usageStats.tokens_used_this_month.toLocaleString()} /{" "}
                {usageStats.monthly_token_limit.toLocaleString()}
              </strong>{" "}
              <span className="text-emerald-700">
                ({usageStats.remaining_tokens.toLocaleString()} left)
              </span>
            </div>
          )}
          <button
            type="button"
            onClick={handleRefreshNow}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {/* Live Telemetry Summary Strip */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Current Task</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                activeRuns.length > 0
                  ? "bg-indigo-100 text-indigo-700"
                  : "bg-slate-100 text-slate-600"
              }`}
            >
              {activeRuns.length > 0 ? `${activeRuns.length} running` : "Last completed"}
            </span>
          </div>
          <p className="mt-1.5 line-clamp-2 text-xs font-semibold text-slate-900">
            {monitorSnapshot?.current_task || "No executions recorded yet"}
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-xs text-slate-500">Current Workflow</div>
          <p className="mt-1.5 font-mono text-xs font-bold text-indigo-700">
            {monitorSnapshot?.current_workflow || "none"}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            MCP connected: {monitorSnapshot?.mcp_summary?.connected_approved_servers ?? 0} /{" "}
            {monitorSnapshot?.mcp_summary?.total_servers ?? 0} servers
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-xs text-slate-500">Sandbox Isolation Mode</div>
          <p className="mt-1.5 text-xs font-bold text-slate-900">
            {runtimesInfo?.docker_available
              ? "Docker Container (--network=none)"
              : "Development Fallback (Subprocess)"}
          </p>
          <p className="mt-1 truncate text-[11px] text-slate-500">
            {activeRuntimes.length} active runtime(s) for tenant
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <div className="text-xs text-slate-500">Cumulative Token Telemetry</div>
          <p className="mt-1.5 font-mono text-sm font-bold text-slate-900">
            {(monitorSnapshot?.token_summary?.total_tokens ?? 0).toLocaleString()} tokens
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            Est. Cost: ${(monitorSnapshot?.token_summary?.estimated_cost_usd ?? 0).toFixed(4)}
          </p>
        </div>
      </div>

      {/* Sandbox Runtime Lifecycle Manager */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-indigo-600" />
              <h2 className="font-display text-base font-bold text-slate-900">
                Tenant Sandbox Runtime Environments ({activeRuntimes.length})
              </h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {runtimesInfo?.isolation_notice ||
                "Each tenant has an isolated workspace directory, CPU/memory bounds, and timeout guardrails."}
            </p>
          </div>
          {canManageRuntimes && (
            <button
              type="button"
              disabled={busyRuntimeId === "create"}
              onClick={handleCreateRuntime}
              className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
            >
              <Play className="h-3.5 w-3.5" />
              {busyRuntimeId === "create" ? "Provisioning..." : "Create Runtime"}
            </button>
          )}
        </div>

        {activeRuntimes.length === 0 ? (
          <p className="mt-4 text-xs text-slate-500">
            No tenant sandbox runtime provisioned yet. Create one above or run any sandboxed HR task.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {activeRuntimes.map((rt) => (
              <div
                key={rt.id}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono font-bold text-slate-900">
                        {rt.agent_runtime_id}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          rt.status === "running"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-slate-200 text-slate-700"
                        }`}
                      >
                        {rt.status}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          rt.is_container_isolated
                            ? "bg-indigo-50 text-indigo-700"
                            : "bg-amber-100 text-amber-900"
                        }`}
                      >
                        {rt.is_container_isolated
                          ? "docker (non-root, --network=none)"
                          : "development_fallback (NOT container isolated)"}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-3 font-mono text-[11px] text-slate-500">
                      <span>CPU: {rt.cpu_limit} cores</span>
                      <span>Memory: {rt.memory_limit_mb} MB</span>
                      <span>Timeout: {rt.timeout_seconds}s</span>
                      <span>Network: {rt.network_mode}</span>
                    </div>
                  </div>

                  {canManageRuntimes && (
                    <div className="flex flex-wrap gap-1.5">
                      {rt.status !== "running" && (
                        <button
                          type="button"
                          disabled={busyRuntimeId === rt.id}
                          onClick={() => handleRuntimeAction(rt.id, "start")}
                          className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                        >
                          <Play className="h-3 w-3" /> Start
                        </button>
                      )}
                      {rt.status === "running" && (
                        <button
                          type="button"
                          disabled={busyRuntimeId === rt.id}
                          onClick={() => handleRuntimeAction(rt.id, "stop")}
                          className="inline-flex items-center gap-1 rounded-lg bg-amber-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-amber-500 disabled:opacity-50"
                        >
                          <Square className="h-3 w-3" /> Stop
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busyRuntimeId === rt.id}
                        onClick={() => handleRuntimeAction(rt.id, "restart")}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                      >
                        <RotateCcw className="h-3 w-3" /> Restart
                      </button>
                      <button
                        type="button"
                        disabled={busyRuntimeId === rt.id}
                        onClick={() => handleDestroyRuntime(rt.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                      >
                        <Trash2 className="h-3 w-3" /> Destroy
                      </button>
                    </div>
                  )}
                </div>

                {rt.execution_logs && rt.execution_logs.length > 0 && (
                  <div className="mt-3 space-y-1 border-t border-slate-200 pt-2">
                    {rt.execution_logs.slice(-3).map((lg, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between gap-2 font-mono text-[10px] text-slate-600"
                      >
                        <span className="truncate">
                          [{lg.event}] {lg.detail}
                        </span>
                        <span className="shrink-0 text-slate-400">{lg.duration_ms}ms</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* HITL Queue */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-amber-600" />
            <h2 className="font-display text-base font-bold text-slate-900">
              Human-in-the-Loop Approval Queue ({pendingApprovals.length} pending / {approvals.length} total)
            </h2>
          </div>
        </div>

        {approvals.length === 0 ? (
          <p className="mt-3 text-xs text-slate-500">No HITL approval items logged yet.</p>
        ) : (
          <div className="mt-4 space-y-2.5">
            {approvals.slice(0, 10).map((ap) => (
              <div
                key={ap.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-900">{ap.title}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        ap.status === "approved"
                          ? "bg-emerald-50 text-emerald-700"
                          : ap.status === "rejected"
                            ? "bg-rose-50 text-rose-700"
                            : "bg-amber-100 text-amber-900"
                      }`}
                    >
                      {ap.status}
                    </span>
                    <span className="font-mono text-[10px] text-slate-500">
                      {ap.agent_slug} • {ap.action_type}
                    </span>
                  </div>
                  <p className="mt-1 text-slate-600">{ap.summary}</p>
                </div>

                {ap.status === "pending" && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => resolveHitlApproval(ap.id, "approved", "Approved in Execution Monitor")}
                      className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-500"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => resolveHitlApproval(ap.id, "rejected", "Rejected in Execution Monitor")}
                      className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 font-semibold text-rose-700 hover:bg-rose-100"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Execution Logs & Telemetry Breakdown */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-indigo-600" />
            <h2 className="font-display text-base font-bold text-slate-900">
              Execution Trace Logs ({filteredExecs.length})
            </h2>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            <select
              value={workflowFilter}
              onChange={(e) => setWorkflowFilter(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-1.5 outline-none focus:border-indigo-400"
            >
              <option value="all">All Workflows</option>
              {HR_WORKFLOW_CATALOG.map((w) => (
                <option key={w.slug} value={w.slug}>
                  {w.name}
                </option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-xl border border-slate-200 px-3 py-1.5 outline-none focus:border-indigo-400"
            >
              <option value="all">All Statuses</option>
              <option value="completed">completed</option>
              <option value="paused_hitl">paused_hitl</option>
              <option value="rejected">rejected</option>
              <option value="blocked">blocked</option>
            </select>
          </div>
        </div>

        {filteredExecs.length === 0 ? (
          <p className="mt-4 text-xs text-slate-500">No execution logs match the active filters.</p>
        ) : (
          <div className="mt-4 space-y-2.5">
            {filteredExecs.map((ex) => {
              const isOpen = expandedId === ex.id;
              const toolCalls = ex.tool_calls || [];
              const browserInfo = ex.browser_activity;
              const sandboxInfo = ex.sandbox_status;
              const tokInfo = ex.token_usage;
              return (
                <div
                  key={ex.id}
                  className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 text-xs"
                >
                  <button
                    type="button"
                    onClick={() => setExpandedId(isOpen ? null : ex.id)}
                    className="flex w-full flex-wrap items-center justify-between gap-2 text-left"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 shrink-0 text-slate-400" />
                      )}
                      <span className="rounded bg-indigo-50 px-2 py-0.5 font-semibold text-indigo-700">
                        {ex.workflow_name}
                      </span>
                      <span className="truncate font-medium text-slate-800">
                        {ex.prompt_preview}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      <span
                        className={`rounded-full px-2 py-0.5 font-semibold ${
                          ex.status === "completed"
                            ? "bg-emerald-50 text-emerald-700"
                            : ex.status === "paused_hitl"
                              ? "bg-amber-50 text-amber-800"
                              : "bg-rose-50 text-rose-700"
                        }`}
                      >
                        {ex.status} ({ex.classifier_result})
                      </span>
                      <span className="text-slate-500">{ex.latency_ms}ms</span>
                    </div>
                  </button>

                  {isOpen && (
                    <div className="mt-3 space-y-3 border-t border-slate-200 pt-3">
                      <div className="flex flex-wrap gap-3 text-[11px] text-slate-600">
                        <span>
                          <strong>Model:</strong> {ex.model_tier_used}
                        </span>
                        <span>
                          <strong>Tokens:</strong> {tokInfo?.total_tokens ?? 0} (in:{" "}
                          {tokInfo?.input_tokens ?? 0}, out: {tokInfo?.output_tokens ?? 0})
                        </span>
                        <span>
                          <strong>Sandbox:</strong>{" "}
                          {sandboxInfo?.backend_mode && sandboxInfo.backend_mode !== "none"
                            ? `${sandboxInfo.backend_mode} (${sandboxInfo.status})`
                            : "not used"}
                        </span>
                        <span>
                          <strong>Browser:</strong> {browserInfo?.status || "not_used"}
                        </span>
                        <span>
                          <strong>Timestamp:</strong> {new Date(ex.created_at).toLocaleString()}
                        </span>
                      </div>

                      {toolCalls.length > 0 && (
                        <div>
                          <div className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-700">
                            <Wrench className="h-3 w-3 text-indigo-600" />
                            Real Tool Calls ({toolCalls.length})
                          </div>
                          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                            {toolCalls.map((tc, i) => (
                              <div
                                key={i}
                                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px]"
                              >
                                <div className="flex items-center justify-between gap-2 font-mono">
                                  <span className="truncate font-semibold text-slate-800">
                                    {tc.tool}
                                  </span>
                                  <span
                                    className={
                                      tc.status === "completed" || tc.status === "ok"
                                        ? "text-emerald-700"
                                        : "text-rose-700"
                                    }
                                  >
                                    {tc.status} ({tc.duration_ms}ms)
                                  </span>
                                </div>
                                {tc.error && (
                                  <p className="mt-1 text-[10px] text-rose-600">{tc.error}</p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {browserInfo && browserInfo.status !== "not_used" && (
                        <div className="rounded-lg border border-indigo-200 bg-indigo-50/50 p-2.5 text-[11px]">
                          <div className="flex items-center gap-1.5 font-semibold text-indigo-900">
                            <Globe className="h-3.5 w-3.5" />
                            Browser Activity: {browserInfo.status}
                          </div>
                          {browserInfo.visited_urls && browserInfo.visited_urls.length > 0 && (
                            <p className="mt-1 font-mono text-[10px] text-slate-700">
                              URLs: {browserInfo.visited_urls.join(", ")}
                            </p>
                          )}
                          {browserInfo.blocked_requests && browserInfo.blocked_requests.length > 0 && (
                            <p className="mt-1 font-mono text-[10px] text-rose-700">
                              Blocked SSRF/Redirects:{" "}
                              {browserInfo.blocked_requests.map((b) => b.reason).join("; ")}
                            </p>
                          )}
                        </div>
                      )}

                      {ex.steps_json.length > 0 && (
                        <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                          {ex.steps_json.map((st, idx) => (
                            <div
                              key={idx}
                              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px]"
                            >
                              <span className="flex items-center gap-1 font-mono font-semibold text-slate-800">
                                {st.status === "blocked" || st.status === "rejected" ? (
                                  <ShieldAlert className="h-3 w-3 text-rose-600" />
                                ) : null}
                                {st.step}
                              </span>
                              <span className="truncate px-2 text-slate-500">{st.detail}</span>
                              <span className="font-mono text-slate-400">{st.duration_ms}ms</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
