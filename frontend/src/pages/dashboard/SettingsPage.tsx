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
  const [monthlyQuota, setMonthlyQuota] = useState(workspace?.settings.monthly_token_quota ?? 2000000);
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
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-600">
          Manage AI compliance guardrails, workspace monthly token quota, team RBAC roles, audit
          trails, and backend API connectivity.
        </p>
      </div>

      {/* AI Guardrails & Monthly Token Quota */}
      <form
        onSubmit={handleSaveSettings}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            HR Agent Guardrails &amp; Monthly Token Quota
          </h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs font-semibold text-slate-700">Model Routing Tier</label>
            <select
              disabled={!canManage}
              value={modelTier}
              onChange={(e) =>
                setModelTier(
                  e.target.value as "tier_0_rule" | "tier_1_fast" | "tier_2_reasoning" | "auto_cascade"
                )
              }
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 disabled:bg-slate-50"
            >
              <option value="auto_cascade">Auto Cascade (Deterministic + Configurable LLM)</option>
              <option value="tier_0_rule">Tier 0 Rule / Deterministic Only</option>
              <option value="tier_1_fast">Tier 1 Fast</option>
              <option value="tier_2_reasoning">Tier 2 Reasoning</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700">
              Monthly Workspace Token Quota
            </label>
            <input
              type="number"
              min={100}
              max={100000000}
              disabled={!canManage}
              value={monthlyQuota}
              onChange={(e) => setMonthlyQuota(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 disabled:bg-slate-50"
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-5 pt-1 text-xs font-medium text-slate-800">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              disabled={!canManage}
              checked={blindMode}
              onChange={(e) => setBlindMode(e.target.checked)}
              className="h-4 w-4 rounded text-indigo-600"
            />
            Blind Resume Screening
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              disabled={!canManage}
              checked={strictPii}
              onChange={(e) => setStrictPii(e.target.checked)}
              className="h-4 w-4 rounded text-indigo-600"
            />
            Strict PII Masking
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              disabled={!canManage}
              checked={requireHitl}
              onChange={(e) => setRequireHitl(e.target.checked)}
              className="h-4 w-4 rounded text-indigo-600"
            />
            Require HITL Approval for Writes
          </label>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-700">
            Custom Tenant Workspace Preferences (Non-overriding instructions)
          </label>
          <textarea
            rows={2}
            disabled={!canManage}
            value={customPersona}
            onChange={(e) => setCustomPersona(e.target.value)}
            placeholder="e.g., Emphasize structured backend architecture skills and concise bullet summaries."
            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 disabled:bg-slate-50"
          />
        </div>

        {canManage && (
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={savingSettings}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
            >
              <Save className="h-3.5 w-3.5" />
              {savingSettings ? "Saving..." : "Save Workspace Settings"}
            </button>
            {settingsFeedback && <span className="text-xs text-slate-600">{settingsFeedback}</span>}
          </div>
        )}
      </form>

      {/* Organization Members & RBAC */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Team Members &amp; Workflow RBAC ({organizationMembers.length})
          </h2>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Email</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {organizationMembers.map((m) => (
                <tr key={m.memberId}>
                  <td className="py-2.5 pr-4 font-semibold text-slate-900">{m.fullName}</td>
                  <td className="py-2.5 pr-4 text-slate-600">{m.email}</td>
                  <td className="py-2.5 pr-4">
                    {canManage && m.role !== "platform_admin" ? (
                      <select
                        value={m.role}
                        onChange={(e) =>
                          updateMemberRole(
                            m.memberId,
                            e.target.value as "business_owner" | "business_admin" | "business_employee",
                            m.isActive
                          )
                        }
                        className="rounded-lg border border-slate-200 px-2 py-1 font-mono text-[11px]"
                      >
                        <option value="business_owner">business_owner</option>
                        <option value="business_admin">business_admin</option>
                        <option value="business_employee">business_employee</option>
                      </select>
                    ) : (
                      <code className="font-mono text-[11px] text-slate-700">{m.role}</code>
                    )}
                  </td>
                  <td className="py-2.5">
                    <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
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
            className="mt-5 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-5"
          >
            <input
              type="text"
              required
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              placeholder="Full Name"
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
            />
            <input
              type="email"
              required
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="Email Address"
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
            />
            <input
              type="password"
              required
              minLength={8}
              value={invitePassword}
              onChange={(e) => setInvitePassword(e.target.value)}
              placeholder="Initial Password"
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
            />
            <select
              value={inviteRole}
              onChange={(e) =>
                setInviteRole(
                  e.target.value as "business_owner" | "business_admin" | "business_employee"
                )
              }
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs"
            >
              <option value="business_employee">business_employee</option>
              <option value="business_admin">business_admin</option>
              <option value="business_owner">business_owner</option>
            </select>
            <button
              type="submit"
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800"
            >
              <UserPlus className="h-3.5 w-3.5" />
              Add Member
            </button>
          </form>
        )}
        {inviteFeedback && <p className="mt-2 text-xs text-slate-600">{inviteFeedback}</p>}
      </div>

      {/* Audit Log Viewer */}
      {canManage && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <h2 className="font-display text-base font-bold text-slate-900">
            Recent Security &amp; Governance Audit Logs ({auditLogs.length})
          </h2>
          {auditLogs.length === 0 ? (
            <p className="mt-3 text-xs text-slate-500">No audit entries recorded yet.</p>
          ) : (
            <div className="mt-3 max-h-64 overflow-y-auto divide-y divide-slate-100 text-xs">
              {auditLogs.slice(0, 20).map((log) => (
                <div key={log.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <div>
                    <code className="font-mono font-semibold text-indigo-700">{log.action}</code>
                    <span className="mx-2 text-slate-300">•</span>
                    <span className="text-slate-600">
                      {log.resourceType} ({log.status})
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-slate-400">
                    {new Date(log.createdAt).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Backend Connection Diagnostics */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-slate-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            FastAPI Control Plane Endpoint
          </h2>
        </div>
        <p className="mt-1 text-xs text-slate-600">{backendStatus.detail}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            type="text"
            value={baseUrlInput}
            onChange={(e) => setBaseUrlInput(e.target.value)}
            className="flex-1 rounded-xl border border-slate-200 px-3 py-2 font-mono text-xs"
          />
          <button
            type="button"
            onClick={() => setApiBaseUrl(baseUrlInput)}
            className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            Update Endpoint
          </button>
          <button
            type="button"
            onClick={() => refreshWorkspaceData()}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Sync Now
          </button>
        </div>
      </div>
    </div>
  );
};
