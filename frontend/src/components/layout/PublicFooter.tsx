import React from "react";
import { Link } from "react-router-dom";
import { Bot, Lock, ShieldCheck } from "lucide-react";

export const PublicFooter: React.FC = () => {
  return (
    <footer className="border-t border-slate-200 bg-slate-950 text-slate-300">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white">
                <Bot className="h-4 w-4" />
              </div>
              <span className="font-display text-base font-bold text-white">
                HireFlow AI — Hiring &amp; HR AI Agent
              </span>
            </div>
            <p className="mt-3 max-w-md text-sm leading-relaxed text-slate-400">
              Specialized enterprise Hiring &amp; HR AI platform powered by LangGraph workflow
              orchestration, tenant-isolated PostgreSQL RLS &amp; pgvector knowledge retrieval,
              role-based access enforcement, and human-in-the-loop sign-off.
            </p>
            <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-400">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900 px-3 py-1">
                <Lock className="h-3.5 w-3.5 text-indigo-400" />
                Tenant RLS Isolation
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900 px-3 py-1">
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                RBAC + Monthly Quota Enforcement
              </span>
            </div>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              HR Agent Workspace
            </h4>
            <ul className="mt-3 space-y-2 text-sm text-slate-400">
              <li>
                <Link to="/dashboard" className="hover:text-white">
                  Dashboard
                </Link>
              </li>
              <li>
                <Link to="/dashboard/assistant" className="hover:text-white">
                  HR Assistant
                </Link>
              </li>
              <li>
                <Link to="/dashboard/monitor" className="hover:text-white">
                  Execution Monitor
                </Link>
              </li>
              <li>
                <Link to="/signin" className="hover:text-white">
                  Sign In / Register Business
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Internal HR Workflows
            </h4>
            <ul className="mt-3 space-y-2 text-sm text-slate-400">
              <li>
                <Link to="/dashboard/screening" className="hover:text-white">
                  Resume Screening
                </Link>
              </li>
              <li>
                <Link to="/dashboard/jd-generator" className="hover:text-white">
                  Job Description Generator
                </Link>
              </li>
              <li>
                <Link to="/dashboard/candidates" className="hover:text-white">
                  Candidate Shortlisting
                </Link>
              </li>
              <li>
                <Link to="/dashboard/onboarding" className="hover:text-white">
                  Onboarding &amp; HR Analytics
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 flex flex-col items-start justify-between gap-4 border-t border-slate-800/80 pt-6 text-xs text-slate-500 sm:flex-row sm:items-center">
          <p>HireFlow AI • Unified Hiring &amp; HR AI Agent Platform</p>
          <p>FastAPI + PostgreSQL + pgvector + LangGraph</p>
        </div>
      </div>
    </footer>
  );
};
