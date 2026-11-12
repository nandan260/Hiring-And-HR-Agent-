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
  FileCode2,
  FileSearch,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  Moon,
  Plug,
  Settings,
  ShieldCheck,
  Sun,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import { useTheme } from "../../utils/theme";

interface NavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  end?: boolean;
  badge?: number;
}

const BrandMark: React.FC = () => (
  <svg
    width="22"
    height="22"
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
);

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
  const [theme, toggleTheme] = useTheme();
  const navigate = useNavigate();

  const pendingApprovals = approvals.filter((a) => a.status === "pending").length;

  const operationsNav: NavItem[] = [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true },
    { to: "/dashboard/recruitment", label: "Recruitment", icon: Briefcase },
    { to: "/dashboard/screening", label: "Resume Screening", icon: FileSearch },
    { to: "/dashboard/candidates", label: "Candidates", icon: Users },
    { to: "/dashboard/jd-generator", label: "Job Description Generator", icon: FileText },
    { to: "/dashboard/interviews", label: "Interview Management", icon: CalendarClock },
    { to: "/dashboard/onboarding", label: "Employee Onboarding", icon: UserCheck },
    { to: "/dashboard/assistant", label: "HR Assistant", icon: MessageSquareText },
    { to: "/dashboard/analytics", label: "HR Analytics", icon: BarChart3 },
  ];

  const governanceNav: NavItem[] = [
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
    <div className="hf-shell">
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-xs lg:hidden"
        />
      )}

      {/* Mobile Topbar */}
      <div className="hf-topbar">
        <Link to="/dashboard" className="hf-brand pb-0">
          <BrandMark />
          <span>HireFlow AI</span>
        </Link>
        <div className="flex items-center gap-2">
          {pendingApprovals > 0 && (
            <Link to="/dashboard/monitor" className="hf-chip hf-chip-escalate no-underline">
              {pendingApprovals} HITL
            </Link>
          )}
          <button
            type="button"
            onClick={() => setSidebarOpen((open) => !open)}
            className="hf-icon-btn"
            aria-label="Open Navigation"
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {/* Floating Sidebar */}
      <aside className={`hf-sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="flex items-center justify-between pb-1">
          <Link to="/" className="hf-brand">
            <BrandMark />
            <span>HireFlow AI</span>
          </Link>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="hf-icon-btn h-8 w-8 lg:hidden"
            aria-label="Close Navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="hf-nav" aria-label="Main navigation">
          {operationsNav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <Icon className="h-[17px] w-[17px] shrink-0 opacity-80" />
                <span className="flex-1 truncate">{item.label}</span>
              </NavLink>
            );
          })}

          <div className="hf-nav-gap" />

          {governanceNav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <Icon className="h-[17px] w-[17px] shrink-0 opacity-80" />
                <span className="flex-1 truncate">{item.label}</span>
                {item.badge !== undefined && <span className="hf-count">{item.badge}</span>}
              </NavLink>
            );
          })}
        </nav>

        <div className="hf-side-foot">
          {quota && (
            <div className="mb-2.5 rounded-xl border border-[var(--line)] bg-[var(--field)] px-3 py-2.5">
              <div className="flex items-center justify-between text-[11px] font-medium text-[var(--muted)]">
                <span>Monthly AI Quota</span>
                <span className="font-mono text-[var(--ink-2)]">{quota.usage_percent}%</span>
              </div>
              <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--panel)]">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, Math.max(2, quota.usage_percent))}%`,
                    background:
                      quota.usage_percent > 85
                        ? "var(--block)"
                        : quota.usage_percent > 60
                          ? "var(--esc)"
                          : "var(--pass)",
                  }}
                />
              </div>
              <div className="mt-1 font-mono text-[10.5px] text-[var(--muted)]">
                {quota.tokens_used_this_month.toLocaleString()} / {quota.monthly_token_limit.toLocaleString()} tok
              </div>
            </div>
          )}

          <div className="hf-who">
            <strong>{session.userName || session.tenantName || "HireFlow Workspace"}</strong>
            <span>
              {session.tenantName}, {session.role}
            </span>
          </div>

          <div className="hf-icon-row">
            <button
              type="button"
              onClick={toggleTheme}
              className="hf-icon-btn"
              aria-label="Toggle theme"
              title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <Link
              to="/dashboard/assistant"
              className="hf-icon-btn"
              aria-label="HR Assistant"
              title="HR Assistant"
            >
              <MessageSquareText className="h-4 w-4" />
            </Link>
            <a
              href="http://127.0.0.1:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="hf-icon-btn"
              aria-label="API Docs"
              title="FastAPI Docs"
            >
              <FileCode2 className="h-4 w-4" />
            </a>
            <button
              type="button"
              onClick={handleSignOut}
              className="hf-icon-btn"
              aria-label="Sign Out"
              title="Sign Out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Floating Main Panel */}
      <div className="hf-main">
        <div className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] bg-[var(--panel)]/95 px-6 py-2.5 backdrop-blur-md">
          <div className="flex flex-wrap items-center gap-2">
            <span className="hf-chip hf-chip-plain">
              <Building2 className="h-3.5 w-3.5 text-[var(--muted)]" />
              Tenant: <strong className="font-semibold text-[var(--ink)]">{session.tenantName}</strong>
            </span>
            <span className="hf-chip hf-chip-plain hidden sm:inline-flex">
              <Users className="h-3.5 w-3.5 text-[var(--muted)]" />
              Role: <code className="font-mono font-semibold text-[var(--ink)]">{session.role}</code>
            </span>
          </div>

          <div className="flex items-center gap-2">
            {pendingApprovals > 0 && (
              <Link to="/dashboard/monitor" className="hf-chip hf-chip-escalate no-underline">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {pendingApprovals} Pending HITL
              </Link>
            )}
            <span
              className={`hf-chip ${
                backendStatus.online && session.isLiveAuthenticated
                  ? "hf-chip-pass"
                  : backendStatus.online
                    ? "hf-chip-escalate"
                    : "hf-chip-block"
              }`}
            >
              {backendStatus.online && session.isLiveAuthenticated
                ? "HireFlow AI Live"
                : backendStatus.online
                  ? "Sign In Required"
                  : "Backend Offline"}
            </span>
            {session.tenantSlug && (
              <span className="hf-chip hf-chip-plain hidden font-mono md:inline-flex">
                <ShieldCheck className="h-3.5 w-3.5 text-[var(--pass)]" />
                {session.tenantSlug}
              </span>
            )}
          </div>
        </div>

        <main className="hf-page animate-fade-in">
          {lastActionError && (
            <div className="mb-5 flex items-center justify-between rounded-xl border border-[color:var(--block-soft)] bg-[var(--block-soft)] px-4 py-3 text-xs font-medium text-[var(--block)]">
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
            <div className="hf-card py-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-[var(--line)] bg-[var(--field)] text-[var(--ink)]">
                <Bot className="h-6 w-6" />
              </div>
              <h2 className="mt-4 text-xl font-bold tracking-tight text-[var(--ink)]">
                Sign in to access your HireFlow AI HR Workspace
              </h2>
              <p className="mx-auto mt-2 max-w-md text-sm text-[var(--muted)]">
                Authenticate with an organization account so all HR workflows, candidates,
                knowledge documents, and audit logs sync securely with PostgreSQL RLS.
              </p>
              <div className="mt-5 flex justify-center">
                <Link to="/signin" className="hf-btn hf-btn-primary">
                  Go to Sign In &rarr;
                </Link>
              </div>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>
    </div>
  );
};
