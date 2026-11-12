import React, { useState } from "react";
import { Badge } from "../../components/common/Badge";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { UnifiedExecutionRecord } from "../../types/agent";

export const ExecutionHistoryPage: React.FC = () => {
  const {
    executions,
    approvals,
    resolveHitlApproval,
    monitorSnapshot,
    runtimesInfo,
    refreshRuntimeData,
    setLastActionError,
  } = useApp();

  const [tab, setTab] = useState<"traces" | "approvals" | "sandboxes">("traces");
  const [selected, setSelected] = useState<UnifiedExecutionRecord | null>(null);
  const [runtimeBusy, setRuntimeBusy] = useState<string | null>(null);

  const pendingApprovals = approvals.filter((a) => a.status === "pending");
  const runtimes = runtimesInfo?.runtimes || [];
  const activeExecution = selected || executions[0] || null;
  const monitorRuns = monitorSnapshot?.executions || [];

  const handleCreateRuntime = async () => {
    setRuntimeBusy("create");
    try {
      await apiClient.createRuntime({ auto_start: true });
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to create sandbox.");
    } finally {
      setRuntimeBusy(null);
    }
  };

  const handleRuntimeAction = async (runtimeId: string, action: "start" | "stop" | "restart") => {
    setRuntimeBusy(`${runtimeId}-${action}`);
    try {
      await apiClient.performRuntimeAction(runtimeId, action);
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : `Failed to ${action} sandbox.`);
    } finally {
      setRuntimeBusy(null);
    }
  };

  const handleDestroyRuntime = async (runtimeId: string) => {
    setRuntimeBusy(`${runtimeId}-destroy`);
    try {
      await apiClient.destroyRuntime(runtimeId);
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to destroy sandbox.");
    } finally {
      setRuntimeBusy(null);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <div className="flex items-center gap-2.5">
          <h1 className="hf-h1">Execution Monitor</h1>
          <span className="hf-chip hf-chip-plain font-mono">
            {runtimesInfo?.docker_available ? "Docker" : "Process Sandbox"}
          </span>
        </div>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("traces")}
            className={`hf-tab ${tab === "traces" ? "active" : ""}`}
          >
            Traces ({executions.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("approvals")}
            className={`hf-tab ${tab === "approvals" ? "active" : ""}`}
          >
            Approvals ({pendingApprovals.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("sandboxes")}
            className={`hf-tab ${tab === "sandboxes" ? "active" : ""}`}
          >
            Sandboxes ({runtimes.length})
          </button>
        </div>
      </div>

      {tab === "traces" && (
        <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
          <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-7">
            {executions.length === 0 ? (
              <div className="hf-empty my-auto">No executions recorded.</div>
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
                    {executions.map((ex) => {
                      const isSel = activeExecution?.id === ex.id;
                      const tok =
                        ex.token_usage?.total_tokens ??
                        (ex.token_usage?.input_tokens ?? 0) + (ex.token_usage?.output_tokens ?? 0);
                      return (
                        <tr
                          key={ex.id}
                          onClick={() => setSelected(ex)}
                          className={`cursor-pointer ${isSel ? "bg-[var(--surface-hover)]" : ""}`}
                        >
                          <td className="font-medium text-[var(--fg)]">{ex.workflow_slug}</td>
                          <td>
                            <Badge
                              variant={
                                ex.status === "completed"
                                  ? "emerald"
                                  : ex.status === "paused_hitl"
                                    ? "amber"
                                    : "rose"
                              }
                            >
                              {ex.status}
                            </Badge>
                          </td>
                          <td className="font-mono text-xs text-[var(--muted)]">
                            {ex.model_tier_used}
                          </td>
                          <td className="num">{tok}</td>
                          <td className="num text-[var(--muted)]">{ex.latency_ms}ms</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 overflow-y-auto lg:col-span-5">
            {!activeExecution ? (
              <div className="hf-empty my-auto">Select a trace to inspect.</div>
            ) : (
              <>
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                  <span className="font-mono text-xs font-semibold text-[var(--fg)]">
                    {activeExecution.workflow_slug}
                  </span>
                  <span className="font-mono text-xs text-[var(--muted)]">
                    {activeExecution.classifier_result}
                  </span>
                </div>
                <div className="hf-subcard text-xs">
                  <div className="font-semibold text-[var(--muted)]">Prompt</div>
                  <div className="mt-1 whitespace-pre-wrap text-[var(--fg)]">
                    {activeExecution.prompt_preview}
                  </div>
                </div>
                {activeExecution.steps_json?.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                      Workflow Steps
                    </div>
                    {activeExecution.steps_json.map((st, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between rounded-[var(--r-field)] border border-[var(--border)] px-2.5 py-1 text-[11px]"
                      >
                        <span className="font-mono text-[var(--fg)]">{st.step}</span>
                        <span className="truncate px-2 text-[var(--muted)]">{st.detail}</span>
                        <span className="font-mono text-[var(--muted)]">{st.duration_ms}ms</span>
                      </div>
                    ))}
                  </div>
                )}
                {monitorRuns.length > 0 && (
                  <div className="space-y-1">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--muted)]">
                      Live Telemetry
                    </div>
                    {monitorRuns.slice(0, 5).map((run) => (
                      <div
                        key={run.id}
                        className="flex items-center justify-between rounded-[var(--r-field)] border border-[var(--border)] px-2.5 py-1 text-[11px]"
                      >
                        <span className="font-mono text-[var(--fg)]">{run.current_workflow}</span>
                        <span className="font-mono text-[var(--muted)]">
                          {run.execution_duration_ms}ms
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {tab === "approvals" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col overflow-y-auto">
          {approvals.length === 0 ? (
            <div className="hf-empty my-auto">No HITL approval requests.</div>
          ) : (
            <div className="space-y-2">
              {approvals.map((ap) => (
                <div key={ap.id} className="hf-subcard flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-[var(--fg)]">{ap.title}</span>
                      <Badge variant={ap.status === "pending" ? "amber" : "slate"}>
                        {ap.status}
                      </Badge>
                    </div>
                    <div className="mt-0.5 text-xs text-[var(--muted)]">{ap.summary}</div>
                  </div>
                  {ap.status === "pending" && (
                    <div className="flex shrink-0 gap-1.5">
                      <button
                        type="button"
                        onClick={() => resolveHitlApproval(ap.id, "approved", "Approved")}
                        className="hf-btn hf-btn-primary hf-btn-sm"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => resolveHitlApproval(ap.id, "rejected", "Rejected")}
                        className="hf-btn hf-btn-sm"
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "sandboxes" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col gap-3">
          <div className="flex flex-none items-center justify-between">
            <span className="text-xs text-[var(--muted)]">
              {runtimesInfo?.isolation_notice || "Isolated sandbox runtimes"}
            </span>
            <button
              type="button"
              onClick={handleCreateRuntime}
              disabled={runtimeBusy === "create"}
              className="hf-btn hf-btn-primary hf-btn-sm"
            >
              {runtimeBusy === "create" ? "Creating..." : "Create Sandbox"}
            </button>
          </div>
          {runtimes.length === 0 ? (
            <div className="hf-empty my-auto">No active sandboxes.</div>
          ) : (
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
              {runtimes.map((rt) => (
                <div
                  key={rt.id}
                  className="hf-subcard flex flex-wrap items-center justify-between gap-2"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-[var(--fg)]">
                        {rt.agent_runtime_id}
                      </span>
                      <Badge variant={rt.status === "running" ? "emerald" : "slate"}>
                        {rt.status}
                      </Badge>
                    </div>
                    <div className="mt-0.5 font-mono text-[11px] text-[var(--muted)]">
                      CPU {rt.cpu_limit} / RAM {rt.memory_limit_mb}MB / {rt.backend_mode}
                    </div>
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => handleRuntimeAction(rt.id, "start")}
                      disabled={Boolean(runtimeBusy)}
                      className="hf-btn hf-btn-sm"
                    >
                      Start
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRuntimeAction(rt.id, "stop")}
                      disabled={Boolean(runtimeBusy)}
                      className="hf-btn hf-btn-sm"
                    >
                      Stop
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRuntimeAction(rt.id, "restart")}
                      disabled={Boolean(runtimeBusy)}
                      className="hf-btn hf-btn-sm"
                    >
                      Restart
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDestroyRuntime(rt.id)}
                      disabled={Boolean(runtimeBusy)}
                      className="hf-btn hf-btn-danger hf-btn-sm"
                    >
                      Destroy
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
