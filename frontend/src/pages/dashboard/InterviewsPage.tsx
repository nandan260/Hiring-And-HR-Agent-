import React, { useState } from "react";
import { Badge } from "../../components/common/Badge";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const InterviewsPage: React.FC = () => {
  const { interviews, approvals, executeWorkflow, resolveHitlApproval } = useApp();
  const [candidateName, setCandidateName] = useState("Arjun Mehta");
  const [roleTitle, setRoleTitle] = useState("Senior Backend Engineer");
  const [stage, setStage] = useState("technical_round");
  const [interviewers, setInterviewers] = useState("maya@acmecloud.io, lead@acmecloud.io");
  const [durationMins, setDurationMins] = useState(45);
  const [preferredDate, setPreferredDate] = useState("2026-04-20");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [tab, setTab] = useState<"schedule" | "approvals" | "output">("schedule");

  const interviewApprovals = approvals.filter(
    (a) => a.agent_slug === "interview-scheduling" && a.status === "pending"
  );

  const handleSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    const emailList = interviewers.split(",").map((s) => s.trim()).filter(Boolean);

    const res = await executeWorkflow({
      prompt: `Schedule a ${durationMins}m ${stage} interview for ${candidateName} (${roleTitle}) with ${emailList.join(", ")} on ${preferredDate}`,
      workflow_hint: "interview-scheduling",
      structured_input: {
        candidate_name: candidateName,
        role_title: roleTitle,
        interview_stage: stage,
        interviewer_emails: emailList,
        duration_minutes: durationMins,
        preferred_start_iso: `${preferredDate}T10:00:00`,
      },
    });
    setRunning(false);
    if (res.ok && res.data) {
      setResult(res.data);
      setTab("output");
    } else {
      setErrorMsg(res.error || "Scheduling failed.");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Interviews</h1>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("schedule")}
            className={`hf-tab ${tab === "schedule" ? "active" : ""}`}
          >
            Scheduled ({interviews.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("approvals")}
            className={`hf-tab ${tab === "approvals" ? "active" : ""}`}
          >
            Approvals ({interviewApprovals.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("output")}
            className={`hf-tab ${tab === "output" ? "active" : ""}`}
          >
            Output
          </button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
        <form
          onSubmit={handleSchedule}
          className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 overflow-y-auto lg:col-span-4"
        >
          <div className="hf-field">
            <label>Candidate Name</label>
            <input
              type="text"
              value={candidateName}
              onChange={(e) => setCandidateName(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="hf-field">
            <label>Role Title</label>
            <input
              type="text"
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="hf-field">
              <label>Stage</label>
              <select value={stage} onChange={(e) => setStage(e.target.value)} className="hf-input">
                <option value="technical_round">Technical Round</option>
                <option value="system_design">System Design</option>
                <option value="hr_culture_fit">HR Culture Fit</option>
                <option value="final_executive">Final Panel</option>
              </select>
            </div>
            <div className="hf-field">
              <label>Minutes</label>
              <input
                type="number"
                min={15}
                max={120}
                value={durationMins}
                onChange={(e) => setDurationMins(Number(e.target.value))}
                className="hf-input"
              />
            </div>
          </div>

          <div className="hf-field">
            <label>Interviewer Emails</label>
            <input
              type="text"
              value={interviewers}
              onChange={(e) => setInterviewers(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="hf-field">
            <label>Date</label>
            <input
              type="date"
              value={preferredDate}
              onChange={(e) => setPreferredDate(e.target.value)}
              className="hf-input"
            />
          </div>

          <button type="submit" disabled={running} className="hf-btn hf-btn-primary mt-auto w-full">
            {running ? "Scheduling..." : "Propose Interview"}
          </button>
        </form>

        <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-8">
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "schedule" &&
              (interviews.length === 0 ? (
                <div className="hf-empty">No interviews scheduled.</div>
              ) : (
                <table className="hf-rows">
                  <thead>
                    <tr>
                      <th>Candidate</th>
                      <th>Role</th>
                      <th>Stage</th>
                      <th>Status</th>
                      <th className="num">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {interviews.map((iv) => (
                      <tr key={iv.id}>
                        <td className="font-medium text-[var(--fg)]">{iv.candidate_name}</td>
                        <td className="text-[var(--muted)]">{iv.role_title}</td>
                        <td className="font-mono text-xs">{iv.interview_stage}</td>
                        <td>
                          <Badge variant={iv.status === "confirmed" ? "emerald" : "amber"}>
                            {iv.status}
                          </Badge>
                        </td>
                        <td className="num text-xs text-[var(--muted)]">
                          {new Date(iv.scheduled_start).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ))}

            {tab === "approvals" &&
              (interviewApprovals.length === 0 ? (
                <div className="hf-empty">No pending interview approvals.</div>
              ) : (
                <div className="space-y-2">
                  {interviewApprovals.map((ap) => (
                    <div key={ap.id} className="hf-subcard flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-[var(--fg)]">{ap.title}</div>
                        <div className="text-xs text-[var(--muted)]">{ap.summary}</div>
                      </div>
                      <div className="flex shrink-0 gap-1.5">
                        <button
                          type="button"
                          onClick={() => resolveHitlApproval(ap.id, "approved", "Confirmed")}
                          className="hf-btn hf-btn-primary hf-btn-sm"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => resolveHitlApproval(ap.id, "rejected", "Declined")}
                          className="hf-btn hf-btn-sm"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}

            {tab === "output" &&
              (result || errorMsg ? (
                <ExecutionResultPanel result={result} errorMsg={errorMsg} title="Scheduling" />
              ) : (
                <div className="hf-empty">Propose an interview to view output.</div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
};
