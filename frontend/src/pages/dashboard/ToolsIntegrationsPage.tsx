import React, { useState } from "react";
import { Badge } from "../../components/common/Badge";
import { Modal } from "../../components/common/Modal";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { UnifiedIntegrationItem } from "../../types/agent";

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

  const [tab, setTab] = useState<"permissions" | "tools" | "mcp">("permissions");
  const [selectedItem, setSelectedItem] = useState<UnifiedIntegrationItem | null>(null);
  const [secretInput, setSecretInput] = useState("");
  const [savingSecret, setSavingSecret] = useState(false);

  const [mcpName, setMcpName] = useState("");
  const [mcpSlug, setMcpSlug] = useState("");
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpBusy, setMcpBusy] = useState(false);

  const canManage = session.role === "business_owner" || session.role === "business_admin";
  const mcpServers = mcpData?.servers || [];

  const handleSaveSecret = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem || !secretInput.trim()) return;
    setSavingSecret(true);
    await bindIntegrationCredential(selectedItem.id, secretInput.trim());
    setSavingSecret(false);
    setSelectedItem(null);
    setSecretInput("");
  };

  const handleRegisterMcp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mcpName.trim() || !mcpSlug.trim() || !mcpUrl.trim()) return;
    setMcpBusy(true);
    try {
      await apiClient.registerMcpServer({
        name: mcpName.trim(),
        slug: mcpSlug.trim(),
        transport: mcpUrl.startsWith("http") ? "sse" : "stdio",
        command_or_url: mcpUrl.trim(),
      });
      setMcpName("");
      setMcpSlug("");
      setMcpUrl("");
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to register MCP server.");
    } finally {
      setMcpBusy(false);
    }
  };

  const handleMcpAction = async (action: () => Promise<unknown>) => {
    setMcpBusy(true);
    try {
      await action();
      await refreshRuntimeData();
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "MCP operation failed.");
    } finally {
      setMcpBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Tools &amp; MCP</h1>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("permissions")}
            className={`hf-tab ${tab === "permissions" ? "active" : ""}`}
          >
            Permissions ({integrations.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("tools")}
            className={`hf-tab ${tab === "tools" ? "active" : ""}`}
          >
            Registry ({structuredTools.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("mcp")}
            className={`hf-tab ${tab === "mcp" ? "active" : ""}`}
          >
            MCP ({mcpServers.length})
          </button>
        </div>
      </div>

      {tab === "permissions" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Workflow</th>
                  <th>Tool</th>
                  <th>Credential</th>
                  <th>Allowed</th>
                  <th className="num">Actions</th>
                </tr>
              </thead>
              <tbody>
                {integrations.map((item) => (
                  <tr key={item.id}>
                    <td className="font-mono text-xs text-[var(--fg)]">{item.workflow_slug}</td>
                    <td>{item.tool_name}</td>
                    <td>
                      <Badge variant={item.credential_status === "configured" ? "emerald" : "slate"}>
                        {item.credential_status}
                      </Badge>
                    </td>
                    <td>{item.is_allowed ? "Yes" : "No"}</td>
                    <td className="num">
                      <div className="flex justify-end gap-1.5">
                        <button
                          type="button"
                          disabled={!canManage}
                          onClick={() => toggleIntegrationPermission(item.id, !item.is_allowed)}
                          className="hf-btn hf-btn-sm"
                        >
                          {item.is_allowed ? "Disable" : "Enable"}
                        </button>
                        <button
                          type="button"
                          disabled={!canManage}
                          onClick={() => setSelectedItem(item)}
                          className="hf-btn hf-btn-sm"
                        >
                          Key
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "tools" && (
        <div className="hf-card flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Tool ID</th>
                  <th>Name</th>
                  <th>Risk</th>
                  <th className="num">Timeout</th>
                </tr>
              </thead>
              <tbody>
                {structuredTools.map((tool) => (
                  <tr key={tool.tool_id}>
                    <td className="font-mono text-xs text-[var(--fg)]">{tool.tool_id}</td>
                    <td className="font-medium text-[var(--fg)]">{tool.name}</td>
                    <td>
                      <Badge variant="slate">{tool.risk_level}</Badge>
                    </td>
                    <td className="num font-mono text-xs">{tool.timeout_seconds}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "mcp" && (
        <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
          <form
            onSubmit={handleRegisterMcp}
            className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 lg:col-span-4"
          >
            <h2 className="hf-h2">Register Server</h2>
            <div className="hf-field">
              <label>Name</label>
              <input
                type="text"
                value={mcpName}
                onChange={(e) => setMcpName(e.target.value)}
                required
                className="hf-input"
                disabled={!canManage}
              />
            </div>
            <div className="hf-field">
              <label>Slug</label>
              <input
                type="text"
                value={mcpSlug}
                onChange={(e) => setMcpSlug(e.target.value)}
                required
                className="hf-input"
                disabled={!canManage}
              />
            </div>
            <div className="hf-field">
              <label>Endpoint / Command</label>
              <input
                type="text"
                value={mcpUrl}
                onChange={(e) => setMcpUrl(e.target.value)}
                required
                className="hf-input"
                disabled={!canManage}
              />
            </div>
            <button
              type="submit"
              disabled={!canManage || mcpBusy}
              className="hf-btn hf-btn-primary mt-auto w-full"
            >
              Register MCP
            </button>
          </form>

          <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-8">
            <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
              {mcpServers.length === 0 ? (
                <div className="hf-empty">No external MCP servers registered.</div>
              ) : (
                mcpServers.map((srv) => (
                  <div key={srv.id} className="hf-subcard flex items-center justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-[var(--fg)]">{srv.name}</span>
                        <Badge variant={srv.is_approved ? "emerald" : "amber"}>
                          {srv.is_approved ? "Approved" : srv.approval_status}
                        </Badge>
                      </div>
                      <div className="font-mono text-[11px] text-[var(--muted)]">
                        {srv.transport} / {srv.command_or_url}
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        type="button"
                        disabled={!canManage || mcpBusy}
                        onClick={() =>
                          handleMcpAction(() => apiClient.setMcpApproval(srv.id, !srv.is_approved))
                        }
                        className="hf-btn hf-btn-sm"
                      >
                        {srv.is_approved ? "Revoke" : "Approve"}
                      </button>
                      <button
                        type="button"
                        disabled={!canManage || mcpBusy}
                        onClick={() => handleMcpAction(() => apiClient.discoverMcpTools(srv.id))}
                        className="hf-btn hf-btn-sm"
                      >
                        Discover
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      <Modal
        isOpen={Boolean(selectedItem)}
        onClose={() => {
          setSelectedItem(null);
          setSecretInput("");
        }}
        title={`Bind Key: ${selectedItem?.tool_name || ""}`}
      >
        <form onSubmit={handleSaveSecret} className="space-y-3">
          <div className="hf-field">
            <label>API Key / Secret</label>
            <input
              type="password"
              value={secretInput}
              onChange={(e) => setSecretInput(e.target.value)}
              required
              className="hf-input"
            />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setSelectedItem(null)} className="hf-btn hf-btn-sm">
              Cancel
            </button>
            <button type="submit" disabled={savingSecret} className="hf-btn hf-btn-primary hf-btn-sm">
              {savingSecret ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
