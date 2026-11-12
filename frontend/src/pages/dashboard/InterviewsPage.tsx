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
  const [interviewers, setInterviewers] = useState(
    "vikram@acmecloud.io, engineering-panel@acmecloud.io"
  );
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
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Interview Management</h1>
          <p className="hf-lede">
            Track candidate interviews, propose conflict-free slots, and approve simulated calendar
            invitations before confirmation.
          </p>
        </div>
        <span className="hf-chip hf-chip-plain">{interviews.length} Tracked Interviews</span>
      </div>

      {/* Pending HITL Invites */}
      {interviewApprovals.length > 0 && (
        <div className="space-y-3 rounded-[18px] border border-dashed border-[var(--esc)] bg-[var(--esc-soft)] p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-[var(--esc)]">
            <Clock className="h-4 w-4" />
            Pending Interview Invite Approvals ({interviewApprovals.length})
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {interviewApprovals.map((ap) => (
              <div
                key={ap.id}
                className="hf-q-item flex flex-col justify-between gap-3 text-xs"
              >
                <div>
                  <div className="font-bold text-[var(--ink)]">{ap.title}</div>
                  <p className="mt-1 text-[var(--muted)]">{ap.summary}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      resolveHitlApproval(ap.id, "approved", "Approved in Interview Management")
                    }
                    className="hf-btn hf-btn-primary hf-btn-sm"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Approve Invite
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      resolveHitlApproval(ap.id, "rejected", "Rejected in Interview Management")
                    }
                    className="hf-btn hf-btn-danger hf-btn-sm"
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
      <div className="hf-card">
        <div className="mb-4 flex items-center gap-2">
          <CalendarClock className="h-4 w-4 text-[var(--muted)]" />
          <h2 className="hf-h2 mb-0">Scheduled &amp; Proposed Interviews</h2>
        </div>

        {interviews.length === 0 ? (
          <div className="hf-empty">
            <strong>No interview records yet</strong>
            Use the form below to propose interview slots and stage HITL calendar invites.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="hf-rows">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Role</th>
                  <th>Stage</th>
                  <th>Panel</th>
                  <th>Start Time</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {interviews.map((iv) => (
                  <tr key={iv.id}>
                    <td className="font-semibold text-[var(--ink)]">{iv.candidate_name}</td>
                    <td>{iv.role_title}</td>
                    <td className="font-mono text-xs">{iv.interview_stage}</td>
                    <td>{iv.interviewer_emails.join(", ")}</td>
                    <td className="font-mono text-xs">
                      {new Date(iv.scheduled_start).toLocaleString()} ({iv.duration_minutes}m)
                    </td>
                    <td>
                      <span
                        className={`hf-chip ${
                          iv.status === "scheduled" ? "hf-chip-pass" : "hf-chip-escalate"
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
      <form onSubmit={handleSchedule} className="hf-card space-y-4">
        <div className="flex items-center gap-2">
          <PlusCircle className="h-4 w-4 text-[var(--pass)]" />
          <h2 className="hf-h2 mb-0">
            Schedule New Interview Round (Mock Calendar + HITL Invite)
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div className="hf-field">
            <label>Candidate Name</label>
            <input
              type="text"
              required
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              className="hf-input"
            />
          </div>
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
            <label>Interview Stage</label>
            <select
              value={stage}
              onChange={(e) => setStage(e.target.value)}
              className="hf-input"
            >
              <option value="screening_call">Screening Call</option>
              <option value="technical_round">Technical Round</option>
              <option value="system_design">System Design</option>
              <option value="hiring_manager_panel">Hiring Manager Panel</option>
            </select>
          </div>
          <div className="hf-field">
            <label>Interviewer Emails (comma-separated)</label>
            <input
              type="text"
              required
              value={interviewers}
              onChange={(e) => setInterviewers(e.target.value)}
              className="hf-input"
            />
          </div>
          <div className="hf-field">
            <label>Preferred Date &amp; Time</label>
            <input
              type="datetime-local"
              value={preferredDate}
              onChange={(e) => setPreferredDate(e.target.value)}
              className="hf-input"
            />
          </div>
          <div className="hf-field">
            <label>Duration (minutes)</label>
            <input
              type="number"
              min={15}
              max={180}
              value={durationMins}
              onChange={(e) => setDurationMins(Number(e.target.value))}
              className="hf-input"
            />
          </div>
        </div>

        <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
          {running ? "Checking Slots & Staging Invite..." : "Run Interview Scheduling Workflow"}
        </button>
      </form>

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
