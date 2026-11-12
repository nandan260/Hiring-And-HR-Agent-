import React from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Briefcase,
  CalendarClock,
  FileSearch,
  FileText,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useApp } from "../../context/AppContext";

export const RecruitmentPage: React.FC = () => {
  const { candidates, interviews, approvals, workspace } = useApp();

  const blindEnabled = workspace?.settings?.blind_screening_mode ?? false;
  const recruitingApprovals = approvals.filter(
    (a) =>
      a.status === "pending" &&
      (a.agent_slug === "candidate-shortlisting" || a.agent_slug === "interview-scheduling")
  );
  const topCandidates = [...candidates]
    .sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0))
    .slice(0, 6);

  return (
    <div className="space-y-6">
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Recruitment Hub</h1>
          <p className="hf-lede">
            End-to-end hiring pipeline connecting job requisitions, blind resume screening,
            merit shortlisting, and panel interviews.
          </p>
        </div>
        <span className={`hf-chip ${blindEnabled ? "hf-chip-pass" : "hf-chip-plain"}`}>
          <ShieldCheck className="h-3.5 w-3.5" />
          Blind PII Screening: {blindEnabled ? "Active" : "Off"}
        </span>
      </div>

      {/* Recruiting Summary Cards */}
      <div className="hf-stats">
        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Tracked Candidates</div>
          <div className="hf-stat-v">{candidates.length}</div>
        </div>
        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Shortlisted / Scored &ge; 75%</div>
          <div className="hf-stat-v text-[var(--pass)]">
            {candidates.filter((c) => (c.match_score ?? 0) >= 75).length}
          </div>
        </div>
        <div className="hf-stat border-b-0">
          <div className="hf-stat-k">Active Interviews</div>
          <div className="hf-stat-v">{interviews.length}</div>
        </div>
        <div className="hf-stat border-b-0 border-r-0">
          <div className="hf-stat-k">Hiring Sign-Offs Pending</div>
          <div className="hf-stat-v text-[var(--esc)]">{recruitingApprovals.length}</div>
        </div>
      </div>

      {/* Stage Shortcuts */}
      <div className="grid gap-3 md:grid-cols-4">
        {[
          {
            title: "1. Draft Job Description",
            desc: "Generate inclusive JDs with internal leveling citations.",
            to: "/dashboard/jd-generator",
            icon: FileText,
          },
          {
            title: "2. Screen Resumes",
            desc: "Upload PDF/DOCX resumes and score against rubrics.",
            to: "/dashboard/screening",
            icon: FileSearch,
          },
          {
            title: "3. Compare & Shortlist",
            desc: "Run merit ranking and surface skill gaps.",
            to: "/dashboard/candidates",
            icon: Users,
          },
          {
            title: "4. Schedule Interviews",
            desc: "Propose conflict-free panel slots & HITL invites.",
            to: "/dashboard/interviews",
            icon: CalendarClock,
          },
        ].map((step) => {
          const Icon = step.icon;
          return (
            <Link
              key={step.title}
              to={step.to}
              className="hf-card group flex flex-col justify-between no-underline transition hover:border-[var(--muted)]"
            >
              <div>
                <Icon className="h-5 w-5 text-[var(--ink)]" />
                <div className="mt-3 text-sm font-bold text-[var(--ink)]">{step.title}</div>
                <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">{step.desc}</p>
              </div>
              <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-[var(--ink-2)] group-hover:text-[var(--ink)]">
                Open <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </Link>
          );
        })}
      </div>

      {/* Top Ranked Candidates Snapshot */}
      <div className="hf-card">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-[var(--muted)]" />
            <h2 className="hf-h2 mb-0">Top Evaluated Candidates</h2>
          </div>
          <Link to="/dashboard/candidates" className="hf-btn hf-btn-sm">
            Full Candidate Pool &rarr;
          </Link>
        </div>

        {topCandidates.length === 0 ? (
          <div className="hf-empty">
            <strong>No candidates stored yet</strong>
            Upload or paste resumes in Resume Screening to populate this pool.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Target Role</th>
                  <th>Experience</th>
                  <th>Skills</th>
                  <th className="num">Match Score</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {topCandidates.map((c) => (
                  <tr key={c.id}>
                    <td className="font-semibold text-[var(--ink)]">{c.full_name}</td>
                    <td>{c.target_role}</td>
                    <td className="font-mono text-xs">{c.years_experience} yrs</td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {c.skills.slice(0, 4).map((s) => (
                          <span key={s} className="hf-chip hf-chip-plain">
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="num font-mono">
                      {c.match_score !== null ? `${c.match_score}%` : "—"}
                    </td>
                    <td>
                      <span className="hf-chip hf-chip-plain">{c.status}</span>
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
