import React, { useEffect, useState } from "react";
import { Badge } from "../../components/common/Badge";
import { useApp } from "../../context/AppContext";
import { apiClient } from "../../services/apiClient";
import type { KnowledgeGraphPayload, ObsidianMarkdownExport } from "../../types/agent";

export const KnowledgeBasePage: React.FC = () => {
  const { knowledgeDocs, uploadKnowledgeDoc, deleteKnowledgeDoc, session } = useApp();
  const [tab, setTab] = useState<"docs" | "markdown" | "graph">("docs");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<"hr_policy" | "job_description" | "resume" | "general">(
    "hr_policy"
  );
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [graphData, setGraphData] = useState<KnowledgeGraphPayload | null>(null);
  const [markdownPreview, setMarkdownPreview] = useState<ObsidianMarkdownExport | null>(null);
  const canManage = session.role === "business_owner" || session.role === "business_admin";

  const loadGraph = async () => {
    try {
      const g = await apiClient.getKnowledgeGraph();
      setGraphData(g);
    } catch {
      setGraphData(null);
    }
  };

  useEffect(() => {
    if (tab === "graph" && !graphData) {
      loadGraph();
    }
  }, [tab, graphData]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("category", category);
    if (title.trim()) fd.append("title", title.trim());
    const res = await uploadKnowledgeDoc(fd);
    setUploading(false);
    if (res.ok) {
      setTitle("");
      setFile(null);
      setMsg("Document indexed.");
    } else {
      setMsg(res.error || "Upload failed.");
    }
  };

  const handlePreviewMarkdown = async (docId: string) => {
    try {
      const md = await apiClient.getKnowledgeMarkdown(docId);
      setMarkdownPreview(md);
      setTab("markdown");
    } catch {
      setMsg("Failed to export markdown.");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Knowledge Base ({knowledgeDocs.length})</h1>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("docs")}
            className={`hf-tab ${tab === "docs" ? "active" : ""}`}
          >
            Documents
          </button>
          <button
            type="button"
            onClick={() => setTab("markdown")}
            className={`hf-tab ${tab === "markdown" ? "active" : ""}`}
          >
            Markdown
          </button>
          <button
            type="button"
            onClick={() => setTab("graph")}
            className={`hf-tab ${tab === "graph" ? "active" : ""}`}
          >
            Graph
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
        <form
          onSubmit={handleUpload}
          className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 overflow-y-auto lg:col-span-4"
        >
          <h2 className="hf-h2">Upload Document</h2>
          <div className="hf-field">
            <label>Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Document title"
              className="hf-input"
              disabled={!canManage}
            />
          </div>
          <div className="hf-field">
            <label>Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value as typeof category)}
              className="hf-input"
              disabled={!canManage}
            >
              <option value="hr_policy">HR Policy</option>
              <option value="job_description">Job Description</option>
              <option value="resume">Candidate Resume</option>
              <option value="general">General</option>
            </select>
          </div>
          <div className="hf-field">
            <label>File</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md,.csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              disabled={!canManage}
              className="text-xs text-[var(--muted)] file:mr-2 file:rounded-[var(--r-field)] file:border file:border-[var(--border)] file:bg-[var(--surface)] file:px-2.5 file:py-1 file:text-xs file:font-medium file:text-[var(--fg)]"
            />
          </div>
          {msg && <div className="text-xs text-[var(--fg)]">{msg}</div>}
          <button
            type="submit"
            disabled={!canManage || uploading || !file}
            className="hf-btn hf-btn-primary mt-auto w-full"
          >
            {uploading ? "Uploading..." : "Upload & Index"}
          </button>
        </form>

        <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-8">
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "docs" &&
              (knowledgeDocs.length === 0 ? (
                <div className="hf-empty">No documents indexed.</div>
              ) : (
                <table className="hf-rows">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Source</th>
                      <th>Status</th>
                      <th className="num">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {knowledgeDocs.map((doc) => (
                      <tr key={doc.id}>
                        <td>
                          <div className="font-medium text-[var(--fg)]">{doc.title}</div>
                          <div className="font-mono text-[11px] text-[var(--muted)]">
                            {doc.original_filename}
                          </div>
                        </td>
                        <td className="font-mono text-xs">{doc.source_type}</td>
                        <td>
                          <Badge variant={doc.status === "indexed" ? "emerald" : "slate"}>
                            {doc.status}
                          </Badge>
                        </td>
                        <td className="num">
                          <div className="flex justify-end gap-1.5">
                            <button
                              type="button"
                              onClick={() => handlePreviewMarkdown(doc.id)}
                              className="hf-btn hf-btn-sm"
                            >
                              Markdown
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                apiClient.downloadHrKnowledge(doc.id, doc.original_filename)
                              }
                              className="hf-btn hf-btn-sm"
                            >
                              Download
                            </button>
                            {canManage && (
                              <button
                                type="button"
                                onClick={() => deleteKnowledgeDoc(doc.id)}
                                className="hf-btn hf-btn-danger hf-btn-sm"
                              >
                                Delete
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ))}

            {tab === "markdown" &&
              (!markdownPreview ? (
                <div className="hf-empty">Select Markdown on any document row to preview.</div>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-[var(--fg)]">
                      {markdownPreview.filename}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        navigator.clipboard?.writeText(markdownPreview.markdown)
                      }
                      className="hf-btn hf-btn-sm"
                    >
                      Copy
                    </button>
                  </div>
                  <pre className="whitespace-pre-wrap rounded-[var(--r-field)] border border-[var(--border)] bg-[var(--surface)] p-3 font-mono text-xs text-[var(--fg)]">
                    {markdownPreview.markdown}
                  </pre>
                </div>
              ))}

            {tab === "graph" && (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-[var(--muted)]">
                    Nodes: {graphData?.nodes?.length ?? 0} | Edges: {graphData?.edges?.length ?? 0}
                  </span>
                  <button type="button" onClick={loadGraph} className="hf-btn hf-btn-sm">
                    Refresh
                  </button>
                </div>
                {!graphData || graphData.nodes.length === 0 ? (
                  <div className="hf-empty">No knowledge graph entities yet.</div>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {graphData.nodes.slice(0, 24).map((node) => (
                      <div key={node.id} className="hf-subcard flex items-center justify-between text-xs">
                        <span className="font-medium text-[var(--fg)]">{node.label}</span>
                        <span className="hf-chip hf-chip-plain font-mono">{node.type}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
