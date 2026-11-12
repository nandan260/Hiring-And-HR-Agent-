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
        <h1 className="font-display text-2xl font-bold text-slate-900">Knowledge Base</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload company employee handbooks, hiring rubrics, leveling guides, and resumes with
          tenant-isolated pgvector indexing and role-based access filtering.
        </p>
      </div>

      {canManage && (
        <form
          onSubmit={handleUpload}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
        >
          <div className="flex items-center gap-2">
            <Upload className="h-4 w-4 text-indigo-600" />
            <h2 className="font-display text-base font-bold text-slate-900">
              Upload &amp; Index HR Document
            </h2>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div>
              <label className="text-xs font-semibold text-slate-700">Document Title</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., 2026 Parental Leave Policy"
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">Document Type</label>
              <select
                value={sourceType}
                onChange={(e) => setSourceType(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
              >
                <option value="handbook">Employee Handbook</option>
                <option value="policy">HR Policy</option>
                <option value="rubric">Hiring Rubric</option>
                <option value="jd_template">JD Leveling Guide</option>
                <option value="resume">Candidate Resume</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">Minimum RBAC Access</label>
              <select
                value={minRoleAccess}
                onChange={(e) => setMinRoleAccess(e.target.value as UserRole)}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
              >
                <option value="business_employee">All Employees (business_employee)</option>
                <option value="business_admin">HR Admins Only (business_admin)</option>
                <option value="business_owner">Owners Only (business_owner)</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-700">Primary HR Domain</label>
              <select
                value={workflowSlug}
                onChange={(e) => setWorkflowSlug(e.target.value)}
                className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
              >
                <option value="hr-policy-support">Employee Policy Support</option>
                <option value="recruitment-screening">Recruitment &amp; Screening</option>
                <option value="jd-generator">Job Description Generator</option>
                <option value="employee-onboarding">Employee Onboarding</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <label className="flex flex-1 cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-2.5 text-xs text-slate-600 hover:border-indigo-400">
              <FileText className="h-4 w-4 text-indigo-600" />
              <span className="truncate">
                {file ? `${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)` : "Choose PDF, DOCX, TXT, MD, or CSV file..."}
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
              className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
            >
              {uploading ? "Uploading & Indexing..." : "Upload & Index"}
            </button>
          </div>

          {statusMsg && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3.5 py-2 text-xs font-medium text-emerald-800">
              {statusMsg}
            </div>
          )}
          {errorMsg && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2 text-xs font-medium text-rose-800">
              {errorMsg}
            </div>
          )}
        </form>
      )}

      {/* Documents List */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Indexed Workspace Documents ({knowledgeDocs.length})
          </h2>
        </div>

        {knowledgeDocs.length === 0 ? (
          <p className="mt-4 text-xs text-slate-500">
            No accessible documents found for role <code>{session.role}</code>.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-2.5 pr-4">Title &amp; File</th>
                  <th className="py-2.5 pr-4">Domain</th>
                  <th className="py-2.5 pr-4">Min Role</th>
                  <th className="py-2.5 pr-4">Chunks</th>
                  <th className="py-2.5 pr-4">Status</th>
                  <th className="py-2.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {knowledgeDocs.map((doc) => (
                  <tr key={doc.id}>
                    <td className="py-3 pr-4">
                      <div className="font-semibold text-slate-900">{doc.title}</div>
                      <div className="font-mono text-[11px] text-slate-500">
                        {doc.original_filename} ({Math.max(1, Math.round(doc.file_size_bytes / 1024))} KB)
                      </div>
                    </td>
                    <td className="py-3 pr-4">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                        {doc.source_type}
                      </span>
                    </td>
                    <td className="py-3 pr-4 font-mono text-[11px] text-slate-700">
                      {doc.min_role_access}
                    </td>
                    <td className="py-3 pr-4 font-mono text-slate-600">{doc.chunk_count}</td>
                    <td className="py-3 pr-4">
                      <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                        {doc.status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <div className="inline-flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleOpenMarkdown(doc.id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[11px] font-medium text-indigo-700 hover:bg-indigo-100"
                        >
                          <FileCode className="h-3 w-3" />
                          .md
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            apiClient.downloadHrKnowledge(doc.id, doc.original_filename)
                          }
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                        >
                          <Download className="h-3 w-3" />
                          Download
                        </button>
                        {canManage && (
                          <button
                            type="button"
                            onClick={() => deleteKnowledgeDoc(doc.id)}
                            className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-[11px] font-medium text-rose-700 hover:bg-rose-100"
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
        <div className="rounded-2xl border border-indigo-200 bg-white p-6 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileCode className="h-4 w-4 text-indigo-600" />
              <h3 className="font-display text-sm font-bold text-slate-900">
                Obsidian Markdown Note: {mdPreview.filename}
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setMdPreview(null)}
              className="text-xs font-medium text-slate-500 hover:text-slate-800"
            >
              Close
            </button>
          </div>
          {mdPreview.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {mdPreview.tags.map((t) => (
                <span key={t} className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
                  #{t}
                </span>
              ))}
            </div>
          )}
          <pre className="max-h-72 overflow-auto rounded-xl bg-slate-950 p-4 text-[11px] text-slate-100">
            {mdPreview.markdown}
          </pre>
        </div>
      )}

      {/* Lightweight PostgreSQL-backed HR Knowledge Graph */}
      {graphData && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Network className="h-4 w-4 text-indigo-600" />
              <h2 className="font-display text-base font-bold text-slate-900">
                Tenant HR Knowledge &amp; Skill Graph
              </h2>
            </div>
            <span className="text-xs text-slate-500">
              {graphData.summary.total_nodes} nodes • {graphData.summary.total_edges} edges (
              {graphData.pii_included ? "full workspace" : "PII-masked view"})
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="text-[11px] font-semibold uppercase text-slate-500">
                Graph Nodes (Sample)
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {graphData.nodes.slice(0, 18).map((n) => (
                  <span
                    key={n.id}
                    className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[11px] text-slate-700"
                  >
                    <strong className="text-indigo-700">{n.type}:</strong> {n.label}
                  </span>
                ))}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="text-[11px] font-semibold uppercase text-slate-500">
                Graph Relationships ([[Wikilinks]], Skills, Tags)
              </div>
              <ul className="mt-2 space-y-1 text-[11px] text-slate-700">
                {graphData.edges.slice(0, 10).map((edge, idx) => (
                  <li key={idx} className="truncate font-mono">
                    {edge.source} —[{edge.relation}]→ {edge.target}
                  </li>
                ))}
                {graphData.edges.length === 0 && (
                  <li className="text-slate-500">Upload documents with #tags or [[wikilinks]] to populate graph edges.</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
