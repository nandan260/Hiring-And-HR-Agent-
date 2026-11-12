import React, { useState } from "react";
import { FileSearch, Play, ShieldCheck, Upload } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const ResumeScreeningPage: React.FC = () => {
  const { executeWorkflow, uploadKnowledgeDoc, workspace } = useApp();

  const [jobTitle, setJobTitle] = useState("Senior Backend Engineer");
  const [requiredSkills, setRequiredSkills] = useState("Python, FastAPI, PostgreSQL");
  const [preferredSkills, setPreferredSkills] = useState("LangGraph, Docker");
  const [minYears, setMinYears] = useState(4);
  const [blindMode, setBlindMode] = useState(
    workspace?.settings?.blind_screening_mode ?? true
  );
  const [resumeText, setResumeText] = useState("");
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleScreen = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    setResult(null);

    const attachments: string[] = [];
    if (resumeFile) {
      const fd = new FormData();
      fd.append("file", resumeFile);
      fd.append("title", `Resume: ${resumeFile.name}`);
      fd.append("source_type", "resume");
      fd.append("min_role_access", "business_admin");
      fd.append("workflow_slug", "recruitment-screening");
      const up = await uploadKnowledgeDoc(fd);
      if (!up.ok || !up.doc) {
        setRunning(false);
        setErrorMsg(up.error || "Resume file upload failed");
        return;
      }
      attachments.push(up.doc.id);
    }

    const reqList = requiredSkills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const prefList = preferredSkills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const prompt = `Screen candidate resumes for ${jobTitle} requiring ${reqList.join(", ")} with minimum ${minYears} years experience.`;
    const structured: Record<string, unknown> = {
      job_title: jobTitle,
      required_skills: reqList,
      preferred_skills: prefList,
      min_years_experience: Number(minYears) || 0,
      blind_screening: blindMode,
      resume_texts: resumeText.trim() ? [resumeText.trim()] : [],
      search_candidate_pool: true,
    };

    const res = await executeWorkflow({
      prompt,
      workflow_hint: "recruitment-screening",
      structured_input: structured,
      attachments,
    });
    setRunning(false);
    if (!res.ok) {
      setErrorMsg(res.error || "Resume screening blocked or failed");
    } else if (res.data) {
      setResult(res.data);
    }
  };

  const evaluations =
    ((result?.structured_output?.candidate_evaluations as Record<string, unknown>[]) || []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900">Resume Screening</h1>
          <p className="mt-1 text-sm text-slate-600">
            Upload a candidate resume (PDF/DOCX/TXT) or paste CV text to score skills, experience,
            and rubric fit via the Recruitment Screening workflow.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800">
          <ShieldCheck className="h-3.5 w-3.5" />
          Protected Attributes Excluded
        </span>
      </div>

      <form
        onSubmit={handleScreen}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-xs font-semibold text-slate-700">Target Role Title</label>
            <input
              type="text"
              required
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Minimum Experience (Years)
            </label>
            <input
              type="number"
              min={0}
              max={30}
              value={minYears}
              onChange={(e) => setMinYears(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Required Skills (comma-separated)
            </label>
            <input
              type="text"
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Preferred Skills (comma-separated)
            </label>
            <input
              type="text"
              value={preferredSkills}
              onChange={(e) => setPreferredSkills(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Upload Resume File (PDF, DOCX, TXT, MD — optional)
            </label>
            <label className="mt-1 flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-xs text-slate-600 hover:border-indigo-400">
              <Upload className="h-4 w-4 text-indigo-600" />
              <span className="truncate">
                {resumeFile ? resumeFile.name : "Choose resume file to upload & screen..."}
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                className="hidden"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              />
            </label>
          </div>

          <div className="flex items-end pb-2">
            <label className="inline-flex cursor-pointer items-center gap-2.5 text-xs font-semibold text-slate-800">
              <input
                type="checkbox"
                checked={blindMode}
                onChange={(e) => setBlindMode(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600"
              />
              Enable Blind Screening Mode (Redact Name, Email &amp; Phone in Report)
            </label>
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-700">
            Or Paste Inline Resume Text (Optional — leave blank to screen existing candidate pool)
          </label>
          <textarea
            rows={4}
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            placeholder="Jane Doe — 6 years backend engineering experience with Python, FastAPI, PostgreSQL, Docker, and LangGraph..."
            className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
          />
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={running}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:from-indigo-500 hover:to-blue-500 disabled:opacity-60"
          >
            {running ? <FileSearch className="h-4 w-4 animate-pulse" /> : <Play className="h-4 w-4" />}
            {running ? "Screening Resumes..." : "Run Resume Screening"}
          </button>
        </div>
      </form>

      {evaluations.length > 0 && (
        <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <h2 className="font-display text-base font-bold text-slate-900">
            Structured Screening Scorecard ({evaluations.length})
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {evaluations.map((ev, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-slate-900">
                    {String(ev.candidate_label || `Candidate #${idx + 1}`)}
                  </span>
                  <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 font-mono font-bold text-indigo-800">
                    {String(ev.match_score ?? 0)}% fit
                  </span>
                </div>
                <p className="mt-1 font-medium text-slate-700">{String(ev.recommendation || "")}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {((ev.matched_required_skills as string[]) || []).map((sk) => (
                    <span
                      key={sk}
                      className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800"
                    >
                      + {sk}
                    </span>
                  ))}
                  {((ev.missing_skills as string[]) || []).map((sk) => (
                    <span
                      key={sk}
                      className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-semibold text-rose-800"
                    >
                      - {sk}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
