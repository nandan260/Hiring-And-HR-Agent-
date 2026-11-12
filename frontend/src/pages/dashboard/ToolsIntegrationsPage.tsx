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
    const map = new Map<string, typeof integrations[number] & { workflows: string[] }>();
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
      setLastActionError(err instanceof Error ? err.message : "Failed to update MCP tool permission");
    } finally {
      setBusyMcpId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Tools and Integrations
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Manage schema-enforced HR tools, external MCP client connections, approval gates, and
            Fernet-encrypted credentials per tenant.
          </p>
        </div>
        {!canManage && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">
            <Lock className="h-3.5 w-3.5" />
            Read-only (Admin/Owner required to modify)
          </span>
        )}
      </div>

      <div className="rounded-xl border border-indigo-200/80 bg-indigo-50/70 px-4 py-3 text-xs text-indigo-950">
        <div className="flex items-start gap-2">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
          <span>
            <strong>Runtime Security Policy:</strong> Resume PDF/DOCX parsing and weighted ranking
            execute inside isolated tenant sandboxes. Web inspection runs inside ephemeral Playwright
            contexts with SSRF and download blocking. External MCP servers require explicit Admin
            approval before discovery or execution.
          </span>
        </div>
      </div>

      {/* Schema-Documented Core HR Tool Registry */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <Wrench className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Schema-Documented HR Tool Registry ({structuredTools.length} Core Tools)
          </h2>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {structuredTools.map((tool) => {
            const props = Object.keys(
              ((tool.input_schema as Record<string, unknown>)?.properties as Record<string, unknown>) || {}
            );
            return (
              <div
                key={tool.tool_id}
                className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="font-bold text-slate-900">{tool.name}</span>
                    <span className="ml-2 font-mono text-[11px] text-slate-500">
                      {tool.tool_id}
                    </span>
                  </div>
                  <div className="flex gap-1.5">
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        tool.risk_level === "medium" || tool.risk_level === "high"
                          ? "bg-amber-100 text-amber-900"
                          : "bg-emerald-50 text-emerald-700"
                      }`}
                    >
                      risk: {tool.risk_level}
                    </span>
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-[10px] font-mono text-slate-700">
                      timeout: {tool.timeout_seconds}s
                    </span>
                  </div>
                </div>
                <p className="mt-1.5 text-slate-600">{tool.description}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-500">
                  <span>
                    <strong>Schema params:</strong>{" "}
                    {props.length > 0 ? props.join(", ") : "none"}
                  </span>
                  <span>
                    <strong>HITL:</strong> {tool.requires_hitl ? "Required" : "Auto-allowed"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* External MCP Client Manager */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-indigo-600" />
              <h2 className="font-display text-base font-bold text-slate-900">
                External MCP Servers ({mcpData?.servers.length ?? 0})
              </h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Newly registered MCP servers are untrusted by default (`pending_approval`) and cannot
              be queried until approved by an Admin or Business Owner.
            </p>
          </div>
          <button
            type="button"
            onClick={() => refreshRuntimeData()}
            className="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh MCP
          </button>
        </div>

        {canManage && (
          <form
            onSubmit={handleRegisterMcp}
            className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs sm:grid-cols-2 lg:grid-cols-3"
          >
            <input
              type="text"
              required
              placeholder="Server slug (e.g. hr-calendar-mcp)"
              value={mcpForm.slug}
              onChange={(e) => setMcpForm((p) => ({ ...p, slug: e.target.value }))}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-indigo-400"
            />
            <input
              type="text"
              required
              placeholder="Display name"
              value={mcpForm.name}
              onChange={(e) => setMcpForm((p) => ({ ...p, name: e.target.value }))}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-indigo-400"
            />
            <select
              value={mcpForm.transport}
              onChange={(e) =>
                setMcpForm((p) => ({ ...p, transport: e.target.value as "stdio" | "sse" }))
              }
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-indigo-400"
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
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-indigo-400"
            />
            <input
              type="text"
              placeholder="Args comma-separated (optional)"
              value={mcpForm.args}
              onChange={(e) => setMcpForm((p) => ({ ...p, args: e.target.value }))}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-indigo-400"
            />
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Allowed env keys (optional)"
                value={mcpForm.env_keys}
                onChange={(e) => setMcpForm((p) => ({ ...p, env_keys: e.target.value }))}
                className="flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 outline-none focus:border-indigo-400"
              />
              <button
                type="submit"
                disabled={registeringMcp}
                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-2 font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                <Plus className="h-3.5 w-3.5" />
                Register
              </button>
            </div>
          </form>
        )}

        {(!mcpData || mcpData.servers.length === 0) ? (
          <p className="text-xs text-slate-500">No external MCP servers registered for this tenant.</p>
        ) : (
          <div className="space-y-3">
            {mcpData.servers.map((srv) => (
              <div
                key={srv.id}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-slate-900">{srv.name}</span>
                      <span className="font-mono text-[11px] text-slate-500">
                        {srv.slug} • {srv.transport}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          srv.is_approved
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-100 text-amber-900"
                        }`}
                      >
                        {srv.approval_status}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          srv.connection_status === "connected"
                            ? "bg-indigo-50 text-indigo-700"
                            : srv.connection_status === "unreachable"
                              ? "bg-rose-50 text-rose-700"
                              : "bg-slate-200 text-slate-700"
                        }`}
                      >
                        conn: {srv.connection_status}
                      </span>
                    </div>
                    {srv.last_error && (
                      <p className="mt-1 text-[11px] text-rose-600">{srv.last_error}</p>
                    )}
                  </div>

                  {canManage && (
                    <div className="flex flex-wrap gap-1.5">
                      {!srv.is_approved ? (
                        <button
                          type="button"
                          disabled={busyMcpId === srv.id}
                          onClick={() => handleApproval(srv.id, true)}
                          className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                        >
                          <CheckCircle2 className="h-3 w-3" /> Approve
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={busyMcpId === srv.id}
                          onClick={() => handleApproval(srv.id, false)}
                          className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50"
                        >
                          <XCircle className="h-3 w-3" /> Block
                        </button>
                      )}
                      <button
                        type="button"
                        disabled={busyMcpId === srv.id || !srv.is_approved}
                        onClick={() => handleDiscoverTools(srv.id)}
                        className="inline-flex items-center gap-1 rounded-lg bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
                      >
                        <ShieldCheck className="h-3 w-3" /> Discover & Verify
                      </button>
                    </div>
                  )}
                </div>

                {srv.discovered_tools.length > 0 && (
                  <div className="mt-3 space-y-1.5 border-t border-slate-200 pt-3">
                    <div className="text-[11px] font-semibold text-slate-700">
                      Discovered Validated Tools ({srv.discovered_tools.length})
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {srv.discovered_tools.map((dt) => {
                        const perm = srv.tool_permissions?.[dt.name];
                        const isAllowed = perm?.allowed === true;
                        return (
                          <div
                            key={dt.name}
                            className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2"
                          >
                            <div className="min-w-0">
                              <div className="font-mono font-semibold text-slate-800">{dt.name}</div>
                              <div className="truncate text-[10px] text-slate-500">
                                {dt.description}
                              </div>
                            </div>
                            <button
                              type="button"
                              disabled={!canManage || busyMcpId === srv.id}
                              onClick={() => handleToggleMcpToolPerm(srv.id, dt.name, !isAllowed)}
                              className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold disabled:opacity-50 ${
                                isAllowed
                                  ? "bg-emerald-50 text-emerald-700"
                                  : "bg-slate-100 text-slate-600"
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
        <div className="rounded-2xl border border-slate-200 bg-white p-6 text-xs text-slate-500">
          No tool permissions initialized yet.
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {uniqueTools.map((tool) => (
            <div
              key={tool.id}
              className="flex flex-col justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Plug className="h-4 w-4 text-indigo-600" />
                      <h2 className="font-display text-sm font-bold text-slate-900">
                        {tool.tool_name}
                      </h2>
                    </div>
                    <p className="mt-0.5 font-mono text-[11px] text-slate-500">
                      {tool.tool_slug} • {tool.execution_mode}
                      {tool.mcp_server_slug ? ` • ${tool.mcp_server_slug}` : ""}
                    </p>
                  </div>

                  <button
                    type="button"
                    disabled={!canManage}
                    onClick={() => toggleIntegrationPermission(tool.id, !tool.is_allowed)}
                    className={`rounded-full px-3 py-1 text-[11px] font-semibold transition disabled:opacity-50 ${
                      tool.is_allowed
                        ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                        : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  >
                    {tool.is_allowed ? "Allowed" : "Disabled"}
                  </button>
                </div>

                <p className="mt-2 text-xs leading-relaxed text-slate-600">{tool.description}</p>

                <div className="mt-2 flex flex-wrap gap-1.5">
                  {tool.requires_hitl && (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                      Requires HITL Sign-Off
                    </span>
                  )}
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">
                    Used by: {tool.workflows.join(", ")}
                  </span>
                </div>
              </div>

              {tool.auth_scheme !== "none" && (
                <div className="space-y-2 border-t border-slate-100 pt-3">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-slate-700">Encrypted Credential:</span>
                    <span className="font-mono text-slate-600">
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
                        className="flex-1 rounded-xl border border-slate-200 px-3 py-1.5 text-xs outline-none focus:border-indigo-400"
                      />
                      <button
                        type="button"
                        disabled={
                          bindingId === tool.id || (secretInputs[tool.id] || "").trim().length < 4
                        }
                        onClick={() => handleBindSecret(tool.id)}
                        className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
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
