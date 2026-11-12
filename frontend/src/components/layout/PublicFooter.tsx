import React from "react";
import { Link } from "react-router-dom";
import { Lock, ShieldCheck } from "lucide-react";

export const PublicFooter: React.FC = () => {
  return (
    <footer className="border-t border-[var(--line)] bg-[var(--panel)] text-[var(--ink-2)]">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5 text-[var(--ink)]">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--field)]">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" />
                  <path d="M8.5 12l2.5 2.5 4.5-5" />
                </svg>
              </div>
              <span className="text-base font-bold tracking-tight">
                HireFlow AI &mdash; Hiring &amp; HR AI Agent
              </span>
            </div>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-[var(--muted)]">
              Specialized enterprise Hiring &amp; HR AI platform powered by LangGraph workflow
              orchestration, tenant-isolated PostgreSQL RLS &amp; pgvector knowledge retrieval,
              role-based access enforcement, and human-in-the-loop sign-off.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="hf-chip hf-chip-plain">
                <Lock className="h-3 w-3" />
                Tenant RLS Isolation
              </span>
              <span className="hf-chip hf-chip-pass">
                <ShieldCheck className="h-3 w-3" />
                RBAC + Monthly Quota
              </span>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--ink)]">
              HR Agent Workspace
            </h4>
            <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
              <li>
                <Link to="/dashboard" className="no-underline hover:text-[var(--ink)]">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/dashboard/assistant" className="no-underline hover:text-[var(--ink)]">
                  HR Assistant
                </Link>
              </li>
              <li>
                <Link to="/dashboard/monitor" className="no-underline hover:text-[var(--ink)]">
                  Execution Monitor
                </Link>
              </li>
              <li>
                <Link to="/signin" className="no-underline hover:text-[var(--ink)]">
                  Sign In / Register Business
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--ink)]">
              Internal HR Workflows
            </h4>
            <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
              <li>
                <Link to="/dashboard/screening" className="no-underline hover:text-[var(--ink)]">
                  Resume Screening
                </Link>
              </li>
              <li>
                <Link to="/dashboard/jd-generator" className="no-underline hover:text-[var(--ink)]">
                  Job Description Generator
                </Link>
              </li>
              <li>
                <Link to="/dashboard/candidates" className="no-underline hover:text-[var(--ink)]">
                  Candidate Shortlisting
                </Link>
              </li>
              <li>
                <Link to="/dashboard/onboarding" className="no-underline hover:text-[var(--ink)]">
                  Onboarding &amp; HR Analytics
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-start justify-between gap-4 border-t border-[var(--line)] pt-6 text-xs text-[var(--muted)] sm:flex-row sm:items-center">
          <p>HireFlow AI &bull; Unified Hiring &amp; HR AI Agent Platform</p>
          <p>FastAPI + PostgreSQL + pgvector + LangGraph</p>
        </div>
      </div>
    </footer>
  );
};
