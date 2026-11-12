import React from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  Briefcase,
  CalendarClock,
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
    <div className="flex min-h-screen flex-col bg-[var(--canvas)] text-[var(--ink)]">
      <PublicNavbar />

      <div className="mx-auto w-full max-w-6xl px-4 pt-5 sm:px-6 lg:px-8">
        <DemoBanner />
      </div>

      {/* Hero Section */}
      <section className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6 lg:px-8 lg:py-16">
        <div className="rounded-[22px] border border-[var(--line)] bg-[var(--panel)] p-8 sm:p-12">
          <div className="grid items-center gap-10 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <span className="hf-chip hf-chip-plain">
                <Sparkles className="h-3.5 w-3.5 text-[var(--pass)]" />
                HireFlow AI &mdash; Hiring &amp; HR AI Agent Platform
              </span>

              <h1 className="mt-5 text-4xl font-bold tracking-tight text-[var(--ink)] sm:text-5xl sm:leading-[1.12]">
                One Specialized <span className="text-[var(--pass)]">Hiring &amp; HR</span> AI
                Agent for Your Entire People Team
              </h1>

              <p className="mt-5 max-w-2xl text-base leading-relaxed text-[var(--ink-2)]">
                Unify resume screening, inclusive JD drafting, candidate shortlisting, interview
                scheduling, employee onboarding, policy RAG support, and SQL-backed HR analytics
                inside one multi-tenant workspace secured by PostgreSQL Row-Level Security.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link
                  to={session.isLiveAuthenticated ? "/dashboard" : "/signin"}
                  className="hf-btn hf-btn-primary h-11 px-6"
                >
                  {session.isLiveAuthenticated ? "Open HR Dashboard" : "Sign In to HR Workspace"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <a href="#capabilities" className="hf-btn h-11 px-6">
                  Explore 7 HR Workflows
                </a>
              </div>

              <div className="mt-8 grid grid-cols-3 gap-4 border-t border-[var(--line)] pt-6 text-xs">
                <div>
                  <div className="text-xl font-bold tracking-tight text-[var(--ink)] tabular-nums">
                    7 Workflows
                  </div>
                  <div className="text-[var(--muted)]">Unified LangGraph Agent</div>
                </div>
                <div>
                  <div className="text-xl font-bold tracking-tight text-[var(--ink)] tabular-nums">
                    pgvector + RLS
                  </div>
                  <div className="text-[var(--muted)]">Strict Tenant Isolation</div>
                </div>
                <div>
                  <div className="text-xl font-bold tracking-tight text-[var(--ink)] tabular-nums">
                    HITL Gated
                  </div>
                  <div className="text-[var(--muted)]">Human-Approved Actions</div>
                </div>
              </div>
            </div>

            <div className="lg:col-span-5">
              <div className="rounded-2xl border border-[var(--line)] bg-[var(--field)] p-6">
                <div className="flex items-center justify-between border-b border-[var(--line)] pb-4">
                  <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--panel)] text-[var(--ink)]">
                      <Bot className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-[var(--ink)]">
                        Unified HR Orchestrator
                      </div>
                      <div className="font-mono text-[11px] text-[var(--muted)]">
                        /api/v1/hr-agent/execute
                      </div>
                    </div>
                  </div>
                  <span className="hf-chip hf-chip-pass">Active</span>
                </div>

                <div className="mt-4 space-y-2.5 text-xs">
                  <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="font-semibold text-[var(--ink)]">1. Domain &amp; Safety Gate</div>
                    <p className="mt-1 text-[var(--muted)]">
                      Classifies HR intents and blocks off-domain topics or prompt injection before
                      any DB or LLM call runs.
                    </p>
                  </div>
                  <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="font-semibold text-[var(--ink)]">
                      2. Scoped Internal Workflow Router
                    </div>
                    <p className="mt-1 text-[var(--muted)]">
                      Dispatches cleanly across Screening, JD, Shortlisting, Interviews,
                      Onboarding, Policies, or Analytics.
                    </p>
                  </div>
                  <div className="rounded-xl border border-[var(--line)] bg-[var(--panel)] p-3">
                    <div className="font-semibold text-[var(--ink)]">
                      3. Grounded Citations &amp; HITL Sign-Off
                    </div>
                    <p className="mt-1 text-[var(--muted)]">
                      Attaches handbook/resume sources and pauses interview invites or provisioning
                      pending manager approval.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Capabilities Section */}
      <section id="capabilities" className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
              Internal Capabilities
            </div>
            <h2 className="mt-1.5 text-3xl font-bold tracking-tight text-[var(--ink)]">
              Seven Specialized HR Workflows, One Agent
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
              Access workflows directly from dedicated operational views or route natural-language
              prompts automatically through the unified assistant.
            </p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {WORKFLOW_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <Link
                key={card.title}
                to={card.route}
                className="hf-card group flex flex-col justify-between no-underline transition hover:border-[var(--muted)]"
              >
                <div>
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--field)] text-[var(--ink)]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="mt-4 text-base font-bold text-[var(--ink)]">{card.title}</h3>
                  <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">{card.desc}</p>
                </div>
                <div className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--ink-2)] group-hover:text-[var(--ink)]">
                  Open Workflow
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Architecture & Security */}
      <section id="architecture" className="mx-auto w-full max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
        <div id="security" className="hf-card p-8 sm:p-10">
          <div className="mb-8">
            <div className="text-xs font-semibold uppercase tracking-wider text-[var(--pass)]">
              Enterprise Security &amp; Governance
            </div>
            <h2 className="mt-1.5 text-2xl font-bold tracking-tight text-[var(--ink)] sm:text-3xl">
              Production Architecture Built for People Data
            </h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="hf-subcard">
              <Database className="h-5 w-5 text-[var(--ink)]" />
              <h3 className="mt-3 text-sm font-bold text-[var(--ink)]">PostgreSQL RLS</h3>
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                Row-Level Security policies bound to transaction-local tenant IDs prevent
                cross-company data leakage.
              </p>
            </div>
            <div className="hf-subcard">
              <Lock className="h-5 w-5 text-[var(--ink)]" />
              <h3 className="mt-3 text-sm font-bold text-[var(--ink)]">RBAC &amp; Quotas</h3>
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                Employees only access approved policy docs while recruitment &amp; analytics remain
                restricted to HR Admins &amp; Owners.
              </p>
            </div>
            <div className="hf-subcard">
              <ClipboardCheck className="h-5 w-5 text-[var(--esc)]" />
              <h3 className="mt-3 text-sm font-bold text-[var(--ink)]">Human-in-the-Loop</h3>
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                Calendar invitations, candidate shortlists, and onboarding provisioning stay in
                draft until explicitly approved.
              </p>
            </div>
            <div className="hf-subcard">
              <Activity className="h-5 w-5 text-[var(--pass)]" />
              <h3 className="mt-3 text-sm font-bold text-[var(--ink)]">Full Execution Audit</h3>
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                Every workflow run logs LangGraph node traces, browser activity, token counts, and
                decision audit trails.
              </p>
            </div>
          </div>

          <div className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--line)] bg-[var(--field)] p-6">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-7 w-7 shrink-0 text-[var(--pass)]" />
              <div>
                <h3 className="text-base font-bold text-[var(--ink)]">
                  Ready to run HireFlow AI with real tenant isolation?
                </h3>
                <p className="text-xs text-[var(--muted)]">
                  Sign in with a demo organization owner/employee account or register your business.
                </p>
              </div>
            </div>
            <Link to="/signin" className="hf-btn hf-btn-primary">
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
