import React, { useState } from "react";
import { Badge } from "../../components/common/Badge";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import type { UnifiedExecuteResponse } from "../../types/agent";

const ALL_KYC_DOCS = [
  { key: "offer_letter_signed", label: "Offer Letter" },
  { key: "aadhar_card", label: "Government ID" },
  { key: "degree_certificate", label: "Degree Certificate" },
  { key: "bank_details", label: "Bank Details" },
];

export const OnboardingPage: React.FC = () => {
  const { onboardingWorkflows, approvals, executeWorkflow, resolveHitlApproval } = useApp();
  const [employeeName, setEmployeeName] = useState("Rohan Kulkarni");
  const [roleTitle, setRoleTitle] = useState("Senior Backend Engineer");
  const [department, setDepartment] = useState("Platform Engineering");
  const [submittedDocs, setSubmittedDocs] = useState<string[]>([
    "offer_letter_signed",
    "aadhar_card",
  ]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [tab, setTab] = useState<"records" | "approvals" | "output">("records");

  const onboardingApprovals = approvals.filter(
    (a) => a.agent_slug === "employee-onboarding" && a.status === "pending"
  );

  const toggleDoc = (key: string) => {
    setSubmittedDocs((prev) =>
      prev.includes(key) ? prev.filter((d) => d !== key) : [...prev, key]
    );
  };

  const handleRunOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    const res = await executeWorkflow({
      prompt: `Verify onboarding and issue starter kit for ${employeeName} (${roleTitle} - ${department}). Submitted docs: ${submittedDocs.join(", ")}.`,
      workflow_hint: "employee-onboarding",
      structured_input: {
        employee_name: employeeName,
        role_title: roleTitle,
        department,
        submitted_documents: submittedDocs,
      },
    });
    setRunning(false);
    if (res.ok && res.data) {
      setResult(res.data);
      setTab("output");
    } else {
      setErrorMsg(res.error || "Onboarding workflow failed.");
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Onboarding</h1>
        <div className="hf-tabs">
          <button
            type="button"
            onClick={() => setTab("records")}
            className={`hf-tab ${tab === "records" ? "active" : ""}`}
          >
            Records ({onboardingWorkflows.length})
          </button>
          <button
            type="button"
            onClick={() => setTab("approvals")}
            className={`hf-tab ${tab === "approvals" ? "active" : ""}`}
          >
            Approvals ({onboardingApprovals.length})
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
          onSubmit={handleRunOnboarding}
          className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 overflow-y-auto lg:col-span-4"
        >
          <div className="hf-field">
            <label>New Hire Name</label>
            <input
              type="text"
              value={employeeName}
              onChange={(e) => setEmployeeName(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="hf-field">
            <label>Role</label>
            <input
              type="text"
              value={roleTitle}
              onChange={(e) => setRoleTitle(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="hf-field">
            <label>Department</label>
            <input
              type="text"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="hf-field">
            <label>Submitted Documents</label>
            <div className="space-y-1.5">
              {ALL_KYC_DOCS.map((doc) => (
                <label
                  key={doc.key}
                  className="flex cursor-pointer items-center gap-2 rounded-[var(--r-field)] border border-[var(--border)] px-2.5 py-1.5 text-xs text-[var(--fg)]"
                >
                  <input
                    type="checkbox"
                    checked={submittedDocs.includes(doc.key)}
                    onChange={() => toggleDoc(doc.key)}
                    className="h-3.5 w-3.5 accent-[var(--fg)]"
                  />
                  {doc.label}
                </label>
              ))}
            </div>
          </div>

          <button type="submit" disabled={running} className="hf-btn hf-btn-primary mt-auto w-full">
            {running ? "Verifying..." : "Verify Onboarding"}
          </button>
        </form>

        <div className="hf-card col-span-12 flex min-h-0 flex-col lg:col-span-8">
          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "records" &&
              (onboardingWorkflows.length === 0 ? (
                <div className="hf-empty">No onboarding records.</div>
              ) : (
                <div className="space-y-2.5">
                  {onboardingWorkflows.map((ob) => {
                    const missing = Object.entries(ob.documents_status || {})
                      .filter(([, st]) => st !== "submitted" && st !== "verified")
                      .map(([k]) => k);
                    return (
                      <div key={ob.id} className="hf-subcard">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-sm font-semibold text-[var(--fg)]">
                              {ob.employee_name}
                            </div>
                            <div className="text-xs text-[var(--muted)]">{ob.role_title}</div>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-[var(--fg)]">
                              {Math.round(ob.progress_percent)}%
                            </span>
                            <Badge variant={ob.current_stage === "completed" ? "emerald" : "amber"}>
                              {ob.current_stage}
                            </Badge>
                          </div>
                        </div>
                        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full border border-[var(--border)]">
                          <div
                            className="h-full bg-[var(--fg)]"
                            style={{ width: `${Math.min(100, ob.progress_percent)}%` }}
                          />
                        </div>
                        {missing.length > 0 && (
                          <div className="mt-1.5 text-[11px] font-mono text-[var(--muted)]">
                            Missing: {missing.join(", ")}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}

            {tab === "approvals" &&
              (onboardingApprovals.length === 0 ? (
                <div className="hf-empty">No pending onboarding approvals.</div>
              ) : (
                <div className="space-y-2">
                  {onboardingApprovals.map((ap) => (
                    <div key={ap.id} className="hf-subcard flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-[var(--fg)]">{ap.title}</div>
                        <div className="text-xs text-[var(--muted)]">{ap.summary}</div>
                      </div>
                      <div className="flex shrink-0 gap-1.5">
                        <button
                          type="button"
                          onClick={() => resolveHitlApproval(ap.id, "approved", "Provisioned")}
                          className="hf-btn hf-btn-primary hf-btn-sm"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => resolveHitlApproval(ap.id, "rejected", "Held")}
                          className="hf-btn hf-btn-sm"
                        >
                          Hold
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}

            {tab === "output" &&
              (result || errorMsg ? (
                <ExecutionResultPanel result={result} errorMsg={errorMsg} title="Onboarding" />
              ) : (
                <div className="hf-empty">Verify onboarding to inspect output.</div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
};
