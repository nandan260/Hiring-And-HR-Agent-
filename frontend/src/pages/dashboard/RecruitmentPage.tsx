import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Briefcase, CalendarClock, FileSearch, FileText, ShieldCheck, Users } from "lucide-react";
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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">Recruitment Hub</h1>
          <p className="mt-1 text-sm text-slate-600">
            End-to-end hiring pipeline connecting job requisitions, blind resume screening,
            merit shortlisting, and panel interviews.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${
              blindEnabled
                ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                : "border-slate-200 bg-white text-slate-700"
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Blind PII Screening: {blindEnabled ? "Active" : "Off"}
          </span>
        </div>
      </div>

      {/* Recruiting Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Tracked Candidates</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-slate-900">
            {candidates.length}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Shortlisted / Scored &ge; 75%</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-emerald-700">
            {candidates.filter((c) => (c.match_score ?? 0) >= 75).length}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Active Interviews</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-indigo-700">
            {interviews.length}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
          <div className="text-xs font-medium text-slate-500">Hiring Sign-Offs Pending</div>
          <div className="mt-1.5 font-display text-2xl font-bold text-amber-700">
            {recruitingApprovals.length}
          </div>
        </div>
      </div>

      {/* Stage Shortcuts */}
      <div className="grid gap-4 md:grid-cols-4">
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
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs transition hover:border-indigo-300"
            >
              <Icon className="h-5 w-5 text-indigo-600" />
              <div className="mt-3 text-sm font-bold text-slate-900">{step.title}</div>
              <p className="mt-1 text-xs text-slate-600">{step.desc}</p>
              <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-indigo-600">
                Open <ArrowRight className="h-3.5 w-3.5" />
              </span>
            </Link>
          );
        })}
      </div>

      {/* Top Ranked Candidates Snapshot */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Briefcase className="h-4 w-4 text-indigo-600" />
            <h2 className="font-display text-base font-bold text-slate-900">
              Top Evaluated Candidates
            </h2>
          </div>
          <Link to="/dashboard/candidates" className="text-xs font-semibold text-indigo-600 hover:underline">
            Full Candidate Pool →
          </Link>
        </div>

        {topCandidates.length === 0 ? (
          <p className="mt-4 text-xs text-slate-500">
            No candidates stored yet. Upload or paste resumes in Resume Screening.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-2.5 pr-4">Candidate</th>
                  <th className="py-2.5 pr-4">Target Role</th>
                  <th className="py-2.5 pr-4">Experience</th>
                  <th className="py-2.5 pr-4">Skills</th>
                  <th className="py-2.5 pr-4">Match Score</th>
                  <th className="py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {topCandidates.map((c) => (
                  <tr key={c.id}>
                    <td className="py-3 pr-4 font-semibold text-slate-900">{c.full_name}</td>
                    <td className="py-3 pr-4 text-slate-600">{c.target_role}</td>
                    <td className="py-3 pr-4 font-mono text-slate-600">{c.years_experience} yrs</td>
                    <td className="py-3 pr-4">
                      <div className="flex flex-wrap gap-1">
                        {c.skills.slice(0, 4).map((s) => (
                          <span
                            key={s}
                            className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-700"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 pr-4 font-mono font-semibold text-indigo-700">
                      {c.match_score !== null ? `${c.match_score}%` : "—"}
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
    </div>
  );
};
