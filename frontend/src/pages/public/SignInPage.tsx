import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Building2, Lock, ShieldCheck, UserCheck, UserPlus } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { PublicNavbar } from "../../components/layout/PublicNavbar";

export const SignInPage: React.FC = () => {
  const { loginLive, registerBusinessLive, backendStatus } = useApp();
  const navigate = useNavigate();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("ananya@acmecloud.io");
  const [password, setPassword] = useState("AcmeOwner!2026");
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [industry, setIndustry] = useState("SaaS & Tech");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setLoading(true);
    const res =
      mode === "login"
        ? await loginLive({ email, password })
        : await registerBusinessLive({
            email,
            password,
            fullName,
            organizationName,
            industry,
          });
    setLoading(false);

    if (!res.ok) {
      setErrorMsg(res.error || "Authentication failed");
      return;
    }
    navigate("/dashboard");
  };

  const quickLoginSeeded = async (seedEmail: string, seedPassword: string) => {
    setErrorMsg(null);
    setMode("login");
    setEmail(seedEmail);
    setPassword(seedPassword);
    setLoading(true);
    const res = await loginLive({ email: seedEmail, password: seedPassword });
    setLoading(false);
    if (res.ok) {
      navigate("/dashboard");
    } else {
      setErrorMsg(res.error || "Seeded tenant login failed");
    }
  };

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      <PublicNavbar />

      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-12 lg:items-start lg:py-16">
        {/* Left: Seeded Organization Accounts & Isolation Notes */}
        <div className="space-y-5 lg:col-span-6">
          <div>
            <span className="hf-chip hf-chip-pass">
              <ShieldCheck className="h-3.5 w-3.5" />
              PostgreSQL RLS + JWT Session
            </span>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-[var(--ink)]">
              Sign in to HireFlow AI
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
              Access your organization&apos;s unified Hiring &amp; HR AI Agent workspace, real-time
              candidate &amp; onboarding tables, pgvector knowledge base, and approval queue.
            </p>
          </div>

          {!backendStatus.online && (
            <div className="rounded-xl border border-[color:var(--esc-soft)] bg-[var(--esc-soft)] p-4 text-xs text-[var(--ink)]">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--esc)]" />
                <div>
                  <strong className="font-semibold text-[var(--esc)]">Backend Offline:</strong>{" "}
                  {backendStatus.detail}
                </div>
              </div>
            </div>
          )}

          <div className="hf-card space-y-3">
            <h2 className="text-sm font-bold text-[var(--ink)]">
              Seeded PostgreSQL Organization Accounts
            </h2>
            <p className="text-xs text-[var(--muted)]">
              Click any seeded account to test real multi-tenant PostgreSQL Row-Level Security and
              role-based access control:
            </p>

            <button
              type="button"
              disabled={loading || !backendStatus.online}
              onClick={() => quickLoginSeeded("ananya@acmecloud.io", "AcmeOwner!2026")}
              className="hf-subcard flex w-full items-center justify-between text-left transition hover:border-[var(--muted)] disabled:opacity-50"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-lg border border-[var(--line)] bg-[var(--panel)] p-2 text-[var(--ink)]">
                  <Building2 className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-[var(--ink)]">
                    Acme Cloud Corp &mdash; HR Business Owner
                  </div>
                  <div className="mt-0.5 text-[11px] text-[var(--muted)]">
                    ananya@acmecloud.io &bull; Full access to all 7 HR workflows &amp; Settings
                  </div>
                </div>
              </div>
              <span className="hf-chip hf-chip-pass shrink-0">Sign In &rarr;</span>
            </button>

            <button
              type="button"
              disabled={loading || !backendStatus.online}
              onClick={() => quickLoginSeeded("maya@acmecloud.io", "AcmeUser!2026")}
              className="hf-subcard flex w-full items-center justify-between text-left transition hover:border-[var(--muted)] disabled:opacity-50"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-lg border border-[var(--line)] bg-[var(--panel)] p-2 text-[var(--ink-2)]">
                  <UserCheck className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-[var(--ink)]">
                    Acme Cloud Corp &mdash; Business Employee (RBAC Test)
                  </div>
                  <div className="mt-0.5 text-[11px] text-[var(--muted)]">
                    maya@acmecloud.io &bull; Employee Policy Support allowed; Hiring/Analytics
                    blocked
                  </div>
                </div>
              </div>
              <span className="hf-chip hf-chip-escalate shrink-0">Sign In &rarr;</span>
            </button>

            <button
              type="button"
              disabled={loading || !backendStatus.online}
              onClick={() => quickLoginSeeded("priya@novabio.io", "NovaOwner!2026")}
              className="hf-subcard flex w-full items-center justify-between text-left transition hover:border-[var(--muted)] disabled:opacity-50"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5 rounded-lg border border-[var(--line)] bg-[var(--panel)] p-2 text-[var(--ink)]">
                  <Lock className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-[var(--ink)]">
                    NovaBio HealthTech &mdash; Isolated Tenant B
                  </div>
                  <div className="mt-0.5 text-[11px] text-[var(--muted)]">
                    priya@novabio.io &bull; Separate RLS Tenant (0 Acme records visible)
                  </div>
                </div>
              </div>
              <span className="hf-chip hf-chip-plain shrink-0">Sign In &rarr;</span>
            </button>
          </div>
        </div>

        {/* Right: Sign In / Register Card */}
        <div className="hf-auth-card mx-auto w-full lg:col-span-6">
          <div className="flex gap-1 rounded-xl border border-[var(--line)] bg-[var(--field)] p-1 text-xs font-semibold">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setErrorMsg(null);
              }}
              className={`flex-1 rounded-lg py-2 transition ${
                mode === "login"
                  ? "bg-[var(--panel)] text-[var(--ink)] shadow-xs"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setErrorMsg(null);
              }}
              className={`flex-1 rounded-lg py-2 transition ${
                mode === "register"
                  ? "bg-[var(--panel)] text-[var(--ink)] shadow-xs"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              Register Business
            </button>
          </div>

          <h2 className="mt-6 text-xl font-bold tracking-tight text-[var(--ink)]">
            {mode === "login" ? "Workspace Sign In" : "Create Isolated Organization"}
          </h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            {mode === "login"
              ? "Authenticate with your organization credentials."
              : "Provision a new PostgreSQL RLS tenant and automatically activate all 7 HR workflows."}
          </p>

          {errorMsg && (
            <div className="mt-4 rounded-xl border border-[color:var(--block-soft)] bg-[var(--block-soft)] p-3 text-xs font-medium text-[var(--block)]">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            {mode === "register" && (
              <>
                <div className="hf-field">
                  <label>Full Name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Rivera"
                    className="hf-input"
                  />
                </div>
                <div className="hf-field">
                  <label>Organization Name</label>
                  <input
                    type="text"
                    required
                    value={organizationName}
                    onChange={(e) => setOrganizationName(e.target.value)}
                    placeholder="Apex Logistics Inc."
                    className="hf-input"
                  />
                </div>
                <div className="hf-field">
                  <label>Industry</label>
                  <input
                    type="text"
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="hf-input"
                  />
                </div>
              </>
            )}

            <div className="hf-field">
              <label>Work Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="hf-input"
              />
            </div>

            <div className="hf-field">
              <label>Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="hf-input"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !backendStatus.online}
              className="hf-btn hf-btn-primary h-11 w-full"
            >
              {mode === "register" && <UserPlus className="h-4 w-4" />}
              {loading ? "Authenticating..." : mode === "login" ? "Sign In" : "Register & Launch"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
