import React, { useState } from "react";
import { Award, Search, Users } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const CandidatesPage: React.FC = () => {
  const { candidates, executeWorkflow } = useApp();
  const [search, setSearch] = useState("");
  const [roleTitle, setRoleTitle] = useState("Senior Backend Engineer");
  const [requiredSkills, setRequiredSkills] = useState("Python, FastAPI, PostgreSQL, LangGraph");
  const [topN, setTopN] = useState(3);
  const [running, setRunning] = useState(false);
  const [shortlistRes, setShortlistRes] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const filtered = candidates.filter((c) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      c.full_name.toLowerCase().includes(q) ||
      c.target_role.toLowerCase().includes(q) ||
      c.skills.some((s) => s.toLowerCase().includes(q))
    );
  });

  const handleRunShortlist = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    setShortlistRes(null);
    const reqSkills = requiredSkills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const res = await executeWorkflow({
      prompt: `Compare and shortlist top ${topN} candidates for ${roleTitle} with ${reqSkills.join(", ")}.`,
      workflow_hint: "candidate-shortlisting",
      structured_input: {
        job_title: roleTitle,
        required_skills: reqSkills,
        top_n: topN,
      },
    });
    setRunning(false);
    if (!res.ok) {
      setErrorMsg(res.error || "Shortlisting failed");
    } else if (res.data) {
      setShortlistRes(res.data);
    }
  };

  const matrix =
    (shortlistRes?.structured_output?.comparison_matrix as Record<string, unknown>[]) || [];

  return (
    <div className="space-y-6">
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Candidates &amp; Shortlisting</h1>
          <p className="hf-lede">
            Browse tenant-isolated candidate profiles from PostgreSQL and generate merit-based
            shortlist comparisons.
          </p>
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="pointer-events-none absolute left-3.5 top-2.5 h-4 w-4 text-[var(--muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter candidates or skills..."
            className="hf-input rounded-full pl-9"
          />
        </div>
      </div>

      {/* Candidate Directory Table */}
      <div className="hf-card">
        <div className="mb-4 flex items-center gap-2">
          <Users className="h-4 w-4 text-[var(--muted)]" />
          <h2 className="hf-h2 mb-0">Candidate Directory ({filtered.length})</h2>
        </div>

        {filtered.length === 0 ? (
          <div className="hf-empty">
            <strong>No matching candidates</strong>
            No matching candidates found in this tenant workspace.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Target Role</th>
                  <th>Exp</th>
                  <th>Extracted Skills</th>
                  <th className="num">Score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td className="font-semibold text-[var(--ink)]">{c.full_name}</td>
                    <td>{c.target_role}</td>
                    <td className="font-mono text-xs">{c.years_experience}y</td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {c.skills.slice(0, 6).map((s) => (
                          <span key={s} className="hf-chip hf-chip-plain">
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="num font-mono">
                      {c.match_score !== null ? `${c.match_score}%` : "Unscored"}
                    </td>
                    <td>
                      <span
                        className={`hf-chip ${
                          c.status === "shortlisted" || c.status === "hired"
                            ? "hf-chip-pass"
                            : c.status === "rejected"
                              ? "hf-chip-block"
                              : "hf-chip-plain"
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Candidate Shortlisting Runner */}
      <form onSubmit={handleRunShortlist} className="hf-card space-y-4">
        <div className="flex items-center gap-2">
          <Award className="h-4 w-4 text-[var(--pass)]" />
          <h2 className="hf-h2 mb-0">Generate Merit Shortlist Comparison</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="hf-field">
            <label>Role Title</label>
            <input
              type="text"
              required
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              className="hf-input"
            />
          </div>
          <div className="hf-field">
            <label>Required Skills (comma-separated)</label>
            <input
              type="text"
              required
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              className="hf-input"
            />
          </div>
          <div className="hf-field">
            <label>Shortlist Size (Top N)</label>
            <input
              type="number"
              min={1}
              max={10}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="hf-input"
            />
          </div>
        </div>

        <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
          {running ? "Ranking Candidates..." : "Run Candidate Shortlisting Workflow"}
        </button>
      </form>

      {matrix.length > 0 && (
        <div className="hf-card space-y-3">
          <h3 className="hf-h2 mb-0">Ranked Shortlist Matrix</h3>
          <div className="grid gap-3 md:grid-cols-3">
            {matrix.map((row, idx) => (
              <div key={idx} className="hf-subcard text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold text-[var(--ink)]">
                    #{idx + 1} {String(row.candidate_label || "")}
                  </span>
                  <span className="hf-chip hf-chip-pass font-mono">
                    {String(row.match_score ?? 0)}%
                  </span>
                </div>
                <p className="mt-1.5 text-[var(--muted)]">
                  Exp: {String(row.years_experience ?? 0)} yrs
                </p>
                {Array.isArray(row.missing_skills) && row.missing_skills.length > 0 && (
                  <p className="mt-2 text-[var(--block)]">
                    Missing: {(row.missing_skills as string[]).join(", ")}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <ExecutionResultPanel result={shortlistRes} errorMsg={errorMsg} />
    </div>
  );
};
