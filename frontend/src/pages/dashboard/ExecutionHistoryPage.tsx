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
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Agent Execution Monitor</h1>
          <p className="hf-lede">
            Real-time task telemetry, isolated sandbox runtimes, browser safety checks, tool calls,
            HITL approvals, and token usage.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {usageStats && (
            <span className="hf-chip hf-chip-plain font-mono">
              {usageStats.tokens_used_this_month.toLocaleString()} /{" "}
              {usageStats.monthly_token_limit.toLocaleString()} tok (
              {usageStats.remaining_tokens.toLocaleString()} left)
            </span>
          )}
          <button
            type="button"
            onClick={handleRefreshNow}
            disabled={refreshing}
            className="hf-btn hf-btn-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Telemetry
          </button>
        </div>
      </div>

      {/* Live Telemetry Summary Strip */}
      <div className="hf-stats">
        <div className="hf-stat border-b-0">
          <div className="flex items-center justify-between gap-2">
            <span className="hf-stat-k">Current Task</span>
            <span className={`hf-chip ${activeRuns.length > 0 ? "hf-chip-pass" : "hf-chip-plain"}`}>
              {activeRuns.length > 0 ? `${activeRuns.length} running` : "Last completed"}
            </span>
          </div>
          <p className="mt-2 line-clamp-2 text-xs font-semibold text-[var(--ink)]">
            {monitorSnapshot?.current_task || "No executions recorded yet"}
          </p>
        </div>

        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Current Workflow</div>
          <p className="mt-1.5 font-mono text-sm font-bold text-[var(--ink)]">
            {monitorSnapshot?.current_workflow || "none"}
          </p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            MCP connected: {monitorSnapshot?.mcp_summary?.connected_approved_servers ?? 0} /{" "}
            {monitorSnapshot?.mcp_summary?.total_servers ?? 0} servers
          </p>
        </div>

        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Sandbox Isolation Mode</div>
          <p className="mt-1.5 text-xs font-bold text-[var(--ink)]">
            {runtimesInfo?.docker_available
              ? "Docker Container (--network=none)"
              : "Development Fallback (Subprocess)"}
          </p>
          <p className="mt-1 truncate text-xs text-[var(--muted)]">
            {activeRuntimes.length} active runtime(s) for tenant
          </p>
        </div>

        <div className="hf-stat border-b-0 border-r-0">
          <div className="hf-stat-k">Cumulative Token Telemetry</div>
          <p className="mt-1.5 text-lg font-bold text-[var(--ink)] tabular-nums">
            {(monitorSnapshot?.token_summary?.total_tokens ?? 0).toLocaleString()} tok
          </p>
          <p className="mt-1 font-mono text-xs text-[var(--muted)]">
            Est. Cost: ${(monitorSnapshot?.token_summary?.estimated_cost_usd ?? 0).toFixed(4)}
          </p>
        </div>
      </div>

      {/* Sandbox Runtime Lifecycle Manager */}
      <div className="hf-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-[var(--muted)]" />
              <h2 className="hf-h2 mb-0">
                Tenant Sandbox Runtime Environments ({activeRuntimes.length})
              </h2>
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {runtimesInfo?.isolation_notice ||
                "Each tenant has an isolated workspace directory, CPU/memory bounds, and timeout guardrails."}
            </p>
          </div>
          {canManageRuntimes && (
            <button
              type="button"
              disabled={busyRuntimeId === "create"}
              onClick={handleCreateRuntime}
              className="hf-btn hf-btn-primary hf-btn-sm"
            >
              <Play className="h-3.5 w-3.5" />
              {busyRuntimeId === "create" ? "Provisioning..." : "Create Runtime"}
            </button>
          )}
        </div>

        {activeRuntimes.length === 0 ? (
          <div className="hf-empty py-8">
            <strong>No sandbox runtimes provisioned</strong>
            Create one above or run any sandboxed HR task.
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {activeRuntimes.map((rt) => (
              <div key={rt.id} className="hf-subcard text-xs">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono font-bold text-[var(--ink)]">
                        {rt.agent_runtime_id}
                      </span>
                      <span
                        className={`hf-chip ${
                          rt.status === "running" ? "hf-chip-pass" : "hf-chip-plain"
                        }`}
                      >
                        {rt.status}
                      </span>
                      <span
                        className={`hf-chip ${
                          rt.is_container_isolated ? "hf-chip-pass" : "hf-chip-escalate"
                        }`}
                      >
                        {rt.is_container_isolated
                          ? "docker (non-root, --network=none)"
                          : "development_fallback (NOT container isolated)"}
                      </span>
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-3 font-mono text-[11px] text-[var(--muted)]">
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
                          className="hf-btn hf-btn-primary hf-btn-sm"
                        >
                          <Play className="h-3 w-3" /> Start
                        </button>
                      )}
                      {rt.status === "running" && (
                        <button
                          type="button"
                          disabled={busyRuntimeId === rt.id}
                          onClick={() => handleRuntimeAction(rt.id, "stop")}
                          className="hf-btn hf-btn-sm"
                        >
                          <Square className="h-3 w-3" /> Stop
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busyRuntimeId === rt.id}
                        onClick={() => handleRuntimeAction(rt.id, "restart")}
                        className="hf-btn hf-btn-sm"
                      >
                        <RotateCcw className="h-3 w-3" /> Restart
                      </button>
                      <button
                        type="button"
                        disabled={busyRuntimeId === rt.id}
                        onClick={() => handleDestroyRuntime(rt.id)}
                        className="hf-btn hf-btn-danger hf-btn-sm"
                      >
                        <Trash2 className="h-3 w-3" /> Destroy
                      </button>
                    </div>
                  )}
                </div>

                {rt.execution_logs && rt.execution_logs.length > 0 && (
                  <div className="mt-3 space-y-1 border-t border-[var(--line)] pt-2">
                    {rt.execution_logs.slice(-3).map((lg, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between gap-2 font-mono text-[10.5px] text-[var(--ink-2)]"
                      >
                        <span className="truncate">
                          [{lg.event}] {lg.detail}
                        </span>
                        <span className="shrink-0 text-[var(--muted)]">{lg.duration_ms}ms</span>
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
      <div className="hf-card">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-[var(--esc)]" />
          <h2 className="hf-h2 mb-0">
            Human-in-the-Loop Approval Queue ({pendingApprovals.length} pending /{" "}
            {approvals.length} total)
          </h2>
        </div>

        {approvals.length === 0 ? (
          <div className="hf-empty py-8">
            <strong>No approval requests queued</strong>
            Drafted calendar invites, shortlists, or onboarding actions will appear here.
          </div>
        ) : (
          <div className="hf-queue mt-4">
            {approvals.slice(0, 10).map((ap) => (
              <div
                key={ap.id}
                className="hf-q-item flex flex-wrap items-center justify-between gap-3 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold text-[var(--ink)]">{ap.title}</span>
                    <span
                      className={`hf-chip ${
                        ap.status === "approved"
                          ? "hf-chip-pass"
                          : ap.status === "rejected"
                            ? "hf-chip-block"
                            : "hf-chip-escalate"
                      }`}
                    >
                      {ap.status}
                    </span>
                    <span className="font-mono text-[11px] text-[var(--muted)]">
                      {ap.agent_slug} &bull; {ap.action_type}
                    </span>
                  </div>
                  <p className="mt-1.5 text-[var(--ink-2)]">{ap.summary}</p>
                </div>

                {ap.status === "pending" && (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        resolveHitlApproval(ap.id, "approved", "Approved in Execution Monitor")
                      }
                      className="hf-btn hf-btn-primary hf-btn-sm"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        resolveHitlApproval(ap.id, "rejected", "Rejected in Execution Monitor")
                      }
                      className="hf-btn hf-btn-danger hf-btn-sm"
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
      <div className="hf-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-[var(--pass)]" />
            <h2 className="hf-h2 mb-0">Execution Trace Logs ({filteredExecs.length})</h2>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            <select
              value={workflowFilter}
              onChange={(e) => setWorkflowFilter(e.target.value)}
              className="hf-input w-auto rounded-full py-1.5 text-xs"
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
              className="hf-input w-auto rounded-full py-1.5 text-xs"
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
          <div className="hf-empty py-8">
            <strong>No matching executions</strong>
            No execution logs match the active filters.
          </div>
        ) : (
          <div className="mt-4 space-y-2.5">
            {filteredExecs.map((ex) => {
              const isOpen = expandedId === ex.id;
              const toolCalls = ex.tool_calls || [];
              const browserInfo = ex.browser_activity;
              const sandboxInfo = ex.sandbox_status;
              const tokInfo = ex.token_usage;
              return (
                <div key={ex.id} className="hf-subcard p-4 text-xs">
                  <button
                    type="button"
                    onClick={() => setExpandedId(isOpen ? null : ex.id)}
                    className="flex w-full flex-wrap items-center justify-between gap-2 text-left"
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 shrink-0 text-[var(--muted)]" />
                      ) : (
                        <ChevronRight className="h-4 w-4 shrink-0 text-[var(--muted)]" />
                      )}
                      <span className="hf-chip hf-chip-plain">{ex.workflow_name}</span>
                      <span className="truncate font-medium text-[var(--ink)]">
                        {ex.prompt_preview}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      <span
                        className={`hf-chip ${
                          ex.status === "completed"
                            ? "hf-chip-pass"
                            : ex.status === "paused_hitl"
                              ? "hf-chip-escalate"
                              : "hf-chip-block"
                        }`}
                      >
                        {ex.status} ({ex.classifier_result})
                      </span>
                      <span className="text-[var(--muted)]">{ex.latency_ms}ms</span>
                    </div>
                  </button>

                  {isOpen && (
                    <div className="mt-3 space-y-3 border-t border-[var(--line)] pt-3">
                      <div className="flex flex-wrap gap-4 text-[11px] text-[var(--ink-2)]">
                        <span>
                          <strong className="text-[var(--ink)]">Model:</strong> {ex.model_tier_used}
                        </span>
                        <span>
                          <strong className="text-[var(--ink)]">Tokens:</strong>{" "}
                          {tokInfo?.total_tokens ?? 0} (in: {tokInfo?.input_tokens ?? 0}, out:{" "}
                          {tokInfo?.output_tokens ?? 0})
                        </span>
                        <span>
                          <strong className="text-[var(--ink)]">Sandbox:</strong>{" "}
                          {sandboxInfo?.backend_mode && sandboxInfo.backend_mode !== "none"
                            ? `${sandboxInfo.backend_mode} (${sandboxInfo.status})`
                            : "not used"}
                        </span>
                        <span>
                          <strong className="text-[var(--ink)]">Browser:</strong>{" "}
                          {browserInfo?.status || "not_used"}
                        </span>
                        <span>
                          <strong className="text-[var(--ink)]">Timestamp:</strong>{" "}
                          {new Date(ex.created_at).toLocaleString()}
                        </span>
                      </div>

                      {toolCalls.length > 0 && (
                        <div>
                          <div className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold text-[var(--ink)]">
                            <Wrench className="h-3 w-3 text-[var(--pass)]" />
                            Real Tool Calls ({toolCalls.length})
                          </div>
                          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
                            {toolCalls.map((tc, i) => (
                              <div
                                key={i}
                                className="rounded-lg border border-[var(--line)] bg-[var(--panel)] px-2.5 py-1.5 text-[11px]"
                              >
                                <div className="flex items-center justify-between gap-2 font-mono">
                                  <span className="truncate font-semibold text-[var(--ink)]">
                                    {tc.tool}
                                  </span>
                                  <span
                                    style={{
                                      color:
                                        tc.status === "completed" || tc.status === "ok"
                                          ? "var(--pass)"
                                          : "var(--block)",
                                    }}
                                  >
                                    {tc.status} ({tc.duration_ms}ms)
                                  </span>
                                </div>
                                {tc.error && (
                                  <p className="mt-1 text-[10px] text-[var(--block)]">
                                    {tc.error}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {browserInfo && browserInfo.status !== "not_used" && (
                        <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3 text-[11px]">
                          <div className="flex items-center gap-1.5 font-semibold text-[var(--ink)]">
                            <Globe className="h-3.5 w-3.5 text-[var(--pass)]" />
                            Browser Activity: {browserInfo.status}
                          </div>
                          {browserInfo.visited_urls && browserInfo.visited_urls.length > 0 && (
                            <p className="mt-1 font-mono text-[10.5px] text-[var(--ink-2)]">
                              URLs: {browserInfo.visited_urls.join(", ")}
                            </p>
                          )}
                          {browserInfo.blocked_requests &&
                            browserInfo.blocked_requests.length > 0 && (
                              <p className="mt-1 font-mono text-[10.5px] text-[var(--block)]">
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
                              className="flex items-center justify-between rounded-lg border border-[var(--line)] bg-[var(--panel)] px-2.5 py-1.5 text-[11px]"
                            >
                              <span className="flex items-center gap-1 font-mono font-semibold text-[var(--ink)]">
                                {st.status === "blocked" || st.status === "rejected" ? (
                                  <ShieldAlert className="h-3 w-3 text-[var(--block)]" />
                                ) : null}
                                {st.step}
                              </span>
                              <span className="truncate px-2 text-[var(--muted)]">{st.detail}</span>
                              <span className="font-mono text-[var(--muted)]">
                                {st.duration_ms}ms
                              </span>
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
