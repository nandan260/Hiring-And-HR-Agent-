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
    ((shortlistRes?.structured_output?.comparison_matrix as Record<string, unknown>[]) || []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Candidates &amp; Shortlisting
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Browse tenant-isolated candidate profiles from PostgreSQL and generate merit-based
            shortlist comparisons.
          </p>
        </div>
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter candidates or skills..."
            className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-indigo-400"
          />
        </div>
      </div>

      {/* Candidate Directory Table */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Candidate Directory ({filtered.length})
          </h2>
        </div>

        {filtered.length === 0 ? (
          <p className="mt-4 text-xs text-slate-500">
            No matching candidates found in this tenant workspace.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-2.5 pr-4">Name</th>
                  <th className="py-2.5 pr-4">Target Role</th>
                  <th className="py-2.5 pr-4">Exp</th>
                  <th className="py-2.5 pr-4">Extracted Skills</th>
                  <th className="py-2.5 pr-4">Score</th>
                  <th className="py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td className="py-3 pr-4 font-semibold text-slate-900">{c.full_name}</td>
                    <td className="py-3 pr-4 text-slate-600">{c.target_role}</td>
                    <td className="py-3 pr-4 font-mono text-slate-600">{c.years_experience}y</td>
                    <td className="py-3 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {c.skills.slice(0, 6).map((s) => (
                          <span
                            key={s}
                            className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 pr-4 font-mono font-bold text-indigo-700">
                      {c.match_score !== null ? `${c.match_score}%` : "Unscored"}
                    </td>
                    <td className="py-3">
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
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
      <form
        onSubmit={handleRunShortlist}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="flex items-center gap-2">
          <Award className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Generate Merit Shortlist Comparison
          </h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="text-xs font-semibold text-slate-700">Role Title</label>
            <input
              type="text"
              required
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Required Skills (comma-separated)
            </label>
            <input
              type="text"
              required
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">Shortlist Size (Top N)</label>
            <input
              type="number"
              min={1}
              max={10}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={running}
          className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          {running ? "Ranking Candidates..." : "Run Candidate Shortlisting Workflow"}
        </button>
      </form>

      {matrix.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <h3 className="font-display text-base font-bold text-slate-900">
            Ranked Shortlist Matrix
          </h3>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            {matrix.map((row, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900">
                    #{idx + 1} {String(row.candidate_label || "")}
                  </span>
                  <span className="font-mono font-bold text-indigo-700">
                    {String(row.match_score ?? 0)}%
                  </span>
                </div>
                <p className="mt-1 text-slate-600">
                  Exp: {String(row.years_experience ?? 0)} yrs
                </p>
                {Array.isArray(row.missing_skills) && row.missing_skills.length > 0 && (
                  <p className="mt-2 text-rose-700">
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
