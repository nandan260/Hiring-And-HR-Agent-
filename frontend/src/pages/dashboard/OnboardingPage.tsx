import React, { useState } from "react";
import { CheckCircle2, Clock, UserCheck, XCircle } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import type { UnifiedExecuteResponse } from "../../types/agent";

const ALL_KYC_DOCS = [
  { key: "offer_letter_signed", label: "Signed Offer Letter" },
  { key: "aadhar_card", label: "Aadhaar / Gov ID" },
  { key: "degree_certificate", label: "Degree Certificate" },
  { key: "bank_details", label: "Bank / Payroll Form" },
];

export const OnboardingPage: React.FC = () => {
  const { onboardingWorkflows, approvals, executeWorkflow, resolveHitlApproval } = useApp();

  const [employeeName, setEmployeeName] = useState("Rohan Kulkarni");
  const [roleTitle, setRoleTitle] = useState("Backend Engineer");
  const [department, setDepartment] = useState("Engineering");
  const [submittedDocs, setSubmittedDocs] = useState<string[]>([
    "offer_letter_signed",
    "aadhar_card",
  ]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const onboardingApprovals = approvals.filter(
    (a) => a.agent_slug === "employee-onboarding" && a.status === "pending"
  );

  const toggleDoc = (key: string) => {
    setSubmittedDocs((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const handleRunOnboarding = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    setResult(null);

    const res = await executeWorkflow({
      prompt: `Onboard ${employeeName} as ${roleTitle} in ${department} with submitted docs: ${submittedDocs.join(", ")}.`,
      workflow_hint: "employee-onboarding",
      structured_input: {
        employee_name: employeeName,
        role_title: roleTitle,
        department,
        submitted_documents: submittedDocs,
      },
    });
    setRunning(false);
    if (!res.ok) {
      setErrorMsg(res.error || "Onboarding execution failed");
    } else if (res.data) {
      setResult(res.data);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="hf-h1">Employee Onboarding</h1>
        <p className="hf-lede">
          Manage new-hire KYC verification, onboarding checklists, simulated IT SCIM provisioning,
          and team allocation approvals.
        </p>
      </div>

      {/* Pending Onboarding HITLs */}
      {onboardingApprovals.length > 0 && (
        <div className="space-y-3 rounded-[18px] border border-dashed border-[var(--esc)] bg-[var(--esc-soft)] p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-[var(--esc)]">
            <Clock className="h-4 w-4" />
            Pending Onboarding Approvals ({onboardingApprovals.length})
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {onboardingApprovals.map((ap) => (
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
                      resolveHitlApproval(ap.id, "approved", "Approved via Onboarding Page")
                    }
                    className="hf-btn hf-btn-primary hf-btn-sm"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Approve Provisioning
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      resolveHitlApproval(ap.id, "rejected", "Rejected via Onboarding Page")
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

      {/* Existing Onboarding Trackers */}
      <div className="grid gap-4 md:grid-cols-2">
        {onboardingWorkflows.length === 0 ? (
          <div className="hf-card col-span-2 text-xs text-[var(--muted)]">
            No active onboarding records yet. Use the form below to start onboarding a new hire.
          </div>
        ) : (
          onboardingWorkflows.map((wf) => (
            <div key={wf.id} className="hf-card">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-base font-bold text-[var(--ink)]">{wf.employee_name}</h3>
                  <p className="text-xs text-[var(--muted)]">
                    {wf.role_title} &bull; {wf.department}
                  </p>
                </div>
                <span className="hf-chip hf-chip-pass font-mono">{wf.progress_percent}%</span>
              </div>

              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-[var(--field)]">
                <div
                  className="h-full rounded-full bg-[var(--pass)] transition-all"
                  style={{ width: `${wf.progress_percent}%` }}
                />
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                {Object.entries(wf.documents_status).map(([docKey, docStat]) => (
                  <span
                    key={docKey}
                    className={`hf-chip ${
                      docStat === "verified" ? "hf-chip-pass" : "hf-chip-escalate"
                    }`}
                  >
                    {docKey}: {docStat}
                  </span>
                ))}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-[var(--ink-2)]">
                <div className="hf-subcard px-3 py-2">
                  <strong className="text-[var(--ink)]">IT SCIM:</strong>{" "}
                  {String(wf.it_provisioning?.scim_status || "draft")}
                </div>
                <div className="hf-subcard px-3 py-2">
                  <strong className="text-[var(--ink)]">Team Allocation:</strong>{" "}
                  {String(wf.team_allocation?.status || "pending")}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Start / Resume Onboarding Form */}
      <form onSubmit={handleRunOnboarding} className="hf-card space-y-4">
        <div className="flex items-center gap-2">
          <UserCheck className="h-4 w-4 text-[var(--pass)]" />
          <h2 className="hf-h2 mb-0">Start or Update New-Hire Onboarding</h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="hf-field">
            <label>Employee Name</label>
            <input
              type="text"
              required
              value={employeeName}
              onChange={(e) => setEmployeeName(e.target.value)}
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
            <label>Department</label>
            <input
              type="text"
              required
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="hf-input"
            />
          </div>
        </div>

        <div className="hf-field">
          <label>Submitted KYC Documents</label>
          <div className="mt-1 flex flex-wrap gap-2.5">
            {ALL_KYC_DOCS.map((doc) => (
              <label
                key={doc.key}
                className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--line)] bg-[var(--field)] px-3 py-2 text-xs font-medium text-[var(--ink)]"
              >
                <input
                  type="checkbox"
                  checked={submittedDocs.includes(doc.key)}
                  onChange={() => toggleDoc(doc.key)}
                  className="h-3.5 w-3.5 accent-[var(--pass)]"
                />
                {doc.label}
              </label>
            ))}
          </div>
        </div>

        <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
          {running ? "Processing Onboarding..." : "Execute Onboarding Workflow"}
        </button>
      </form>

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
