import React, { useState } from "react";
import { CalendarClock, CheckCircle2, Clock, PlusCircle, XCircle } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const InterviewsPage: React.FC = () => {
  const { interviews, approvals, executeWorkflow, resolveHitlApproval } = useApp();

  const [candidateName, setCandidateName] = useState("Arnav Sharma");
  const [roleTitle, setRoleTitle] = useState("Senior Backend Engineer");
  const [stage, setStage] = useState("technical_round");
  const [interviewers, setInterviewers] = useState("vikram@acmecloud.io, engineering-panel@acmecloud.io");
  const [durationMins, setDurationMins] = useState(45);
  const [preferredDate, setPreferredDate] = useState(() => {
    const d = new Date(Date.now() + 86400 * 1000 * 2);
    return d.toISOString().slice(0, 16);
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const interviewApprovals = approvals.filter(
    (a) => a.agent_slug === "interview-scheduling" && a.status === "pending"
  );

  const handleSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    setResult(null);
    const emailList = interviewers
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const res = await executeWorkflow({
      prompt: `Schedule a ${durationMins}-minute ${stage} interview for ${candidateName} applying for ${roleTitle} with ${emailList.join(", ")}.`,
      workflow_hint: "interview-scheduling",
      structured_input: {
        candidate_name: candidateName,
        role_title: roleTitle,
        interview_stage: stage,
        interviewer_emails: emailList,
        duration_minutes: durationMins,
        preferred_start_iso: new Date(preferredDate).toISOString(),
      },
    });
    setRunning(false);
    if (!res.ok) {
      setErrorMsg(res.error || "Scheduling failed");
    } else if (res.data) {
      setResult(res.data);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">
            Interview Management
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Track candidate interviews, propose conflict-free slots, and approve simulated calendar
            invitations before confirmation.
          </p>
        </div>
        <span className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-700">
          {interviews.length} Tracked Interviews
        </span>
      </div>

      {/* Pending HITL Invites */}
      {interviewApprovals.length > 0 && (
        <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-950">
            <Clock className="h-4 w-4 text-amber-600" />
            Pending Interview Invite Approvals ({interviewApprovals.length})
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {interviewApprovals.map((ap) => (
              <div
                key={ap.id}
                className="flex flex-col justify-between gap-3 rounded-xl border border-amber-200 bg-white p-4 text-xs"
              >
                <div>
                  <div className="font-bold text-slate-900">{ap.title}</div>
                  <p className="mt-1 text-slate-600">{ap.summary}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => resolveHitlApproval(ap.id, "approved", "Approved in Interview Management")}
                    className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-500"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Approve Invite
                  </button>
                  <button
                    type="button"
                    onClick={() => resolveHitlApproval(ap.id, "rejected", "Rejected in Interview Management")}
                    className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 font-semibold text-rose-700 hover:bg-rose-100"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Existing Interviews Table */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
        <div className="flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Scheduled &amp; Proposed Interviews
          </h2>
        </div>

        {interviews.length === 0 ? (
          <p className="mt-4 text-xs text-slate-500">No interview records in this tenant yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-200 text-[11px] uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-2.5 pr-4">Candidate</th>
                  <th className="py-2.5 pr-4">Role</th>
                  <th className="py-2.5 pr-4">Stage</th>
                  <th className="py-2.5 pr-4">Panel</th>
                  <th className="py-2.5 pr-4">Start Time</th>
                  <th className="py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {interviews.map((iv) => (
                  <tr key={iv.id}>
                    <td className="py-3 pr-4 font-semibold text-slate-900">{iv.candidate_name}</td>
                    <td className="py-3 pr-4 text-slate-600">{iv.role_title}</td>
                    <td className="py-3 pr-4 font-mono text-slate-600">{iv.interview_stage}</td>
                    <td className="py-3 pr-4 text-slate-600">
                      {iv.interviewer_emails.join(", ")}
                    </td>
                    <td className="py-3 pr-4 font-mono text-slate-600">
                      {new Date(iv.scheduled_start).toLocaleString()} ({iv.duration_minutes}m)
                    </td>
                    <td className="py-3">
                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${
                          iv.status === "scheduled"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-800"
                        }`}
                      >
                        {iv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Schedule New Interview Form */}
      <form
        onSubmit={handleSchedule}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="flex items-center gap-2">
          <PlusCircle className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Schedule New Interview Round (Mock Calendar + HITL Invite)
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <label className="text-xs font-semibold text-slate-700">Candidate Name</label>
            <input
              type="text"
              required
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
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
            <label className="text-xs font-semibold text-slate-700">Interview Stage</label>
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            >
              <option value="screening_call">Screening Call</option>
              <option value="technical_round">Technical Round</option>
              <option value="system_design">System Design</option>
              <option value="hiring_manager_panel">Hiring Manager Panel</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Interviewer Emails (comma-separated)
            </label>
            <input
              type="text"
              required
              value={interviewers}
              onChange={(e) => setInterviewers(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">Preferred Date &amp; Time</label>
            <input
              type="datetime-local"
              value={preferredDate}
              onChange={(e) => setPreferredDate(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">Duration (minutes)</label>
            <input
              type="number"
              min={15}
              max={180}
              value={durationMins}
              onChange={(e) => setDurationMins(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={running}
          className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          {running ? "Checking Slots & Staging Invite..." : "Run Interview Scheduling Workflow"}
        </button>
      </form>

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
