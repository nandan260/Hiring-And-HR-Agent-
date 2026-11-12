import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BookOpen,
  CalendarClock,
  Lock,
  MessageSquareText,
  Send,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import { DemoBanner } from "../../components/common/DemoBanner";
import { HR_WORKFLOW_CATALOG } from "../../data/catalogData";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const OverviewPage: React.FC = () => {
  const { workspace, executeWorkflow, session, executions } = useApp();
  const [quickPrompt, setQuickPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [quickResult, setQuickResult] = useState<UnifiedExecuteResponse | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);

  const metrics = workspace?.metrics;
  const quota = workspace?.quota;
  const wfMap = new Map((workspace?.workflows || []).map((w) => [w.slug, w]));

  const completed = metrics?.completed_executions ?? 0;
  const hitl = metrics?.pending_hitl_count ?? 0;
  const failedOrBlocked =
    (metrics?.failed_executions ?? 0) +
    (metrics?.blocked_executions ?? 0) +
    (metrics?.rejected_executions ?? 0);
  const totalExecSplit = Math.max(1, completed + hitl + failedOrBlocked);

  const handleQuickRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickPrompt.trim()) return;
    setRunning(true);
    setQuickError(null);
    setQuickResult(null);
    const res = await executeWorkflow({ prompt: quickPrompt.trim() });
    setRunning(false);
    if (!res.ok) {
      setQuickError(res.error || "Request failed");
    } else if (res.data) {
      setQuickResult(res.data);
    }
  };

  return (
    <div className="space-y-8">
      <DemoBanner compact />

      {/* Centered Hero Greeting (Reference Pattern) */}
      <div className="hf-hello">
        <h1>Dashboard &mdash; {session.tenantName}</h1>
        <p>
          Unified command overview for HireFlow AI Hiring &amp; HR workflows, candidate pipeline,
          approvals, and monthly token quota.
        </p>
        <div className="hf-quick">
          <Link to="/dashboard/screening" className="hf-btn">
            Screen a resume
          </Link>
          <Link to="/dashboard/jd-generator" className="hf-btn">
            Generate job description
          </Link>
          <Link to="/dashboard/assistant" className="hf-btn hf-btn-primary">
            <MessageSquareText className="h-4 w-4" />
            Open HR Assistant
          </Link>
          <Link to="/dashboard/monitor" className="hf-btn">
            Review execution trace
          </Link>
        </div>
      </div>

      {/* Unified Quick Prompt Composer */}
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2 px-1">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
            <Sparkles className="h-3.5 w-3.5 text-[var(--pass)]" />
            Unified HireFlow AI Prompt Router
          </div>
          <span className="font-mono text-[11px] text-[var(--muted)]">
            /api/v1/hr-agent/execute
          </span>
        </div>

        <form onSubmit={handleQuickRun} className="hf-composer">
          <textarea
            rows={2}
            value={quickPrompt}
            onChange={(e) => setQuickPrompt(e.target.value)}
            placeholder="Ask any Hiring or HR question (e.g. How many days of paid parental leave do we offer? / Screen candidates for Senior Backend Engineer)..."
            className="!min-h-[68px]"
          />
          <div className="hf-composer-row">
            <button
              type="button"
              onClick={() =>
                setQuickPrompt("How many days of paid parental leave and PTO do employees receive?")
              }
              className="hf-btn hf-btn-sm"
            >
              Policy Example
            </button>
            <button
              type="button"
              onClick={() =>
                setQuickPrompt(
                  "Draft an inclusive Job Description for Senior Backend Engineer requiring Python and FastAPI."
                )
              }
              className="hf-btn hf-btn-sm"
            >
              JD Example
            </button>
            <div className="flex-1" />
            <button
              type="submit"
              disabled={running || !quickPrompt.trim()}
              className="hf-send"
              aria-label={running ? "Routing request" : "Run prompt"}
              title={running ? "Routing..." : "Run prompt"}
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>

        {(quickResult || quickError) && (
          <ExecutionResultPanel result={quickResult} errorMsg={quickError} />
        )}
      </div>

      {/* Segmented Real PostgreSQL Analytics KPIs (All 9 Required Metrics) */}
      <div>
        <div className="mb-3 flex items-center justify-between px-1">
          <h2 className="hf-h2 mb-0">Workspace Telemetry</h2>
          <span className="font-mono text-xs text-[var(--muted)]">Live PostgreSQL Aggregates</span>
        </div>
        <div className="grid overflow-hidden rounded-[16px] border border-[var(--line)] bg-[var(--panel)] sm:grid-cols-2 lg:grid-cols-3 [&>.hf-stat]:sm:odd:border-r [&>.hf-stat]:sm:even:border-r-0 [&>.hf-stat]:lg:border-r [&>.hf-stat:nth-child(3n)]:lg:border-r-0 [&>.hf-stat:nth-last-child(-n+3)]:lg:border-b-0 [&>.hf-stat:nth-last-child(-n+2)]:sm:border-b-0 [&>.hf-stat:last-child]:border-b-0">
          <div className="hf-stat">
            <div className="hf-stat-k">Total Jobs</div>
            <div className="hf-stat-v">{metrics?.total_jobs_count ?? 0}</div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Active roles across requisitions, JDs &amp; pipelines
            </p>
          </div>

          <div className="hf-stat">
            <div className="hf-stat-k">Total Candidates</div>
            <div className="hf-stat-v">{metrics?.candidate_count ?? 0}</div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {metrics?.kb_document_count ?? 0} indexed knowledge docs
            </p>
          </div>

          <div className="hf-stat">
            <div className="hf-stat-k">Resumes Analyzed</div>
            <div className="hf-stat-v">{metrics?.resumes_analyzed_count ?? 0}</div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Parsed &amp; vector-scored in isolated sandbox
            </p>
          </div>

          <div className="hf-stat">
            <div className="hf-stat-k">Interviews Scheduled</div>
            <div className="hf-stat-v">
              {metrics?.scheduled_interviews_count ?? metrics?.interview_count ?? 0}
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {metrics?.interview_count ?? 0} total interview records
            </p>
          </div>

          <div className="hf-stat">
            <div className="hf-stat-k">Pending Onboarding</div>
            <div className="hf-stat-v">{metrics?.pending_onboarding_count ?? 0}</div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              of {metrics?.onboarding_count ?? 0} onboarding workflows &bull;{" "}
              {metrics?.pending_hitl_count ?? 0} HITL pending
            </p>
          </div>

          <div className="hf-stat">
            <div className="hf-stat-k">Completed Executions</div>
            <div className="hf-stat-v">
              {completed} <small>/ {metrics?.total_executions ?? 0}</small>
            </div>
            <div className="hf-split" aria-hidden="true">
              <i
                style={{
                  width: `${(completed / totalExecSplit) * 100}%`,
                  background: "var(--pass)",
                }}
              />
              <i
                style={{
                  width: `${(hitl / totalExecSplit) * 100}%`,
                  background: "var(--esc)",
                }}
              />
              <i
                style={{
                  width: `${(failedOrBlocked / totalExecSplit) * 100}%`,
                  background: "var(--block)",
                }}
              />
            </div>
          </div>

          <div className="hf-stat lg:border-b-0">
            <div className="hf-stat-k">Failed Executions</div>
            <div className="hf-stat-v">{metrics?.failed_executions ?? 0}</div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {(metrics?.blocked_executions ?? 0) + (metrics?.rejected_executions ?? 0)} policy
              blocked / off-domain rejected
            </p>
          </div>

          <div className="hf-stat lg:border-b-0">
            <div className="hf-stat-k">Token Consumption</div>
            <div className="hf-stat-v">
              {(quota?.tokens_used_this_month ?? 0).toLocaleString()}
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              of {(quota?.monthly_token_limit ?? 2000000).toLocaleString()} monthly cap (
              {quota?.usage_percent ?? 0}%)
            </p>
          </div>

          <div className="hf-stat border-b-0 border-r-0">
            <div className="hf-stat-k">Estimated AI Costs</div>
            <div className="hf-stat-v">${(metrics?.estimated_ai_cost_usd ?? 0).toFixed(4)}</div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Cumulative PostgreSQL token billing telemetry
            </p>
          </div>
        </div>
      </div>

      {/* 7 Internal HR Workflows */}
      <div>
        <div className="mb-3 flex items-center justify-between px-1">
          <h2 className="hf-h2 mb-0">Internal HR Agent Workflows (7)</h2>
          <span className="text-xs text-[var(--muted)]">
            Role: <code className="font-mono font-semibold text-[var(--ink)]">{session.role}</code>
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {HR_WORKFLOW_CATALOG.map((wf) => {
            const live = wfMap.get(wf.slug);
            const allowed = live ? live.allowed_for_current_role : !wf.requiresAdmin;
            return (
              <Link
                key={wf.slug}
                to={wf.routePath}
                className="hf-card group flex flex-col justify-between no-underline transition hover:border-[var(--muted)]"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-[var(--ink)]">{wf.name}</span>
                    {allowed ? (
                      <span className="hf-chip hf-chip-pass">Ready</span>
                    ) : (
                      <span className="hf-chip hf-chip-plain">
                        <Lock className="h-3 w-3" />
                        Admin
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
                    {wf.description}
                  </p>
                </div>
                <div className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-[var(--ink-2)] group-hover:text-[var(--ink)]">
                  Open {wf.shortLabel}
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Recent Workflow Executions (Quiet Rows Table) */}
      <div className="hf-card">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-[var(--muted)]" />
            <h2 className="hf-h2 mb-0">Recent Agent Executions</h2>
          </div>
          <Link to="/dashboard/monitor" className="hf-btn hf-btn-sm">
            View Full Trace &rarr;
          </Link>
        </div>

        {executions.length === 0 ? (
          <div className="hf-empty">
            <strong>No workflow executions yet</strong>
            Run a prompt above or open any workflow to view traces here.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Workflow</th>
                  <th>Prompt</th>
                  <th>Status</th>
                  <th className="num">Latency</th>
                </tr>
              </thead>
              <tbody>
                {executions.slice(0, 5).map((ex) => (
                  <tr key={ex.id}>
                    <td className="font-semibold text-[var(--ink)]">{ex.workflow_name}</td>
                    <td className="max-w-md truncate">{ex.prompt_preview}</td>
                    <td>
                      <span
                        className={`hf-chip ${
                          ex.status === "completed"
                            ? "hf-chip-pass"
                            : ex.status === "paused_hitl"
                              ? "hf-chip-escalate"
                              : "hf-chip-block"
                        }`}
                      >
                        {ex.status}
                      </span>
                    </td>
                    <td className="num font-mono text-xs">{ex.latency_ms}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Quick Operational Links */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Link
          to="/dashboard/knowledge-base"
          className="hf-card flex items-center gap-3 no-underline transition hover:border-[var(--muted)]"
        >
          <BookOpen className="h-5 w-5 text-[var(--ink)]" />
          <div>
            <div className="text-sm font-bold text-[var(--ink)]">Knowledge Base</div>
            <div className="text-xs text-[var(--muted)]">
              Upload handbooks, rubrics &amp; resumes
            </div>
          </div>
        </Link>
        <Link
          to="/dashboard/interviews"
          className="hf-card flex items-center gap-3 no-underline transition hover:border-[var(--muted)]"
        >
          <CalendarClock className="h-5 w-5 text-[var(--esc)]" />
          <div>
            <div className="text-sm font-bold text-[var(--ink)]">Interview Management</div>
            <div className="text-xs text-[var(--muted)]">
              Review proposed rounds &amp; HITL invites
            </div>
          </div>
        </Link>
        <Link
          to="/dashboard/settings"
          className="hf-card flex items-center gap-3 no-underline transition hover:border-[var(--muted)]"
        >
          <ShieldCheck className="h-5 w-5 text-[var(--pass)]" />
          <div>
            <div className="text-sm font-bold text-[var(--ink)]">Governance &amp; Quota</div>
            <div className="text-xs text-[var(--muted)]">
              RBAC team members, blind mode &amp; limits
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
};
