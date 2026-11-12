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
        <h1 className="font-display text-2xl font-bold text-slate-900">Employee Onboarding</h1>
        <p className="mt-1 text-sm text-slate-600">
          Manage new-hire KYC verification, onboarding checklists, simulated IT SCIM provisioning,
          and team allocation approvals.
        </p>
      </div>

      {/* Pending Onboarding HITLs */}
      {onboardingApprovals.length > 0 && (
        <div className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50/70 p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-950">
            <Clock className="h-4 w-4 text-amber-600" />
            Pending Onboarding Approvals ({onboardingApprovals.length})
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {onboardingApprovals.map((ap) => (
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
                    onClick={() => resolveHitlApproval(ap.id, "approved", "Approved via Onboarding Page")}
                    className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-500"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Approve Provisioning
                  </button>
                  <button
                    type="button"
                    onClick={() => resolveHitlApproval(ap.id, "rejected", "Rejected via Onboarding Page")}
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

      {/* Existing Onboarding Trackers */}
      <div className="grid gap-4 md:grid-cols-2">
        {onboardingWorkflows.length === 0 ? (
          <div className="col-span-2 rounded-2xl border border-slate-200 bg-white p-6 text-xs text-slate-500 shadow-xs">
            No active onboarding records yet. Use the form below to start onboarding a new hire.
          </div>
        ) : (
          onboardingWorkflows.map((wf) => (
            <div
              key={wf.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs"
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="font-display text-base font-bold text-slate-900">
                    {wf.employee_name}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {wf.role_title} • {wf.department}
                  </p>
                </div>
                <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 font-mono text-xs font-bold text-indigo-700">
                  {wf.progress_percent}%
                </span>
              </div>

              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-indigo-600"
                  style={{ width: `${wf.progress_percent}%` }}
                />
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                {Object.entries(wf.documents_status).map(([docKey, docStat]) => (
                  <span
                    key={docKey}
                    className={`rounded-full px-2 py-0.5 font-medium ${
                      docStat === "verified"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-amber-50 text-amber-800"
                    }`}
                  >
                    {docKey}: {docStat}
                  </span>
                ))}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-600">
                <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
                  <strong>IT SCIM:</strong> {String(wf.it_provisioning?.scim_status || "draft")}
                </div>
                <div className="rounded-lg bg-slate-50 px-2.5 py-1.5">
                  <strong>Team Allocation:</strong>{" "}
                  {String(wf.team_allocation?.status || "pending")}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Start / Resume Onboarding Form */}
      <form
        onSubmit={handleRunOnboarding}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="flex items-center gap-2">
          <UserCheck className="h-4 w-4 text-indigo-600" />
          <h2 className="font-display text-base font-bold text-slate-900">
            Start or Update New-Hire Onboarding
          </h2>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="text-xs font-semibold text-slate-700">Employee Name</label>
            <input
              type="text"
              required
              value={employeeName}
              onChange={(e) => setEmployeeName(e.target.value)}
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
            <label className="text-xs font-semibold text-slate-700">Department</label>
            <input
              type="text"
              required
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-700">Submitted KYC Documents</label>
          <div className="mt-2 flex flex-wrap gap-3">
            {ALL_KYC_DOCS.map((doc) => (
              <label
                key={doc.key}
                className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800"
              >
                <input
                  type="checkbox"
                  checked={submittedDocs.includes(doc.key)}
                  onChange={() => toggleDoc(doc.key)}
                  className="h-3.5 w-3.5 rounded text-indigo-600"
                />
                {doc.label}
              </label>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={running}
          className="rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          {running ? "Processing Onboarding..." : "Execute Onboarding Workflow"}
        </button>
      </form>

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
