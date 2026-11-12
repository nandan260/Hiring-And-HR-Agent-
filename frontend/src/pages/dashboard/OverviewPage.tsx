import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Briefcase,
  CalendarClock,
  CheckCircle2,
  Clock,
  DollarSign,
  FileSearch,
  Lock,
  MessageSquareText,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
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
    <div className="space-y-6">
      <DemoBanner />

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Dashboard — {session.tenantName}
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Unified command overview for HireFlow AI Hiring &amp; HR workflows, candidate pipeline,
            approvals, and monthly token quota.
          </p>
        </div>
        <Link
          to="/dashboard/assistant"
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:from-indigo-500 hover:to-blue-500"
        >
          <MessageSquareText className="h-4 w-4" />
          Open HR Assistant
        </Link>
      </div>

      {/* Live Metrics Grid (9 Real Postgres Analytics KPIs) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Total Jobs</span>
            <Briefcase className="h-4 w-4 text-indigo-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.total_jobs_count ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Active roles across requisitions, JDs &amp; pipelines
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Total Candidates</span>
            <Users className="h-4 w-4 text-blue-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.candidate_count ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {metrics?.kb_document_count ?? 0} indexed knowledge docs
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Resumes Analyzed</span>
            <FileSearch className="h-4 w-4 text-violet-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.resumes_analyzed_count ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Parsed &amp; vector-scored in isolated sandbox
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Interviews Scheduled</span>
            <CalendarClock className="h-4 w-4 text-sky-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.scheduled_interviews_count ?? metrics?.interview_count ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {metrics?.interview_count ?? 0} total interview records
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Pending Onboarding</span>
            <Clock className="h-4 w-4 text-amber-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.pending_onboarding_count ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            of {metrics?.onboarding_count ?? 0} onboarding workflows • {metrics?.pending_hitl_count ?? 0} HITL pending
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Completed Executions</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.completed_executions ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            out of {metrics?.total_executions ?? 0} logged workflow runs
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Failed Executions</span>
            <AlertTriangle className="h-4 w-4 text-rose-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {metrics?.failed_executions ?? 0}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {(metrics?.blocked_executions ?? 0) + (metrics?.rejected_executions ?? 0)} policy blocked / off-domain rejected
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Token Consumption</span>
            <Activity className="h-4 w-4 text-blue-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            {(quota?.tokens_used_this_month ?? 0).toLocaleString()}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            of {(quota?.monthly_token_limit ?? 2000000).toLocaleString()} monthly cap ({quota?.usage_percent ?? 0}%)
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between text-xs font-medium text-slate-500">
            <span>Estimated AI Costs</span>
            <DollarSign className="h-4 w-4 text-teal-600" />
          </div>
          <div className="mt-2 font-display text-2xl font-bold text-slate-900">
            ${(metrics?.estimated_ai_cost_usd ?? 0).toFixed(4)}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Cumulative PostgreSQL token billing telemetry
          </p>
        </div>
      </div>

      {/* Unified Quick Prompt Launcher */}
      <div className="rounded-2xl border border-indigo-200/80 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
          <Sparkles className="h-4 w-4 text-indigo-600" />
          Unified HireFlow AI Prompt Router
        </div>
        <p className="mt-1 text-xs text-slate-600">
          Ask any Hiring or HR question below. HireFlow AI automatically routes your request to the
          right internal HR workflow and blocks off-topic or unauthorized actions.
        </p>

        <form onSubmit={handleQuickRun} className="mt-4 flex flex-col gap-3 sm:flex-row">
          <input
            type="text"
            value={quickPrompt}
            onChange={(e) => setQuickPrompt(e.target.value)}
            placeholder="e.g., How many days of parental leave do full-time employees get? OR Shortlist top Backend Engineer candidates..."
            className="flex-1 rounded-xl border border-slate-200 px-4 py-2.5 text-sm outline-none focus:border-indigo-400"
          />
          <button
            type="submit"
            disabled={running || !quickPrompt.trim()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-60"
          >
            <Send className="h-4 w-4" />
            {running ? "Routing..." : "Execute"}
          </button>
        </form>

        {(quickResult || quickError) && (
          <div className="mt-4">
            <ExecutionResultPanel result={quickResult} errorMsg={quickError} />
          </div>
        )}
      </div>

      {/* All 7 Internal HR Workflow Cards */}
      <div>
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-bold text-slate-900">
            Integrated Hiring &amp; HR Workflows
          </h2>
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            Role: <code className="font-mono font-semibold">{session.role}</code>
          </span>
        </div>

        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {HR_WORKFLOW_CATALOG.map((wf) => {
            const live = wfMap.get(wf.slug);
            const allowed = live ? live.allowed_for_current_role : !wf.requiresAdmin;
            return (
              <Link
                key={wf.slug}
                to={wf.routePath}
                className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-indigo-300 hover:shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-lg bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">
                      {wf.shortLabel}
                    </span>
                    {allowed ? (
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Permitted
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                        <Lock className="h-3 w-3" />
                        Admin / Owner
                      </span>
                    )}
                  </div>
                  <h3 className="mt-3 font-display text-base font-bold text-slate-900">
                    {wf.name}
                  </h3>
                  <p className="mt-1 text-xs leading-relaxed text-slate-600">{wf.description}</p>
                </div>
                <div className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-indigo-600">
                  Open View
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Recent Telemetry Snapshot */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-slate-500" />
            <h2 className="font-display text-base font-bold text-slate-900">
              Recent Agent Executions
            </h2>
          </div>
          <Link to="/dashboard/monitor" className="text-xs font-semibold text-indigo-600 hover:underline">
            View Full Monitor →
          </Link>
        </div>
        {executions.length === 0 ? (
          <p className="mt-3 text-xs text-slate-500">No executions logged yet for this tenant.</p>
        ) : (
          <div className="mt-3 divide-y divide-slate-100">
            {executions.slice(0, 5).map((ex) => (
              <div key={ex.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-xs">
                <div className="min-w-0 flex-1">
                  <span className="font-semibold text-slate-800">{ex.workflow_name}</span>
                  <span className="mx-2 text-slate-300">•</span>
                  <span className="truncate text-slate-600">{ex.prompt_preview}</span>
                </div>
                <div className="flex items-center gap-2 font-mono text-[11px]">
                  <span
                    className={`rounded-full px-2 py-0.5 font-semibold ${
                      ex.status === "completed"
                        ? "bg-emerald-50 text-emerald-700"
                        : ex.status === "paused_hitl"
                          ? "bg-amber-50 text-amber-700"
                          : "bg-rose-50 text-rose-700"
                    }`}
                  >
                    {ex.status}
                  </span>
                  <span className="text-slate-400">{ex.latency_ms}ms</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Operational Links */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          to="/dashboard/knowledge-base"
          className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 hover:border-indigo-300"
        >
          <BookOpen className="h-5 w-5 text-indigo-600" />
          <div>
            <div className="text-sm font-bold text-slate-900">Knowledge Base</div>
            <div className="text-xs text-slate-500">Upload handbooks, rubrics &amp; resumes</div>
          </div>
        </Link>
        <Link
          to="/dashboard/interviews"
          className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 hover:border-indigo-300"
        >
          <CalendarClock className="h-5 w-5 text-blue-600" />
          <div>
            <div className="text-sm font-bold text-slate-900">Interview Management</div>
            <div className="text-xs text-slate-500">Review proposed rounds &amp; HITL invites</div>
          </div>
        </Link>
        <Link
          to="/dashboard/settings"
          className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 hover:border-indigo-300"
        >
          <ShieldCheck className="h-5 w-5 text-emerald-600" />
          <div>
            <div className="text-sm font-bold text-slate-900">Governance &amp; Quota</div>
            <div className="text-xs text-slate-500">RBAC team members, blind mode &amp; limits</div>
          </div>
        </Link>
      </div>
    </div>
  );
};
