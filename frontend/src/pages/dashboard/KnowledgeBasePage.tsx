import React, { useEffect, useState } from "react";
import { BookOpen, Download, FileCode, FileText, Network, Trash2, Upload } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { KnowledgeGraphPayload, ObsidianMarkdownExport, UserRole } from "../../types/agent";

export const KnowledgeBasePage: React.FC = () => {
  const { knowledgeDocs, uploadKnowledgeDoc, deleteKnowledgeDoc, session } = useApp();

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("handbook");
  const [minRoleAccess, setMinRoleAccess] = useState<UserRole>("business_employee");
  const [workflowSlug, setWorkflowSlug] = useState("hr-policy-support");
  const [uploading, setUploading] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [mdPreview, setMdPreview] = useState<ObsidianMarkdownExport | null>(null);
  const [graphData, setGraphData] = useState<KnowledgeGraphPayload | null>(null);

  const loadGraph = async () => {
    try {
      const g = await apiClient.getKnowledgeGraph();
      setGraphData(g);
    } catch {
      // ignore if offline
    }
  };

  useEffect(() => {
    loadGraph();
  }, [knowledgeDocs.length]);

  const canManage =
    session.role === "business_owner" ||
    session.role === "business_admin" ||
    session.role === "platform_admin";

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title.trim()) return;
    setUploading(true);
    setStatusMsg(null);
    setErrorMsg(null);

    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title.trim());
    fd.append("source_type", sourceType);
    fd.append("min_role_access", minRoleAccess);
    fd.append("workflow_slug", workflowSlug);

    const res = await uploadKnowledgeDoc(fd);
    setUploading(false);
    if (res.ok && res.doc) {
      setStatusMsg(
        `Indexed "${res.doc.title}" (${res.doc.chunk_count} pgvector chunk(s)) cleanly.`
      );
      setTitle("");
      setFile(null);
      await loadGraph();
    } else if (!res.ok) {
      setErrorMsg(res.error || "Document blocked by security scan or validation.");
    }
  };

  const handleOpenMarkdown = async (docId: string) => {
    try {
      const data = await apiClient.getKnowledgeMarkdown(docId);
      setMdPreview(data);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load Obsidian Markdown");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="hf-h1">Knowledge Base</h1>
        <p className="hf-lede">
          Upload company employee handbooks, hiring rubrics, leveling guides, and resumes with
          tenant-isolated pgvector indexing and role-based access filtering.
        </p>
      </div>

      {canManage && (
        <form onSubmit={handleUpload} className="hf-card space-y-4">
          <div className="flex items-center gap-2">
            <Upload className="h-4 w-4 text-[var(--pass)]" />
            <h2 className="hf-h2 mb-0">Upload &amp; Index HR Document</h2>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="hf-field">
              <label>Document Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., 2026 Parental Leave Policy"
                className="hf-input"
              />
            </div>

            <div className="hf-field">
              <label>Document Type</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="hf-input"
              >
                <option value="handbook">Employee Handbook</option>
                <option value="policy">HR Policy</option>
                <option value="rubric">Hiring Rubric</option>
                <option value="jd_template">JD Leveling Guide</option>
                <option value="resume">Candidate Resume</option>
              </select>
            </div>

            <div className="hf-field">
              <label>Minimum RBAC Access</label>
              <select
                value={minRoleAccess}
                onChange={(e) => setMinRoleAccess(e.target.value as UserRole)}
                className="hf-input"
              >
                <option value="business_employee">All Employees (business_employee)</option>
                <option value="business_admin">HR Admins Only (business_admin)</option>
                <option value="business_owner">Owners Only (business_owner)</option>
              </select>
            </div>

            <div className="hf-field">
              <label>Primary HR Domain</label>
              <select
                value={workflowSlug}
                onChange={(e) => setWorkflowSlug(e.target.value)}
                className="hf-input"
              >
                <option value="hr-policy-support">Employee Policy Support</option>
                <option value="recruitment-screening">Recruitment &amp; Screening</option>
                <option value="jd-generator">Job Description Generator</option>
                <option value="employee-onboarding">Employee Onboarding</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <label className="flex flex-1 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-[var(--line)] bg-[var(--field)] px-4 py-2.5 text-xs text-[var(--ink-2)] transition hover:border-[var(--muted)]">
              <FileText className="h-4 w-4 text-[var(--ink)]" />
              <span className="truncate">
                {file
                  ? `${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)`
                  : "Choose PDF, DOCX, TXT, MD, or CSV file..."}
              </span>
              <input
                type="file"
                required
                accept=".pdf,.docx,.txt,.md,.csv"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>

            <button
              type="submit"
              disabled={uploading || !file || !title.trim()}
              className="hf-btn hf-btn-primary"
            >
              {uploading ? "Uploading & Indexing..." : "Upload & Index"}
            </button>
          </div>

          {statusMsg && (
            <div className="rounded-xl border border-[color:var(--pass-soft)] bg-[var(--pass-soft)] px-3.5 py-2 text-xs font-medium text-[var(--pass)]">
              {statusMsg}
            </div>
          )}
          {errorMsg && (
            <div className="rounded-xl border border-[color:var(--block-soft)] bg-[var(--block-soft)] px-3.5 py-2 text-xs font-medium text-[var(--block)]">
              {errorMsg}
            </div>
          )}
        </form>
      )}

      {/* Documents List */}
      <div className="hf-card">
        <div className="mb-4 flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-[var(--muted)]" />
          <h2 className="hf-h2 mb-0">Indexed Workspace Documents ({knowledgeDocs.length})</h2>
        </div>

        {knowledgeDocs.length === 0 ? (
          <div className="hf-empty">
            <strong>No accessible documents</strong>
            No accessible documents found for role <code>{session.role}</code>.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Title &amp; File</th>
                  <th>Domain</th>
                  <th>Min Role</th>
                  <th className="num">Chunks</th>
                  <th>Status</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {knowledgeDocs.map((doc) => (
                  <tr key={doc.id}>
                    <td>
                      <div className="font-semibold text-[var(--ink)]">{doc.title}</div>
                      <div className="font-mono text-[11px] text-[var(--muted)]">
                        {doc.original_filename} (
                        {Math.max(1, Math.round(doc.file_size_bytes / 1024))} KB)
                      </div>
                    </td>
                    <td>
                      <span className="hf-chip hf-chip-plain">{doc.source_type}</span>
                    </td>
                    <td className="font-mono text-xs">{doc.min_role_access}</td>
                    <td className="num font-mono">{doc.chunk_count}</td>
                    <td>
                      <span className="hf-chip hf-chip-pass">{doc.status}</span>
                    </td>
                    <td className="text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleOpenMarkdown(doc.id)}
                          className="hf-btn hf-btn-sm"
                        >
                          <FileCode className="h-3 w-3" />
                          .md
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            apiClient.downloadHrKnowledge(doc.id, doc.original_filename)
                          }
                          className="hf-btn hf-btn-sm"
                        >
                          <Download className="h-3 w-3" />
                          Download
                        </button>
                        {canManage && (
                          <button
                            type="button"
                            onClick={() => deleteKnowledgeDoc(doc.id)}
                            className="hf-btn hf-btn-danger hf-btn-sm"
                          >
                            <Trash2 className="h-3 w-3" />
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Obsidian Markdown Preview Drawer */}
      {mdPreview && (
        <div className="hf-card space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode className="h-4 w-4 text-[var(--pass)]" />
              <h3 className="text-sm font-bold text-[var(--ink)]">
                Obsidian Markdown Note: {mdPreview.filename}
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setMdPreview(null)}
              className="hf-btn hf-btn-sm"
            >
              Close
            </button>
          </div>
          {mdPreview.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {mdPreview.tags.map((t) => (
                <span key={t} className="hf-chip hf-chip-plain">
                  #{t}
                </span>
              ))}
            </div>
          )}
          <pre className="max-h-72 overflow-auto rounded-xl border border-[var(--line)] bg-[var(--field)] p-4 font-mono text-xs text-[var(--ink)]">
            {mdPreview.markdown}
          </pre>
        </div>
      )}

      {/* Lightweight PostgreSQL-backed HR Knowledge Graph */}
      {graphData && (
        <div className="hf-card space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4 text-[var(--muted)]" />
              <h2 className="hf-h2 mb-0">Tenant HR Knowledge &amp; Skill Graph</h2>
            </div>
            <span className="text-xs text-[var(--muted)]">
              {graphData.summary.total_nodes} nodes &bull; {graphData.summary.total_edges} edges (
              {graphData.pii_included ? "full workspace" : "PII-masked view"})
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="hf-subcard">
              <div className="text-[11px] font-semibold uppercase text-[var(--muted)]">
                Graph Nodes (Sample)
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {graphData.nodes.slice(0, 18).map((n) => (
                  <span
                    key={n.id}
                    className="rounded-lg border border-[var(--line)] bg-[var(--panel)] px-2 py-1 text-[11px] text-[var(--ink-2)]"
                  >
                    <strong className="text-[var(--ink)]">{n.type}:</strong> {n.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="hf-subcard">
              <div className="text-[11px] font-semibold uppercase text-[var(--muted)]">
                Graph Relationships ([[Wikilinks]], Skills, Tags)
              </div>
              <ul className="mt-2 space-y-1 text-[11px] text-[var(--ink-2)]">
                {graphData.edges.slice(0, 10).map((edge, idx) => (
                  <li key={idx} className="truncate font-mono">
                    {edge.source} &mdash;[{edge.relation}]&rarr; {edge.target}
                  </li>
                ))}
                {graphData.edges.length === 0 && (
                  <li className="text-[var(--muted)]">
                    Upload documents with #tags or [[wikilinks]] to populate graph edges.
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
