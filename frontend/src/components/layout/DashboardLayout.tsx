import React, { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useApp } from "../../context/AppContext";
import { useTheme } from "../../utils/theme";

interface NavItem {
  to: string;
  label: string;
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
  const [theme, toggleTheme] = useTheme();
  const navigate = useNavigate();

  const pendingApprovals = approvals.filter((a) => a.status === "pending").length;

  const operationsNav: NavItem[] = [
    { to: "/dashboard", label: "Dashboard", end: true },
    { to: "/dashboard/recruitment", label: "Recruitment" },
    { to: "/dashboard/screening", label: "Resume Screening" },
    { to: "/dashboard/candidates", label: "Candidates" },
    { to: "/dashboard/jd-generator", label: "Job Description Generator" },
    { to: "/dashboard/interviews", label: "Interview Management" },
    { to: "/dashboard/onboarding", label: "Employee Onboarding" },
    { to: "/dashboard/assistant", label: "HR Assistant" },
    { to: "/dashboard/analytics", label: "HR Analytics" },
  ];

  const governanceNav: NavItem[] = [
    {
      to: "/dashboard/monitor",
      label: "Agent Execution Monitor",
      badge: pendingApprovals || undefined,
    },
    { to: "/dashboard/knowledge-base", label: "Knowledge Base" },
    { to: "/dashboard/integrations", label: "Tools and Integrations" },
    { to: "/dashboard/settings", label: "Settings" },
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
          className="fixed inset-0 z-30 bg-black/60 lg:hidden"
        />
      )}

      <div className="hf-topbar">
        <Link to="/dashboard" className="hf-brand pb-0">
          HireFlow AI
        </Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSidebarOpen((s) => !s)}
            className="hf-btn hf-btn-sm"
          >
            Menu
          </button>
        </div>
      </div>

      <aside className={`hf-sidebar ${sidebarOpen ? "open" : ""}`}>
        <Link to="/dashboard" className="hf-brand">
          HireFlow AI
        </Link>

        <nav className="hf-nav">
          {operationsNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <span>{item.label}</span>
            </NavLink>
          ))}

          <div className="hf-nav-gap" />

          {governanceNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              <span className="truncate">{item.label}</span>
              {item.badge ? <span className="hf-count">{item.badge}</span> : null}
            </NavLink>
          ))}
        </nav>

        <div className="hf-side-foot">
          {quota && (
            <div className="rounded-[var(--r-field)] border border-[var(--border)] px-2.5 py-2 text-[11px]">
              <div className="flex items-center justify-between text-[var(--muted)]">
                <span>Quota</span>
                <span className="font-mono font-semibold text-[var(--fg)]">
                  {quota.usage_percent.toFixed(1)}%
                </span>
              </div>
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full border border-[var(--border)]">
                <div
                  className="h-full bg-[var(--fg)]"
                  style={{ width: `${Math.min(100, Math.max(2, quota.usage_percent))}%` }}
                />
              </div>
            </div>
          )}

          <div className="hf-who">
            <strong>{session.userName}</strong>
            <span>
              {session.tenantName} / {session.role}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-1.5">
            <button type="button" onClick={toggleTheme} className="hf-btn hf-btn-sm">
              {theme === "dark" ? "Light" : "Dark"}
            </button>
            <button type="button" onClick={handleSignOut} className="hf-btn hf-btn-sm">
              Sign Out
            </button>
          </div>
        </div>
      </aside>

      <div className="hf-main">
        <header className="flex flex-none items-center justify-between gap-2 border-b border-[var(--border)] px-5 py-2 text-xs">
          <div className="flex items-center gap-2 font-mono text-[var(--muted)]">
            <strong className="text-[var(--fg)]">{session.tenantName}</strong>
            <span>/</span>
            <span>{session.role}</span>
          </div>

          <div className="flex items-center gap-2">
            {pendingApprovals > 0 && (
              <Link to="/dashboard/monitor" className="hf-chip hf-chip-escalate no-underline">
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
                ? "Live"
                : backendStatus.online
                  ? "Sign In"
                  : "Offline"}
            </span>
          </div>
        </header>

        <main className="hf-page">
          {lastActionError && (
            <div className="mb-3 flex flex-none items-center justify-between rounded-[var(--r-field)] border border-[var(--fg)] px-3 py-2 text-xs text-[var(--fg)]">
              <span>{lastActionError}</span>
              <button type="button" onClick={clearLastActionError} className="font-semibold underline">
                Dismiss
              </button>
            </div>
          )}

          {!session.isLiveAuthenticated ? (
            <div className="hf-card my-auto flex flex-col items-center gap-3 py-10 text-center">
              <h2 className="text-lg font-bold text-[var(--fg)]">Sign in required</h2>
              <Link to="/signin" className="hf-btn hf-btn-primary">
                Go to Sign In
              </Link>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>
    </div>
  );
};
