import React, { useEffect, useState } from "react";
import { RefreshCw, Save, Server, Shield, UserPlus, Users } from "lucide-react";
import { useApp } from "../../context/AppContext";

export const SettingsPage: React.FC = () => {
  const {
    session,
    workspace,
    apiBaseUrl,
    setApiBaseUrl,
    backendStatus,
    organizationMembers,
    auditLogs,
    updateWorkspaceSettings,
    inviteMember,
    updateMemberRole,
    refreshWorkspaceData,
  } = useApp();

  const [baseUrlInput, setBaseUrlInput] = useState(apiBaseUrl);
  const [blindMode, setBlindMode] = useState(workspace?.settings.blind_screening_mode ?? true);
  const [strictPii, setStrictPii] = useState(workspace?.settings.strict_pii_masking ?? true);
  const [requireHitl, setRequireHitl] = useState(workspace?.settings.require_hitl_approval ?? true);
  const [modelTier, setModelTier] = useState<
    "tier_0_rule" | "tier_1_fast" | "tier_2_reasoning" | "auto_cascade"
  >(workspace?.settings.model_routing_tier || "auto_cascade");
  const [monthlyQuota, setMonthlyQuota] = useState(
    workspace?.settings.monthly_token_quota ?? 2000000
  );
  const [customPersona, setCustomPersona] = useState(
    workspace?.settings.custom_persona_prompt ?? ""
  );
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsFeedback, setSettingsFeedback] = useState<string | null>(null);

  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [invitePassword, setInvitePassword] = useState("TempPass!2026");
  const [inviteRole, setInviteRole] = useState<
    "business_owner" | "business_admin" | "business_employee"
  >("business_employee");
  const [inviteFeedback, setInviteFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (workspace?.settings) {
      setBlindMode(workspace.settings.blind_screening_mode);
      setStrictPii(workspace.settings.strict_pii_masking);
      setRequireHitl(workspace.settings.require_hitl_approval);
      setModelTier(workspace.settings.model_routing_tier);
      setMonthlyQuota(workspace.settings.monthly_token_quota);
      setCustomPersona(workspace.settings.custom_persona_prompt);
    }
  }, [workspace]);

  const canManage =
    session.role === "business_owner" ||
    session.role === "business_admin" ||
    session.role === "platform_admin";

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    setSettingsFeedback(null);
    const res = await updateWorkspaceSettings({
      blind_screening_mode: blindMode,
      strict_pii_masking: strictPii,
      require_hitl_approval: requireHitl,
      model_routing_tier: modelTier,
      monthly_token_quota: Number(monthlyQuota),
      custom_persona_prompt: customPersona,
    });
    setSavingSettings(false);
    setSettingsFeedback(
      res.ok ? "Workspace AI guardrails & monthly token quota saved." : res.error || "Failed"
    );
  };

  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setInviteFeedback(null);
    const res = await inviteMember({
      fullName: inviteName,
      email: inviteEmail,
      password: invitePassword,
      role: inviteRole,
    });
    if (res.ok) {
      setInviteFeedback(`Added ${inviteEmail} as ${inviteRole}.`);
      setInviteName("");
      setInviteEmail("");
    } else {
      setInviteFeedback(res.error || "Invite failed");
    }
  };

  return (
    <div className="space-y-8">
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Settings</h1>
          <p className="hf-lede">
            Manage AI compliance guardrails, workspace monthly token quota, team RBAC roles, audit
            trails, and backend API connectivity.
          </p>
        </div>
      </div>

      <div className="hf-card space-y-0">
        {/* Section 1: AI Guardrails & Monthly Token Quota */}
        <form onSubmit={handleSaveSettings} className="hf-section">
          <div className="hf-section-grid">
            <div>
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-[var(--pass)]" />
                <h2 className="hf-h2 mb-0">AI Guardrails &amp; Quota</h2>
              </div>
              <p className="hf-lede mt-2 text-xs">
                Control model cascade tiering, monthly token ceiling, blind screening mode, and
                human-in-the-loop write approvals.
              </p>
            </div>

            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="hf-field">
                  <label>Model Routing Tier</label>
                  <select
                    disabled={!canManage}
                    value={modelTier}
                    onChange={(e) =>
                      setModelTier(
                        e.target.value as
                          | "tier_0_rule"
                          | "tier_1_fast"
                          | "tier_2_reasoning"
                          | "auto_cascade"
                      )
                    }
                    className="hf-input disabled:opacity-60"
                  >
                    <option value="auto_cascade">
                      Auto Cascade (Deterministic + Configurable LLM)
                    </option>
                    <option value="tier_0_rule">Tier 0 Rule / Deterministic Only</option>
                    <option value="tier_1_fast">Tier 1 Fast</option>
                    <option value="tier_2_reasoning">Tier 2 Reasoning</option>
                  </select>
                </div>

                <div className="hf-field">
                  <label>Monthly Workspace Token Quota</label>
                  <input
                    type="number"
                    min={100}
                    max={100000000}
                    disabled={!canManage}
                    value={monthlyQuota}
                    onChange={(e) => setMonthlyQuota(Number(e.target.value))}
                    className="hf-input disabled:opacity-60"
                  />
                </div>
              </div>

              <div className="hf-policy">
                <label className="hf-tier flex cursor-pointer items-center justify-between gap-2 text-xs font-semibold text-[var(--ink)]">
                  <span>Blind Resume Screening</span>
                  <input
                    type="checkbox"
                    disabled={!canManage}
                    checked={blindMode}
                    onChange={(e) => setBlindMode(e.target.checked)}
                    className="h-4 w-4 accent-[var(--pass)]"
                  />
                </label>
                <label className="hf-tier flex cursor-pointer items-center justify-between gap-2 text-xs font-semibold text-[var(--ink)]">
                  <span>Strict PII Masking</span>
                  <input
                    type="checkbox"
                    disabled={!canManage}
                    checked={strictPii}
                    onChange={(e) => setStrictPii(e.target.checked)}
                    className="h-4 w-4 accent-[var(--pass)]"
                  />
                </label>
                <label className="hf-tier flex cursor-pointer items-center justify-between gap-2 text-xs font-semibold text-[var(--ink)]">
                  <span>Require HITL for Writes</span>
                  <input
                    type="checkbox"
                    disabled={!canManage}
                    checked={requireHitl}
                    onChange={(e) => setRequireHitl(e.target.checked)}
                    className="h-4 w-4 accent-[var(--esc)]"
                  />
                </label>
              </div>

              <div className="hf-field">
                <label>Custom Tenant Workspace Preferences (Non-overriding instructions)</label>
                <textarea
                  rows={2}
                  disabled={!canManage}
                  value={customPersona}
                  onChange={(e) => setCustomPersona(e.target.value)}
                  placeholder="e.g., Emphasize structured backend architecture skills and concise bullet summaries."
                  className="hf-input disabled:opacity-60"
                />
              </div>

              {canManage && (
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="submit"
                    disabled={savingSettings}
                    className="hf-btn hf-btn-primary hf-btn-sm"
                  >
                    <Save className="h-3.5 w-3.5" />
                    {savingSettings ? "Saving..." : "Save Workspace Settings"}
                  </button>
                  {settingsFeedback && (
                    <span className="text-xs text-[var(--pass)]">{settingsFeedback}</span>
                  )}
                </div>
              )}
            </div>
          </div>
        </form>

        {/* Section 2: Team Members & RBAC */}
        <div className="hf-section">
          <div className="hf-section-grid">
            <div>
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-[var(--ink)]" />
                <h2 className="hf-h2 mb-0">
                  Team &amp; RBAC ({organizationMembers.length})
                </h2>
              </div>
              <p className="hf-lede mt-2 text-xs">
                Assign business owners, HR admins, or policy-only employee accounts within your
                isolated tenant.
              </p>
            </div>

            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="hf-rows">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {organizationMembers.map((m) => (
                      <tr key={m.memberId}>
                        <td className="font-semibold text-[var(--ink)]">{m.fullName}</td>
                        <td>{m.email}</td>
                        <td>
                          {canManage && m.role !== "platform_admin" ? (
                            <select
                              value={m.role}
                              onChange={(e) =>
                                updateMemberRole(
                                  m.memberId,
                                  e.target.value as
                                    | "business_owner"
                                    | "business_admin"
                                    | "business_employee",
                                  m.isActive
                                )
                              }
                              className="hf-input w-auto py-1 font-mono text-xs"
                            >
                              <option value="business_owner">business_owner</option>
                              <option value="business_admin">business_admin</option>
                              <option value="business_employee">business_employee</option>
                            </select>
                          ) : (
                            <code className="font-mono text-xs text-[var(--ink)]">{m.role}</code>
                          )}
                        </td>
                        <td>
                          <span className={`hf-chip ${m.isActive ? "hf-chip-pass" : "hf-chip-plain"}`}>
                            {m.isActive ? "Active" : "Inactive"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {canManage && (
                <form
                  onSubmit={handleInviteMember}
                  className="grid gap-2.5 border-t border-[var(--line)] pt-4 sm:grid-cols-2 lg:grid-cols-[1fr_1.2fr_0.9fr_1.2fr_auto]"
                >
                  <input
                    type="text"
                    required
                    value={inviteName}
                    onChange={(e) => setInviteName(e.target.value)}
                    placeholder="Full Name"
                    className="hf-input text-xs"
                  />
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="Email Address"
                    className="hf-input text-xs"
                  />
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={invitePassword}
                    onChange={(e) => setInvitePassword(e.target.value)}
                    placeholder="Initial Password"
                    className="hf-input text-xs"
                  />
                  <select
                    value={inviteRole}
                    onChange={(e) =>
                      setInviteRole(
                        e.target.value as "business_owner" | "business_admin" | "business_employee"
                      )
                    }
                    className="hf-input text-xs"
                  >
                    <option value="business_employee">business_employee</option>
                    <option value="business_admin">business_admin</option>
                    <option value="business_owner">business_owner</option>
                  </select>
                  <button type="submit" className="hf-btn hf-btn-primary">
                    <UserPlus className="h-3.5 w-3.5" />
                    Add Member
                  </button>
                </form>
              )}
              {inviteFeedback && <p className="text-xs text-[var(--ink-2)]">{inviteFeedback}</p>}
            </div>
          </div>
        </div>

        {/* Section 3: Audit Logs */}
        {canManage && (
          <div className="hf-section">
            <div className="hf-section-grid">
              <div>
                <h2 className="hf-h2 mb-0">Security Audit Logs ({auditLogs.length})</h2>
                <p className="hf-lede mt-2 text-xs">
                  Immutable event records scoped to your organization via PostgreSQL RLS.
                </p>
              </div>

              <div>
                {auditLogs.length === 0 ? (
                  <p className="text-xs text-[var(--muted)]">No audit entries recorded yet.</p>
                ) : (
                  <div className="max-h-64 divide-y divide-[var(--line)] overflow-y-auto text-xs">
                    {auditLogs.slice(0, 20).map((log) => (
                      <div
                        key={log.id}
                        className="flex flex-wrap items-center justify-between gap-2 py-2.5"
                      >
                        <div>
                          <code className="font-mono font-semibold text-[var(--ink)]">
                            {log.action}
                          </code>
                          <span className="mx-2 text-[var(--muted)]">&bull;</span>
                          <span className="text-[var(--ink-2)]">
                            {log.resourceType} ({log.status})
                          </span>
                        </div>
                        <span className="font-mono text-[11px] text-[var(--muted)]">
                          {new Date(log.createdAt).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Section 4: FastAPI Endpoint & Diagnostics */}
        <div className="hf-section">
          <div className="hf-section-grid">
            <div>
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-[var(--muted)]" />
                <h2 className="hf-h2 mb-0">FastAPI Control Plane</h2>
              </div>
              <p className="hf-lede mt-2 text-xs">{backendStatus.detail}</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={baseUrlInput}
                onChange={(e) => setBaseUrlInput(e.target.value)}
                className="hf-input flex-1 font-mono text-xs"
              />
              <button
                type="button"
                onClick={() => setApiBaseUrl(baseUrlInput)}
                className="hf-btn"
              >
                Update Endpoint
              </button>
              <button type="button" onClick={() => refreshWorkspaceData()} className="hf-btn">
                <RefreshCw className="h-3.5 w-3.5" />
                Sync Now
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
