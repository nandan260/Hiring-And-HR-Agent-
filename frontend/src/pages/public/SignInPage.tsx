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
    if (!backendStatus.online) {
      setErrorMsg("FastAPI backend is offline. Start the backend server on port 8000 first.");
      return;
    }

    setLoading(true);
    const res =
      mode === "login"
        ? await loginLive({ email, password })
        : await registerBusinessLive({
            fullName,
            email,
            password,
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
    if (!backendStatus.online) {
      setErrorMsg("FastAPI backend is offline. Start the backend server on port 8000 first.");
      return;
    }
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
    <div className="min-h-screen bg-slate-50">
      <PublicNavbar />

      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-12 lg:px-8">
        <div className="space-y-6 lg:col-span-6">
          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              HireFlow AI • Tenant-Isolated Workspace Access
            </span>
            <h1 className="mt-3 font-display text-3xl font-bold text-slate-900">
              Sign in to HireFlow AI — Hiring &amp; HR AI Agent
            </h1>
            <p className="mt-2 text-sm text-slate-600">
              Authenticate against PostgreSQL with Argon2id + JWT. Every organization&apos;s
              resumes, candidates, interviews, onboarding records, and knowledge documents are
              strictly isolated via Row-Level Security.
            </p>
          </div>

          <div
            className={`rounded-xl border px-4 py-3 text-xs ${
              backendStatus.online
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-rose-200 bg-rose-50 text-rose-900"
            }`}
          >
            <div className="flex items-center gap-2">
              {!backendStatus.online && <AlertTriangle className="h-4 w-4 shrink-0 text-rose-600" />}
              <div>
                <strong>Backend Status:</strong> {backendStatus.detail}
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Seeded PostgreSQL Organization Accounts
            </h2>

            <button
              type="button"
              disabled={loading || !backendStatus.online}
              onClick={() => quickLoginSeeded("ananya@acmecloud.io", "AcmeOwner!2026")}
              className="flex w-full items-center justify-between rounded-2xl border border-indigo-200 bg-white p-4 text-left shadow-xs transition hover:border-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    Acme Cloud Corp — HR Business Owner
                  </div>
                  <div className="text-xs text-slate-500">
                    ananya@acmecloud.io • Full access to all 7 HR workflows &amp; Settings
                  </div>
                </div>
              </div>
              <span className="text-xs font-semibold text-indigo-600">Sign In →</span>
            </button>

            <button
              type="button"
              disabled={loading || !backendStatus.online}
              onClick={() => quickLoginSeeded("maya@acmecloud.io", "AcmeUser!2026")}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-xs transition hover:border-indigo-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
                  <UserCheck className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    Acme Cloud Corp — Business Employee (RBAC Test)
                  </div>
                  <div className="text-xs text-slate-500">
                    maya@acmecloud.io • Employee Policy Support allowed; Hiring/Analytics blocked
                  </div>
                </div>
              </div>
              <span className="text-xs font-semibold text-slate-700">Sign In →</span>
            </button>

            <button
              type="button"
              disabled={loading || !backendStatus.online}
              onClick={() => quickLoginSeeded("priya@novabio.io", "NovaOwner!2026")}
              className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-xs transition hover:border-indigo-300 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
                  <Lock className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-bold text-slate-900">
                    NovaBio HealthTech — Isolated Tenant B
                  </div>
                  <div className="text-xs text-slate-500">
                    priya@novabio.io • Separate RLS Tenant (0 Acme records visible)
                  </div>
                </div>
              </div>
              <span className="text-xs font-semibold text-slate-700">Sign In →</span>
            </button>
          </div>
        </div>

        <div className="w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-6 lg:justify-self-end lg:max-w-md">
          <div className="flex rounded-xl bg-slate-100 p-1 text-xs font-semibold">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setErrorMsg(null);
              }}
              className={`flex-1 rounded-lg py-2 transition ${
                mode === "login" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600"
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
                mode === "register" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600"
              }`}
            >
              Register Business
            </button>
          </div>

          <h2 className="mt-4 font-display text-lg font-bold text-slate-900">
            {mode === "login" ? "Business Account Sign-In" : "Create New Business Tenant"}
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            {mode === "login"
              ? "Authenticate against FastAPI and receive a tenant-scoped JWT."
              : "Creates an isolated organization tenant with full HireFlow AI HR capabilities."}
          </p>

          {errorMsg && (
            <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs font-medium text-rose-800">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleSubmit} className="mt-5 space-y-4">
            {mode === "register" && (
              <>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Full Name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Alex Morgan"
                    className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Organization Name</label>
                  <input
                    type="text"
                    required
                    value={organizationName}
                    onChange={(e) => setOrganizationName(e.target.value)}
                    placeholder="Vertex Systems Pvt Ltd"
                    className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700">Industry</label>
                  <input
                    type="text"
                    required
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400"
                  />
                </div>
              </>
            )}

            <div>
              <label className="text-xs font-semibold text-slate-700">Work Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2.5 text-sm outline-none focus:border-indigo-400"
              />
            </div>

            <button
              type="submit"
              disabled={loading || !backendStatus.online}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:from-indigo-500 hover:to-blue-500 disabled:opacity-60"
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
