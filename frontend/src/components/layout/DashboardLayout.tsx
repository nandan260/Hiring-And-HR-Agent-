import React, { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  Briefcase,
  Building2,
  CalendarClock,
  CheckCircle2,
  FileSearch,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  Plug,
  Settings,
  ShieldCheck,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import { useApp } from "../../context/AppContext";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  end?: boolean;
  badge?: number;
}

export const DashboardLayout: React.FC = () => {
  const {
    session,
    workspace,
    approvals,
    backendStatus,
    signOut,
    lastActionError,
    clearLastActionError,
  } = useApp();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const navigate = useNavigate();

  const pendingApprovals = approvals.filter((a) => a.status === "pending").length;

  const navItems: NavItem[] = [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/dashboard/recruitment", label: "Recruitment", icon: Briefcase },
    { to: "/dashboard/screening", label: "Resume Screening", icon: FileSearch },
    { to: "/dashboard/candidates", label: "Candidates", icon: Users },
    { to: "/dashboard/jd-generator", label: "Job Description Generator", icon: FileText },
    { to: "/dashboard/interviews", label: "Interview Management", icon: CalendarClock },
    { to: "/dashboard/onboarding", label: "Employee Onboarding", icon: UserCheck },
    { to: "/dashboard/assistant", label: "HR Assistant", icon: MessageSquareText },
    { to: "/dashboard/analytics", label: "HR Analytics", icon: BarChart3 },
    {
      to: "/dashboard/monitor",
      label: "Agent Execution Monitor",
      icon: Activity,
      badge: pendingApprovals || undefined,
    },
    { to: "/dashboard/knowledge-base", label: "Knowledge Base", icon: BookOpen },
    { to: "/dashboard/integrations", label: "Tools and Integrations", icon: Plug },
    { to: "/dashboard/settings", label: "Settings", icon: Settings },
  ];

  const quota = workspace?.quota;

  const handleSignOut = () => {
    signOut();
    navigate("/signin");
  };

  return (
    <div className="flex min-h-screen bg-slate-100/70">
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-slate-950/60 backdrop-blur-xs lg:hidden"
        />
      )}

      {/* Left Sidebar (Dark Charcoal/Navy) */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col bg-slate-950 text-slate-300 transition-transform duration-200 lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-800/80 px-5 py-4">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 text-white shadow-sm shadow-indigo-500/30">
              <Bot className="h-5 w-5" />
            </div>
            <div>
              <div className="font-display text-sm font-bold text-white">HireFlow AI</div>
              <div className="text-[10px] font-medium text-indigo-300">
                Hiring &amp; HR AI Agent
              </div>
            </div>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-900 lg:hidden"
            aria-label="Close Sidebar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* All 13 Required Navigation Views */}
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Hiring &amp; HR Workspace
          </p>
          <nav className="mt-2 space-y-1" aria-label="HR Agent Navigation">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={() => setSidebarOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center justify-between rounded-xl px-3 py-2 text-[13px] font-medium transition ${
                      isActive
                        ? "bg-indigo-600 text-white shadow-sm shadow-indigo-500/30"
                        : "text-slate-300 hover:bg-slate-900 hover:text-white"
                    }`
                  }
                >
                  <span className="flex items-center gap-2.5 truncate">
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                  </span>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-slate-950">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {quota && (
            <div className="mt-6 rounded-xl border border-slate-800/80 bg-slate-900/60 p-3">
              <div className="flex items-center justify-between text-[11px] font-medium text-slate-300">
                <span>Monthly Token Quota</span>
                <span className="font-mono text-indigo-300">{quota.usage_percent}%</span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full ${
                    quota.usage_percent >= 90
                      ? "bg-rose-500"
                      : quota.usage_percent >= 70
                        ? "bg-amber-400"
                        : "bg-indigo-500"
                  }`}
                  style={{ width: `${Math.min(100, Math.max(2, quota.usage_percent))}%` }}
                />
              </div>
              <p className="mt-1.5 font-mono text-[10px] text-slate-400">
                {quota.tokens_used_this_month.toLocaleString()} /{" "}
                {quota.monthly_token_limit.toLocaleString()} tokens
              </p>
            </div>
          )}
        </div>

        {/* User Footer */}
        <div className="border-t border-slate-800/80 p-3">
          <div className="rounded-xl bg-slate-900/90 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-xs font-semibold text-white">{session.userName}</span>
              <span className="shrink-0 rounded bg-indigo-500/20 px-1.5 py-0.5 font-mono text-[10px] text-indigo-300">
                {session.role}
              </span>
            </div>
            <p className="mt-0.5 truncate text-[11px] text-slate-400">
              {session.userEmail || "Not authenticated"}
            </p>
            <div className="mt-2.5 flex items-center justify-between border-t border-slate-800 pt-2">
              <Link to="/" className="text-[11px] text-slate-400 hover:text-white">
                Overview Site
              </Link>
              {session.isLiveAuthenticated ? (
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="inline-flex items-center gap-1 text-[11px] text-rose-400 hover:text-rose-300"
                >
                  <LogOut className="h-3 w-3" />
                  Sign Out
                </button>
              ) : (
                <Link
                  to="/signin"
                  className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300"
                >
                  Sign In →
                </Link>
              )}
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Shell */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/90 bg-white/95 px-4 py-3 backdrop-blur-md sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
              aria-label="Open Navigation"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-800">
                <Building2 className="h-3.5 w-3.5 text-indigo-600" />
                Tenant: <strong className="font-semibold">{session.tenantName}</strong>
              </span>
              <span className="hidden items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 sm:inline-flex">
                <Users className="h-3.5 w-3.5 text-blue-600" />
                Role: <code className="font-mono font-semibold">{session.role}</code>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            {pendingApprovals > 0 && (
              <Link
                to="/dashboard/monitor"
                className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-100"
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-amber-600" />
                {pendingApprovals} Pending HITL
              </Link>
            )}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                backendStatus.online && session.isLiveAuthenticated
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : backendStatus.online
                    ? "border-amber-200 bg-amber-50 text-amber-800"
                    : "border-rose-200 bg-rose-50 text-rose-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  backendStatus.online && session.isLiveAuthenticated
                    ? "bg-emerald-500"
                    : backendStatus.online
                      ? "bg-amber-500"
                      : "bg-rose-500"
                }`}
              />
              {backendStatus.online && session.isLiveAuthenticated
                ? "HireFlow AI Live"
                : backendStatus.online
                  ? "Sign In Required"
                  : "Backend Offline"}
            </span>
            {session.tenantSlug && (
              <span className="hidden items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 font-mono text-[11px] font-medium text-indigo-700 md:inline-flex">
                <ShieldCheck className="h-3.5 w-3.5" />
                {session.tenantSlug}
              </span>
            )}
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl space-y-5">
            {lastActionError && (
              <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs font-medium text-rose-800">
                <span>{lastActionError}</span>
                <button
                  type="button"
                  onClick={clearLastActionError}
                  className="ml-4 font-semibold underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            {!session.isLiveAuthenticated ? (
              <div className="rounded-2xl border border-amber-200 bg-white p-8 text-center shadow-xs">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
                  <Bot className="h-6 w-6" />
                </div>
                <h2 className="mt-4 font-display text-xl font-bold text-slate-900">
                  Sign in to access your HireFlow AI HR Workspace
                </h2>
                <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
                  Authenticate with an organization account so all HR workflows, candidates,
                  knowledge documents, and audit logs sync securely with PostgreSQL RLS.
                </p>
                <div className="mt-5 flex justify-center gap-3">
                  <Link
                    to="/signin"
                    className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-500"
                  >
                    Go to Sign In →
                  </Link>
                </div>
              </div>
            ) : (
              <Outlet />
            )}
          </div>
        </main>
      </div>
    </div>
  );
};
