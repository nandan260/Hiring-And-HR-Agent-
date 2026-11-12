import React from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/common/Badge";
import { useApp } from "../../context/AppContext";

export const RecruitmentPage: React.FC = () => {
  const { candidates, interviews, approvals, workspace } = useApp();
  const blindEnabled = workspace?.settings?.blind_screening_mode ?? false;
  const topCandidates = [...candidates]
    .sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0))
    .slice(0, 10);

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <div className="flex items-center gap-2.5">
          <h1 className="hf-h1">Recruitment</h1>
          <Badge variant={blindEnabled ? "emerald" : "slate"}>
            {blindEnabled ? "Blind On" : "Standard"}
          </Badge>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Link to="/dashboard/jd-generator" className="hf-btn hf-btn-sm">
            JD Generator
          </Link>
          <Link to="/dashboard/screening" className="hf-btn hf-btn-sm">
            Resume Screening
          </Link>
          <Link to="/dashboard/candidates" className="hf-btn hf-btn-sm">
            Candidates
          </Link>
          <Link to="/dashboard/interviews" className="hf-btn hf-btn-sm">
            Interviews
          </Link>
        </div>
      </div>

      <div className="hf-stats">
        <div className="hf-stat">
          <div className="hf-stat-k">Candidates</div>
          <div className="hf-stat-v">{candidates.length}</div>
        </div>
        <div className="hf-stat">
          <div className="hf-stat-k">Shortlisted</div>
          <div className="hf-stat-v">
            {candidates.filter((c) => c.status === "shortlisted" || c.status === "interviewing").length}
          </div>
        </div>
        <div className="hf-stat">
          <div className="hf-stat-k">Interviews</div>
          <div className="hf-stat-v">{interviews.length}</div>
        </div>
        <div className="hf-stat">
          <div className="hf-stat-k">Approvals</div>
          <div className="hf-stat-v">{approvals.filter((a) => a.status === "pending").length}</div>
        </div>
      </div>

      <div className="hf-card flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex flex-none items-center justify-between">
          <h2 className="hf-h2">Ranked Pool</h2>
          <Link
            to="/dashboard/candidates"
            className="text-xs font-medium text-[var(--muted)] hover:text-[var(--fg)]"
          >
            All Candidates
          </Link>
        </div>
        {topCandidates.length === 0 ? (
          <div className="hf-empty my-auto">No candidates available.</div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Target Role</th>
                  <th>Status</th>
                  <th className="num">Match</th>
                </tr>
              </thead>
              <tbody>
                {topCandidates.map((cand) => (
                  <tr key={cand.id}>
                    <td className="font-medium text-[var(--fg)]">{cand.full_name}</td>
                    <td className="text-[var(--muted)]">{cand.target_role}</td>
                    <td>
                      <Badge variant={cand.status === "shortlisted" ? "emerald" : "slate"}>
                        {cand.status}
                      </Badge>
                    </td>
                    <td className="num font-semibold text-[var(--fg)]">
                      {cand.match_score !== null && cand.match_score !== undefined
                        ? `${Math.round(cand.match_score)}%`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
