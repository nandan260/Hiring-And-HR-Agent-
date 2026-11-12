import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PublicFooter } from "../../components/layout/PublicFooter";
import { PublicNavbar } from "../../components/layout/PublicNavbar";
import { useApp } from "../../context/AppContext";

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
      setErrorMsg(res.error || "Login failed");
    }
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--bg)] text-[var(--fg)]">
      <PublicNavbar />

      <main className="mx-auto grid min-h-0 w-full max-w-5xl flex-1 items-center gap-6 px-6 lg:grid-cols-12">
        <div className="hf-card space-y-2.5 lg:col-span-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-bold text-[var(--fg)]">Workspace Sign In</h1>
            {!backendStatus.online && (
              <span className="hf-chip hf-chip-block">Offline</span>
            )}
          </div>

          <button
            type="button"
            disabled={loading || !backendStatus.online}
            onClick={() => quickLoginSeeded("ananya@acmecloud.io", "AcmeOwner!2026")}
            className="hf-subcard flex w-full items-center justify-between text-left hover:bg-[var(--surface-hover)] disabled:opacity-50"
          >
            <div>
              <div className="text-xs font-semibold text-[var(--fg)]">
                Acme Cloud &mdash; Owner
              </div>
              <div className="font-mono text-[11px] text-[var(--muted)]">ananya@acmecloud.io</div>
            </div>
            <span className="hf-chip hf-chip-pass">Sign In</span>
          </button>

          <button
            type="button"
            disabled={loading || !backendStatus.online}
            onClick={() => quickLoginSeeded("maya@acmecloud.io", "AcmeUser!2026")}
            className="hf-subcard flex w-full items-center justify-between text-left hover:bg-[var(--surface-hover)] disabled:opacity-50"
          >
            <div>
              <div className="text-xs font-semibold text-[var(--fg)]">
                Acme Cloud &mdash; Employee
              </div>
              <div className="font-mono text-[11px] text-[var(--muted)]">maya@acmecloud.io</div>
            </div>
            <span className="hf-chip hf-chip-plain">Sign In</span>
          </button>

          <button
            type="button"
            disabled={loading || !backendStatus.online}
            onClick={() => quickLoginSeeded("priya@novabio.io", "NovaOwner!2026")}
            className="hf-subcard flex w-full items-center justify-between text-left hover:bg-[var(--surface-hover)] disabled:opacity-50"
          >
            <div>
              <div className="text-xs font-semibold text-[var(--fg)]">
                NovaBio &mdash; Owner
              </div>
              <div className="font-mono text-[11px] text-[var(--muted)]">priya@novabio.io</div>
            </div>
            <span className="hf-chip hf-chip-plain">Sign In</span>
          </button>
        </div>

        <div className="hf-card lg:col-span-6">
          <div className="mb-4 flex gap-1.5 rounded-[var(--r-field)] border border-[var(--border)] p-1">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setErrorMsg(null);
              }}
              className={`flex-1 rounded-[6px] py-1.5 text-xs font-semibold ${
                mode === "login"
                  ? "bg-[var(--inv-bg)] text-[var(--inv-fg)]"
                  : "text-[var(--muted)] hover:text-[var(--fg)]"
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
              className={`flex-1 rounded-[6px] py-1.5 text-xs font-semibold ${
                mode === "register"
                  ? "bg-[var(--inv-bg)] text-[var(--inv-fg)]"
                  : "text-[var(--muted)] hover:text-[var(--fg)]"
              }`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === "register" && (
              <>
                <div className="hf-field">
                  <label>Full Name</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="hf-input"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="hf-field">
                    <label>Organization</label>
                    <input
                      type="text"
                      required
                      value={organizationName}
                      onChange={(e) => setOrganizationName(e.target.value)}
                      className="hf-input"
                    />
                  </div>
                  <div className="hf-field">
                    <label>Industry</label>
                    <input
                      type="text"
                      required
                      value={industry}
                      onChange={(e) => setIndustry(e.target.value)}
                      className="hf-input"
                    />
                  </div>
                </div>
              </>
            )}

            <div className="hf-field">
              <label>Email</label>
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
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="hf-input"
              />
            </div>

            {errorMsg && (
              <div className="rounded-[var(--r-field)] border border-[var(--fg)] px-3 py-2 text-xs text-[var(--fg)]">
                {errorMsg}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !backendStatus.online}
              className="hf-btn hf-btn-primary w-full"
            >
              {loading ? "Signing in..." : mode === "login" ? "Sign In" : "Create Account"}
            </button>
          </form>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
};
