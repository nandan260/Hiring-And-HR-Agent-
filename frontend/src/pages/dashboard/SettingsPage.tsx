import React, { useState } from "react";
import { Badge } from "../../components/common/Badge";
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

  const [tab, setTab] = useState<"guardrails" | "team" | "audit" | "api">("guardrails");
  const [blindMode, setBlindMode] = useState<boolean>(
    workspace?.settings.blind_screening_mode ?? false
  );
  const [strictPii, setStrictPii] = useState<boolean>(
    workspace?.settings.strict_pii_masking ?? true
  );
  const [requireHitl, setRequireHitl] = useState<boolean>(
    workspace?.settings.require_hitl_approval ?? true
  );
  const [routingTier, setRoutingTier] = useState<
    "tier_0_rule" | "tier_1_fast" | "tier_2_reasoning" | "auto_cascade"
  >(workspace?.settings.model_routing_tier || "auto_cascade");
  const [customPersona, setCustomPersona] = useState<string>(
    workspace?.settings.custom_persona_prompt || ""
  );
  const [savingSettings, setSavingSettings] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [invitePassword, setInvitePassword] = useState("HireFlowMember123!");
  const [inviteRole, setInviteRole] = useState<
    "business_owner" | "business_admin" | "business_employee"
  >("business_employee");

  const [urlInput, setUrlInput] = useState(apiBaseUrl);
  const canManage = session.role === "business_owner" || session.role === "business_admin";

  const handleSaveGuardrails = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    setSaveMessage(null);
    const res = await updateWorkspaceSettings({
      blind_screening_mode: blindMode,
      strict_pii_masking: strictPii,
      require_hitl_approval: requireHitl,
      model_routing_tier: routingTier,
      custom_persona_prompt: customPersona,
    });
    setSavingSettings(false);
    setSaveMessage(res.ok ? "Saved." : res.error || "Failed.");
  };

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await inviteMember({
      fullName: inviteName,
      email: inviteEmail,
      password: invitePassword,
      role: inviteRole,
    });
    if (res.ok) {
      setInviteName("");
      setInviteEmail("");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Settings</h1>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("guardrails")}
            className={`hf-tab ${tab === "guardrails" ? "active" : ""}`}
          >
            Guardrails
          </button>
          <button
            type="button"
            onClick={() => setTab("team")}
            className={`hf-tab ${tab === "team" ? "active" : ""}`}
          >
            Team ({organizationMembers.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("audit")}
            className={`hf-tab ${tab === "audit" ? "active" : ""}`}
          >
            Audit ({auditLogs.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("api")}
            className={`hf-tab ${tab === "api" ? "active" : ""}`}
          >
            API
          </button>
        </div>
      </div>

      {tab === "guardrails" && (
        <form
          onSubmit={handleSaveGuardrails}
          className="hf-card flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto"
        >
          <div className="grid gap-3 md:grid-cols-3">
            <label className="hf-subcard flex cursor-pointer items-center justify-between gap-2 text-xs">
              <span className="font-medium text-[var(--fg)]">Blind Screening</span>
              <input
                type="checkbox"
                checked={blindMode}
                onChange={(e) => setBlindMode(e.target.checked)}
                disabled={!canManage}
                className="h-4 w-4 accent-[var(--fg)]"
              />
            </label>
            <label className="hf-subcard flex cursor-pointer items-center justify-between gap-2 text-xs">
              <span className="font-medium text-[var(--fg)]">Strict PII Masking</span>
              <input
                type="checkbox"
                checked={strictPii}
                onChange={(e) => setStrictPii(e.target.checked)}
                disabled={!canManage}
                className="h-4 w-4 accent-[var(--fg)]"
              />
            </label>
            <label className="hf-subcard flex cursor-pointer items-center justify-between gap-2 text-xs">
              <span className="font-medium text-[var(--fg)]">HITL Approval</span>
              <input
                type="checkbox"
                checked={requireHitl}
                onChange={(e) => setRequireHitl(e.target.checked)}
                disabled={!canManage}
                className="h-4 w-4 accent-[var(--fg)]"
              />
            </label>
          </div>

          <div className="hf-field max-w-xs">
            <label>Model Routing Tier</label>
            <select
              value={routingTier}
              onChange={(e) => setRoutingTier(e.target.value as typeof routingTier)}
              disabled={!canManage}
              className="hf-input"
            >
              <option value="auto_cascade">Auto Cascade</option>
              <option value="tier_0_rule">Tier 0 Rule</option>
              <option value="tier_1_fast">Tier 1 Fast</option>
              <option value="tier_2_reasoning">Tier 2 Reasoning</option>
            </select>
          </div>

          <div className="hf-field flex min-h-0 flex-1 flex-col">
            <label>Custom HR Policy Persona</label>
            <textarea
              rows={3}
              value={customPersona}
              onChange={(e) => setCustomPersona(e.target.value)}
              disabled={!canManage}
              className="hf-input min-h-[80px] flex-1 resize-none"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--muted)]">{saveMessage || ""}</span>
            <button
              type="submit"
              disabled={!canManage || savingSettings}
              className="hf-btn hf-btn-primary"
            >
              {savingSettings ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </form>
      )}

      {tab === "team" && (
        <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
          <form onSubmit={handleInvite} className="hf-card col-span-12 flex flex-col gap-2.5 lg:col-span-4">
            <h2 className="hf-h2">Invite Member</h2>
            <div className="hf-field">
              <label>Full Name</label>
              <input
                type="text"
                value={inviteName}
                onChange={(e) => setInviteName(e.target.value)}
                required
                disabled={!canManage}
                className="hf-input"
              />
            </div>
            <div className="hf-field">
              <label>Email</label>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                required
                disabled={!canManage}
                className="hf-input"
              />
            </div>
            <div className="hf-field">
              <label>Temporary Password</label>
              <input
                type="password"
                value={invitePassword}
                onChange={(e) => setInvitePassword(e.target.value)}
                required
                disabled={!canManage}
                className="hf-input"
              />
            </div>
            <div className="hf-field">
              <label>Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}
                disabled={!canManage}
                className="hf-input"
              >
                <option value="business_employee">Employee</option>
                <option value="business_admin">Admin</option>
                <option value="business_owner">Owner</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={!canManage}
              className="hf-btn hf-btn-primary mt-auto w-full"
            >
              Invite
            </button>
          </form>

          <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-8">
            <div className="min-h-0 flex-1 overflow-y-auto">
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
                      <td className="font-medium text-[var(--fg)]">{m.fullName}</td>
                      <td className="font-mono text-xs text-[var(--muted)]">{m.email}</td>
                      <td>
                        <select
                          value={m.role}
                          disabled={!canManage}
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
                          className="hf-input py-1 text-xs"
                        >
                          <option value="business_owner">Owner</option>
                          <option value="business_admin">Admin</option>
                          <option value="business_employee">Employee</option>
                        </select>
                      </td>
                      <td>
                        <Badge variant={m.isActive ? "emerald" : "slate"}>
                          {m.isActive ? "Active" : "Disabled"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {tab === "audit" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col">
          {auditLogs.length === 0 ? (
            <div className="hf-empty my-auto">No audit entries.</div>
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <table className="hf-rows">
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Status</th>
                    <th>Resource</th>
                    <th className="num">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log) => (
                    <tr key={log.id}>
                      <td className="font-mono text-xs font-medium text-[var(--fg)]">
                        {log.action}
                      </td>
                      <td className="text-xs text-[var(--muted)]">{log.status}</td>
                      <td className="font-mono text-xs text-[var(--muted)]">
                        {log.resourceType}
                      </td>
                      <td className="num text-xs text-[var(--muted)]">
                        {new Date(log.createdAt).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "api" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-[var(--fg)]">Status:</span>
            <Badge variant={backendStatus.online ? "emerald" : "rose"}>
              {backendStatus.online ? "Online" : "Offline"}
            </Badge>
            <span className="font-mono text-[var(--muted)]">{backendStatus.detail}</span>
          </div>
          <div className="hf-field max-w-md">
            <label>Backend API Base URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="hf-input flex-1 font-mono"
              />
              <button
                type="button"
                onClick={() => {
                  setApiBaseUrl(urlInput);
                  refreshWorkspaceData();
                }}
                className="hf-btn hf-btn-primary"
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
