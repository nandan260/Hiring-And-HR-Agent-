import React, { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  KeyRound,
  Lock,
  Plug,
  Plus,
  RefreshCw,
  Server,
  ShieldAlert,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";

export const ToolsIntegrationsPage: React.FC = () => {
  const {
    integrations,
    toggleIntegrationPermission,
    bindIntegrationCredential,
    session,
    structuredTools,
    mcpData,
    refreshRuntimeData,
    setLastActionError,
  } = useApp();

  const [secretInputs, setSecretInputs] = useState<Record<string, string>>({});
  const [bindingId, setBindingId] = useState<string | null>(null);
  const [busyMcpId, setBusyMcpId] = useState<string | null>(null);
  const [registeringMcp, setRegisteringMcp] = useState(false);

  const [mcpForm, setMcpForm] = useState({
    slug: "",
    name: "",
    transport: "stdio" as "stdio" | "sse",
    command_or_url: "",
    args: "",
    env_keys: "",
    description: "",
  });

  const canManage =
    session.role === "business_owner" ||
    session.role === "business_admin" ||
    session.role === "platform_admin";

  useEffect(() => {
    refreshRuntimeData();
  }, [refreshRuntimeData]);

  // Deduplicate by tool_slug so admin toggles & Fernet credential bindings stay unified
  const uniqueTools = useMemo(() => {
    const map = new Map<string, (typeof integrations)[number] & { workflows: string[] }>();
    for (const item of integrations) {
      const existing = map.get(item.tool_slug);
      if (!existing) {
        map.set(item.tool_slug, { ...item, workflows: [item.workflow_name] });
      } else {
        if (!existing.workflows.includes(item.workflow_name)) {
          existing.workflows.push(item.workflow_name);
        }
        if (item.credential_status === "bound_encrypted") {
          existing.credential_status = item.credential_status;
          existing.masked_secret_ref = item.masked_secret_ref;
        }
      }
    }
    return Array.from(map.values());
  }, [integrations]);

  const handleBindSecret = async (permissionId: string) => {
    const val = (secretInputs[permissionId] || "").trim();
    if (!val || val.length < 4) return;
    setBindingId(permissionId);
    const ok = await bindIntegrationCredential(permissionId, val);
    setBindingId(null);
    if (ok) {
      setSecretInputs((prev) => ({ ...prev, [permissionId]: "" }));
    }
  };

  const handleRegisterMcp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mcpForm.slug.trim() || !mcpForm.name.trim() || !mcpForm.command_or_url.trim()) return;
    setRegisteringMcp(true);
    try {
      await apiClient.registerMcpServer({
        slug: mcpForm.slug.trim(),
        name: mcpForm.name.trim(),
        transport: mcpForm.transport,
        command_or_url: mcpForm.command_or_url.trim(),
        args: mcpForm.args
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        env_keys: mcpForm.env_keys
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        description: mcpForm.description.trim(),
      });
      setMcpForm({
        slug: "",
        name: "",
        transport: "stdio",
        command_or_url: "",
        args: "",
        env_keys: "",
        description: "",
      });
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to register MCP server");
    } finally {
      setRegisteringMcp(false);
    }
  };

  const handleApproval = async (serverId: string, approved: boolean) => {
    setBusyMcpId(serverId);
    try {
      await apiClient.setMcpApproval(serverId, approved);
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to update MCP approval");
    } finally {
      setBusyMcpId(null);
    }
  };

  const handleDiscoverTools = async (serverId: string) => {
    setBusyMcpId(serverId);
    try {
      await apiClient.discoverMcpTools(serverId);
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to discover MCP tools");
    } finally {
      setBusyMcpId(null);
    }
  };

  const handleToggleMcpToolPerm = async (serverId: string, toolName: string, allowed: boolean) => {
    setBusyMcpId(serverId);
    try {
      await apiClient.updateMcpToolPermission(serverId, { tool_name: toolName, allowed });
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(
        err instanceof Error ? err.message : "Failed to update MCP tool permission"
      );
    } finally {
      setBusyMcpId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Tools and Integrations</h1>
          <p className="hf-lede">
            Manage schema-enforced HR tools, external MCP client connections, approval gates, and
            Fernet-encrypted credentials per tenant.
          </p>
        </div>
        {!canManage && (
          <span className="hf-chip hf-chip-escalate">
            <Lock className="h-3.5 w-3.5" />
            Read-only (Admin/Owner required to modify)
          </span>
        )}
      </div>

      <div className="hf-claim escalated">
        <div className="bar" />
        <div className="flex items-start gap-2.5 pr-2 text-xs text-[var(--ink-2)]">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-[var(--esc)]" />
          <span>
            <strong className="text-[var(--ink)]">Runtime Security Policy:</strong> Resume
            PDF/DOCX parsing and weighted ranking execute inside isolated tenant sandboxes. Web
            inspection runs inside ephemeral Playwright contexts with SSRF and download blocking.
            External MCP servers require explicit Admin approval before discovery or execution.
          </span>
        </div>
      </div>

      {/* Schema-Documented Core HR Tool Registry */}
      <div className="hf-card">
        <div className="flex items-center gap-2">
          <Wrench className="h-4 w-4 text-[var(--muted)]" />
          <h2 className="hf-h2 mb-0">
            Schema-Documented HR Tool Registry ({structuredTools.length} Core Tools)
          </h2>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {structuredTools.map((tool) => {
            const props = Object.keys(
              ((tool.input_schema as Record<string, unknown>)?.properties as Record<
                string,
                unknown
              >) || {}
            );
            return (
              <div key={tool.tool_id} className="hf-subcard text-xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-bold text-[var(--ink)]">{tool.name}</span>
                    <span className="ml-2 font-mono text-[11px] text-[var(--muted)]">
                      {tool.tool_id}
                    </span>
                  </div>
                  <div className="flex gap-1.5">
                    <span
                      className={`hf-chip ${
                        tool.risk_level === "medium" || tool.risk_level === "high"
                          ? "hf-chip-escalate"
                          : "hf-chip-pass"
                      }`}
                    >
                      risk: {tool.risk_level}
                    </span>
                    <span className="hf-chip hf-chip-plain font-mono">
                      timeout: {tool.timeout_seconds}s
                    </span>
                  </div>
                </div>
                <p className="mt-1.5 text-[var(--ink-2)]">{tool.description}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-[var(--muted)]">
                  <span>
                    <strong className="text-[var(--ink-2)]">Schema params:</strong>{" "}
                    {props.length > 0 ? props.join(", ") : "none"}
                  </span>
                  <span>
                    <strong className="text-[var(--ink-2)]">HITL:</strong>{" "}
                    {tool.requires_hitl ? "Required" : "Auto-allowed"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* External MCP Client Manager */}
      <div className="hf-card space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-[var(--muted)]" />
              <h2 className="hf-h2 mb-0">
                External MCP Servers ({mcpData?.servers.length ?? 0})
              </h2>
            </div>
            <p className="mt-1 text-xs text-[var(--muted)]">
              Newly registered MCP servers are untrusted by default (`pending_approval`) and cannot
              be queried until approved by an Admin or Business Owner.
            </p>
          </div>
          <button type="button" onClick={() => refreshRuntimeData()} className="hf-btn hf-btn-sm">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh MCP
          </button>
        </div>

        {canManage && (
          <form
            onSubmit={handleRegisterMcp}
            className="hf-subcard grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3"
          >
            <input
              type="text"
              required
              placeholder="Server slug (e.g. hr-calendar-mcp)"
              value={mcpForm.slug}
              onChange={(e) => setMcpForm((p) => ({ ...p, slug: e.target.value }))}
              className="hf-input bg-[var(--panel)]"
            />
            <input
              type="text"
              required
              placeholder="Display name"
              value={mcpForm.name}
              onChange={(e) => setMcpForm((p) => ({ ...p, name: e.target.value }))}
              className="hf-input bg-[var(--panel)]"
            />
            <select
              value={mcpForm.transport}
              onChange={(e) =>
                setMcpForm((p) => ({ ...p, transport: e.target.value as "stdio" | "sse" }))
              }
              className="hf-input bg-[var(--panel)]"
            >
              <option value="stdio">stdio (local command)</option>
              <option value="sse">sse (https endpoint)</option>
            </select>
            <input
              type="text"
              required
              placeholder={
                mcpForm.transport === "stdio"
                  ? "Executable (e.g. python, uvx — no shell wrappers)"
                  : "HTTPS SSE URL (non-private/SSRF checked)"
              }
              value={mcpForm.command_or_url}
              onChange={(e) => setMcpForm((p) => ({ ...p, command_or_url: e.target.value }))}
              className="hf-input bg-[var(--panel)]"
            />
            <input
              type="text"
              placeholder="Args comma-separated (optional)"
              value={mcpForm.args}
              onChange={(e) => setMcpForm((p) => ({ ...p, args: e.target.value }))}
              className="hf-input bg-[var(--panel)]"
            />
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Allowed env keys (optional)"
                value={mcpForm.env_keys}
                onChange={(e) => setMcpForm((p) => ({ ...p, env_keys: e.target.value }))}
                className="hf-input flex-1 bg-[var(--panel)]"
              />
              <button
                type="submit"
                disabled={registeringMcp}
                className="hf-btn hf-btn-primary hf-btn-sm shrink-0"
              >
                <Plus className="h-3.5 w-3.5" />
                Register
              </button>
            </div>
          </form>
        )}

        {!mcpData || mcpData.servers.length === 0 ? (
          <div className="hf-empty py-8">
            <strong>No external MCP servers</strong>
            Register a custom HR MCP server above to integrate tools under Admin approval.
          </div>
        ) : (
          <div className="space-y-3">
            {mcpData.servers.map((srv) => (
              <div key={srv.id} className="hf-subcard text-xs">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-bold text-[var(--ink)]">{srv.name}</span>
                      <span className="font-mono text-[11px] text-[var(--muted)]">
                        {srv.slug} &bull; {srv.transport}
                      </span>
                      <span
                        className={`hf-chip ${srv.is_approved ? "hf-chip-pass" : "hf-chip-escalate"}`}
                      >
                        {srv.approval_status}
                      </span>
                      <span
                        className={`hf-chip ${
                          srv.connection_status === "connected"
                            ? "hf-chip-pass"
                            : srv.connection_status === "unreachable"
                              ? "hf-chip-block"
                              : "hf-chip-plain"
                        }`}
                      >
                        conn: {srv.connection_status}
                      </span>
                    </div>
                    {srv.last_error && (
                      <p className="mt-1 text-[11px] text-[var(--block)]">{srv.last_error}</p>
                    )}
                  </div>

                  {canManage && (
                    <div className="flex flex-wrap gap-1.5">
                      {!srv.is_approved ? (
                        <button
                          type="button"
                          disabled={busyMcpId === srv.id}
                          onClick={() => handleApproval(srv.id, true)}
                          className="hf-btn hf-btn-primary hf-btn-sm"
                        >
                          <CheckCircle2 className="h-3 w-3" /> Approve
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={busyMcpId === srv.id}
                          onClick={() => handleApproval(srv.id, false)}
                          className="hf-btn hf-btn-danger hf-btn-sm"
                        >
                          <XCircle className="h-3 w-3" /> Block
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busyMcpId === srv.id || !srv.is_approved}
                        onClick={() => handleDiscoverTools(srv.id)}
                        className="hf-btn hf-btn-sm"
                      >
                        <ShieldCheck className="h-3 w-3" /> Discover &amp; Verify
                      </button>
                    </div>
                  )}
                </div>

                {srv.discovered_tools.length > 0 && (
                  <div className="mt-3 space-y-1.5 border-t border-[var(--line)] pt-3">
                    <div className="text-[11px] font-semibold text-[var(--ink-2)]">
                      Discovered Validated Tools ({srv.discovered_tools.length})
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {srv.discovered_tools.map((dt) => {
                        const perm = srv.tool_permissions?.[dt.name];
                        const isAllowed = perm?.allowed === true;
                        return (
                          <div
                            key={dt.name}
                            className="flex items-center justify-between gap-2 rounded-xl border border-[var(--line)] bg-[var(--panel)] px-3 py-2"
                          >
                            <div className="min-w-0">
                              <div className="font-mono font-semibold text-[var(--ink)]">
                                {dt.name}
                              </div>
                              <div className="truncate text-[11px] text-[var(--muted)]">
                                {dt.description}
                              </div>
                            </div>
                            <button
                              type="button"
                              disabled={!canManage || busyMcpId === srv.id}
                              onClick={() => handleToggleMcpToolPerm(srv.id, dt.name, !isAllowed)}
                              className={`hf-chip cursor-pointer border-0 disabled:opacity-50 ${
                                isAllowed ? "hf-chip-pass" : "hf-chip-plain"
                              }`}
                            >
                              {isAllowed ? "Allowed" : "Blocked"}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Existing Tenant Workflow Tool Permissions & Encrypted Secrets */}
      {uniqueTools.length === 0 ? (
        <div className="hf-card text-xs text-[var(--muted)]">
          No tool permissions initialized yet.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {uniqueTools.map((tool) => (
            <div key={tool.id} className="hf-card flex flex-col justify-between gap-4">
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Plug className="h-4 w-4 text-[var(--ink)]" />
                      <h2 className="text-sm font-bold text-[var(--ink)]">{tool.tool_name}</h2>
                    </div>
                    <p className="mt-0.5 font-mono text-[11px] text-[var(--muted)]">
                      {tool.tool_slug} &bull; {tool.execution_mode}
                      {tool.mcp_server_slug ? ` • ${tool.mcp_server_slug}` : ""}
                    </p>
                  </div>

                  <button
                    type="button"
                    disabled={!canManage}
                    onClick={() => toggleIntegrationPermission(tool.id, !tool.is_allowed)}
                    className={`hf-chip cursor-pointer border-0 disabled:opacity-50 ${
                      tool.is_allowed ? "hf-chip-pass" : "hf-chip-plain"
                    }`}
                  >
                    {tool.is_allowed ? "Allowed" : "Disabled"}
                  </button>
                </div>

                <p className="mt-2.5 text-xs leading-relaxed text-[var(--ink-2)]">
                  {tool.description}
                </p>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {tool.requires_hitl && (
                    <span className="hf-chip hf-chip-escalate">Requires HITL Sign-Off</span>
                  )}
                  <span className="hf-chip hf-chip-plain">
                    Used by: {tool.workflows.join(", ")}
                  </span>
                </div>
              </div>

              {tool.auth_scheme !== "none" && (
                <div className="space-y-2 border-t border-[var(--line)] pt-3">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-[var(--ink-2)]">
                      Encrypted Credential:
                    </span>
                    <span className="font-mono text-[var(--ink)]">
                      {tool.credential_status === "bound_encrypted"
                        ? tool.masked_secret_ref
                        : "Not bound"}
                    </span>
                  </div>

                  {canManage && (
                    <div className="flex gap-2">
                      <input
                        type="password"
                        value={secretInputs[tool.id] || ""}
                        onChange={(e) =>
                          setSecretInputs((prev) => ({ ...prev, [tool.id]: e.target.value }))
                        }
                        placeholder="Paste API key or OAuth token (Fernet encrypted)"
                        className="hf-input flex-1 py-1.5 text-xs"
                      />
                      <button
                        type="button"
                        disabled={
                          bindingId === tool.id || (secretInputs[tool.id] || "").trim().length < 4
                        }
                        onClick={() => handleBindSecret(tool.id)}
                        className="hf-btn hf-btn-primary hf-btn-sm shrink-0"
                      >
                        <KeyRound className="h-3.5 w-3.5" />
                        {bindingId === tool.id ? "Binding..." : "Bind"}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
