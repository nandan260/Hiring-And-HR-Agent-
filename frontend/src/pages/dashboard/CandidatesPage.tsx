import React, { useMemo, useState } from "react";
import { Badge } from "../../components/common/Badge";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const CandidatesPage: React.FC = () => {
  const { candidates, executeWorkflow } = useApp();
  const [search, setSearch] = useState("");
  const [roleTitle, setRoleTitle] = useState("Senior Backend Engineer");
  const [requiredSkills, setRequiredSkills] = useState("Python, FastAPI, PostgreSQL");
  const [topN, setTopN] = useState(3);
  const [running, setRunning] = useState(false);
  const [shortlistRes, setShortlistRes] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter(
      (c) =>
        c.full_name.toLowerCase().includes(q) ||
        c.target_role.toLowerCase().includes(q) ||
        c.skills.some((s) => s.toLowerCase().includes(q))
    );
  }, [candidates, search]);

  const handleShortlist = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    const reqSkills = requiredSkills.split(",").map((s) => s.trim()).filter(Boolean);
    const res = await executeWorkflow({
      prompt: `Shortlist top ${topN} candidates for ${roleTitle} requiring ${reqSkills.join(", ")}`,
      workflow_hint: "candidate-shortlisting",
      structured_input: {
        job_title: roleTitle,
        required_skills: reqSkills,
        top_n: topN,
      },
    });
    setRunning(false);
    if (res.ok && res.data) {
      setShortlistRes(res.data);
    } else {
      setErrorMsg(res.error || "Shortlisting failed.");
    }
  };

  const matrix =
    (shortlistRes?.structured_output?.comparison_matrix as Array<{
      candidate_name: string;
      status: string;
      years_experience: number;
      match_score: number;
      matched_skills?: string[];
      missing_skills?: string[];
    }>) || [];

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Candidates ({filtered.length})</h1>
        <form onSubmit={handleShortlist} className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter pool..."
            className="hf-input w-40"
          />
          <input
            type="text"
            value={roleTitle}
            onChange={(e) => setRoleTitle(e.target.value)}
            placeholder="Role"
            className="hf-input w-44"
          />
          <input
            type="text"
            value={requiredSkills}
            onChange={(e) => setRequiredSkills(e.target.value)}
            placeholder="Skills"
            className="hf-input w-44"
          />
          <input
            type="number"
            min={1}
            max={10}
            value={topN}
            onChange={(e) => setTopN(Number(e.target.value))}
            className="hf-input w-16"
          />
          <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
            {running ? "Ranking..." : "Shortlist"}
          </button>
        </form>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
        <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-7">
          {filtered.length === 0 ? (
            <div className="hf-empty my-auto">No matching candidates.</div>
          ) : (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <table className="hf-rows">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Exp</th>
                    <th>Status</th>
                    <th className="num">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id}>
                      <td className="font-medium text-[var(--fg)]">{c.full_name}</td>
                      <td className="text-[var(--muted)]">{c.target_role}</td>
                      <td className="font-mono text-xs text-[var(--fg)]">{c.years_experience}y</td>
                      <td>
                        <Badge variant={c.status === "shortlisted" ? "emerald" : "slate"}>
                          {c.status}
                        </Badge>
                      </td>
                      <td className="num font-semibold text-[var(--fg)]">
                        {c.match_score != null ? `${Math.round(c.match_score)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="hf-card col-span-12 flex min-h-0 flex-col gap-3 overflow-y-auto lg:col-span-5">
          <h2 className="hf-h2 flex-none">Shortlist Matrix</h2>
          {matrix.length > 0 && (
            <table className="hf-rows flex-none">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th className="num">Match</th>
                </tr>
              </thead>
              <tbody>
                {matrix.map((row, idx) => (
                  <tr key={idx}>
                    <td>
                      <div className="font-medium text-[var(--fg)]">{row.candidate_name}</div>
                      <div className="text-[11px] text-[var(--muted)]">
                        {row.matched_skills?.join(", ")}
                      </div>
                    </td>
                    <td className="num font-bold text-[var(--fg)]">{row.match_score}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {shortlistRes || errorMsg ? (
            <ExecutionResultPanel result={shortlistRes} errorMsg={errorMsg} title="Shortlisting" />
          ) : (
            <div className="hf-empty my-auto">Run Shortlist to rank candidates.</div>
          )}
        </div>
      </div>
    </div>
  );
};
