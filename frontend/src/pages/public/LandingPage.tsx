import React from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  Briefcase,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  Lock,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
} from "lucide-react";
import { PublicNavbar } from "../../components/layout/PublicNavbar";
import { PublicFooter } from "../../components/layout/PublicFooter";
import { DemoBanner } from "../../components/common/DemoBanner";
import { useApp } from "../../context/AppContext";

const WORKFLOW_CARDS = [
  {
    icon: FileText,
    title: "Resume Screening",
    desc: "Extract skills and experience from uploaded PDF/DOCX/TXT resumes, apply custom rubrics, and enforce optional blind PII screening.",
    route: "/dashboard/screening",
  },
  {
    icon: Briefcase,
    title: "Job Description Generator",
    desc: "Draft role-aligned job descriptions grounded in company leveling guides with automated inclusive language linting.",
    route: "/dashboard/jd-generator",
  },
  {
    icon: Users,
    title: "Candidate Shortlisting",
    desc: "Rank applicants on skills and experience with transparent missing-skill analysis, anti-bias guardrails, and HITL approval.",
    route: "/dashboard/candidates",
  },
  {
    icon: CalendarClock,
    title: "Interview Management",
    desc: "Detect interviewer schedule conflicts, propose interview slots, and draft calendar invitations pending human approval.",
    route: "/dashboard/interviews",
  },
  {
    icon: UserCheck,
    title: "Employee Onboarding",
    desc: "Track KYC documents, generate 30/60/90-day onboarding checklists, and gate IT/team provisioning behind human sign-off.",
    route: "/dashboard/onboarding",
  },
  {
    icon: MessageSquareText,
    title: "HR Policy Assistant",
    desc: "Answer PTO, parental leave, travel, and benefits queries with tenant-isolated pgvector citations and role access filters.",
    route: "/dashboard/assistant",
  },
  {
    icon: BarChart3,
    title: "HR Analytics",
    desc: "Run sqlglot-validated read-only queries for hiring funnel conversion, candidate match scores, and monthly token budgets.",
    route: "/dashboard/analytics",
  },
];

export const LandingPage: React.FC = () => {
  const { session } = useApp();

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <PublicNavbar />

      {/* Hero Section */}
      <section className="relative overflow-hidden border-b border-slate-200 bg-gradient-to-b from-slate-950 via-slate-900 to-indigo-950 py-16 text-white sm:py-24">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(79,70,229,0.28),transparent_55%)]" />
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 max-w-3xl">
            <DemoBanner compact />
          </div>

          <div className="grid items-center gap-12 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <div className="inline-flex items-center gap-2 rounded-full border border-indigo-400/30 bg-indigo-500/15 px-3.5 py-1.5 text-xs font-medium text-indigo-200">
                <Sparkles className="h-3.5 w-3.5 text-indigo-300" />
                HireFlow AI • Specialized Hiring &amp; HR AI Agent
              </div>

              <h1 className="mt-5 font-display text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-[3.25rem] lg:leading-[1.08]">
                One Intelligent Hiring &amp; HR AI Agent Across Every People Workflow.
              </h1>

              <p className="mt-5 max-w-2xl text-base leading-relaxed text-slate-300 sm:text-lg">
                Automate resume screening, inclusive job descriptions, merit shortlisting, interview
                scheduling, employee onboarding, policy Q&amp;A, and HR analytics in one unified,
                tenant-isolated LangGraph workspace.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3.5">
                <Link
                  to={session.isLiveAuthenticated ? "/dashboard" : "/signin"}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-500 to-blue-500 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:from-indigo-400 hover:to-blue-400"
                >
                  {session.isLiveAuthenticated ? "Open HR Workspace" : "Sign In to Workspace"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <a
                  href="#capabilities"
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/70 px-5 py-3.5 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
                >
                  Explore 7 HR Workflows
                </a>
              </div>
            </div>

            <div className="lg:col-span-5">
              <div className="rounded-2xl border border-slate-700/80 bg-slate-900/90 p-6 shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-white">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-white">Unified HireFlow Router</div>
                      <div className="text-[11px] text-slate-400">
                        POST /api/v1/hr-agent/execute
                      </div>
                    </div>
                  </div>
                  <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-medium text-emerald-300">
                    Active
                  </span>
                </div>

                <div className="mt-4 space-y-2.5 text-xs">
                  {[
                    "Cross-HR internal routing across 7 workflows",
                    "Strict non-HR rejection (medical, finance, legal)",
                    "Role-based access (employee vs HR admin/owner)",
                    "Concurrency-safe monthly token quota lock",
                    "Human-in-the-Loop gates for invites & provisioning",
                  ].map((item) => (
                    <div
                      key={item}
                      className="flex items-center gap-2.5 rounded-xl border border-slate-800 bg-slate-950/70 px-3.5 py-2.5 text-slate-200"
                    >
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 7 Capabilities Section */}
      <section id="capabilities" className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-2xl">
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-600">
            Unified Capabilities
          </span>
          <h2 className="mt-1 font-display text-2xl font-bold text-slate-900 sm:text-3xl">
            Seven Specialized HR Workflows Inside One Agent
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Send any Hiring or HR request to the HR Assistant or launch a focused operational module
            directly from your dashboard.
          </p>
        </div>

        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {WORKFLOW_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <Link
                key={card.title}
                to={session.isLiveAuthenticated ? card.route : "/signin"}
                className="group rounded-2xl border border-slate-200 bg-white p-6 shadow-xs transition hover:-translate-y-0.5 hover:border-indigo-300 hover:shadow-md"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 transition group-hover:bg-indigo-600 group-hover:text-white">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 font-display text-base font-bold text-slate-900">
                  {card.title}
                </h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{card.desc}</p>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Architecture & Security */}
      <section id="architecture" className="border-t border-slate-200 bg-white py-16">
        <div id="security" className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-600">
              Enterprise Controls
            </span>
            <h2 className="mt-1 font-display text-2xl font-bold text-slate-900 sm:text-3xl">
              Production Multi-Tenancy, RBAC &amp; Auditability
            </h2>
          </div>

          <div className="mt-8 grid gap-6 md:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <Database className="h-5 w-5 text-indigo-600" />
              <h3 className="mt-3 text-sm font-bold text-slate-900">PostgreSQL RLS + pgvector</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Every candidate, interview, document chunk, and audit record enforces strict
                tenant_id isolation via Row-Level Security policies.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <Lock className="h-5 w-5 text-blue-600" />
              <h3 className="mt-3 text-sm font-bold text-slate-900">Workflow-Scoped RBAC</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Employees can query HR policies self-service, while screening, shortlisting,
                scheduling, onboarding, and analytics require Admin/Owner privileges.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <ClipboardCheck className="h-5 w-5 text-emerald-600" />
              <h3 className="mt-3 text-sm font-bold text-slate-900">Human-in-the-Loop Gates</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Calendar invites, shortlists, IT provisioning, and team allocations pause for
                explicit human sign-off in the approval queue.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <Activity className="h-5 w-5 text-amber-600" />
              <h3 className="mt-3 text-sm font-bold text-slate-900">Quota &amp; Execution Trace</h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                Concurrency-safe monthly_token_quota locks prevent budget overruns while logging
                every LangGraph node timing and tool invocation.
              </p>
            </div>
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-indigo-200 bg-indigo-50/70 p-6">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-7 w-7 shrink-0 text-indigo-600" />
              <div>
                <h3 className="font-display text-base font-bold text-slate-900">
                  Ready to run HireFlow AI with real tenant isolation?
                </h3>
                <p className="text-xs text-slate-600">
                  Sign in with a demo organization owner/employee account or register your business.
                </p>
              </div>
            </div>
            <Link
              to="/signin"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500"
            >
              Sign In / Get Started
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <PublicFooter />
    </div>
  );
};
