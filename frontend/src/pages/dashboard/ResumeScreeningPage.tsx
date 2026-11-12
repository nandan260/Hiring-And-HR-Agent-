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
    Boolean(workspace?.settings.blind_screening_mode)
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
    (result?.structured_output?.candidate_evaluations as Record<string, unknown>[]) || [];

  return (
    <div className="space-y-6">
      <div className="hf-page-head mb-0">
        <div>
          <h1 className="hf-h1">Resume Screening</h1>
          <p className="hf-lede">
            Upload a candidate resume (PDF/DOCX/TXT) or paste CV text to score skills, experience,
            and job fit against structured requirements.
          </p>
        </div>
        <span className="hf-chip hf-chip-plain">
          <FileSearch className="h-3.5 w-3.5" />
          Internal Workflow: recruitment-screening
        </span>
      </div>

      <form onSubmit={handleScreen} className="hf-card space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="hf-field lg:col-span-2">
            <label>Target Role</label>
            <input
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              className="hf-input"
              required
            />
          </div>
          <div className="hf-field">
            <label>Minimum Years Experience</label>
            <input
              type="number"
              min={0}
              max={30}
              value={minYears}
              onChange={(e) => setMinYears(Number(e.target.value))}
              className="hf-input"
            />
          </div>
          <div className="flex items-end">
            <label className="flex w-full cursor-pointer items-center justify-between rounded-[var(--r-field)] border border-[var(--line)] bg-[var(--field)] px-3.5 py-2.5 text-xs font-medium text-[var(--ink)]">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-[var(--pass)]" />
                Blind Screening
              </span>
              <input
                type="checkbox"
                checked={blindMode}
                onChange={(e) => setBlindMode(e.target.checked)}
                className="accent-[var(--pass)]"
              />
            </label>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="hf-field">
            <label>Required Skills (comma-separated)</label>
            <input
              type="text"
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              className="hf-input"
            />
          </div>
          <div className="hf-field">
            <label>Preferred Skills (comma-separated)</label>
            <input
              type="text"
              value={preferredSkills}
              onChange={(e) => setPreferredSkills(e.target.value)}
              className="hf-input"
            />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="hf-field">
            <label>Upload Resume File (PDF, DOCX, TXT, MD &mdash; optional)</label>
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--line)] bg-[var(--field)] p-6 text-center transition hover:border-[var(--muted)] hover:bg-[var(--field-hover)]">
              <Upload className="h-5 w-5 text-[var(--ink)]" />
              <span className="mt-2 text-xs font-semibold text-[var(--ink)]">
                {resumeFile ? resumeFile.name : "Choose resume file to upload"}
              </span>
              <span className="mt-0.5 text-[11px] text-[var(--muted)]">
                Automatically parsed, chunked &amp; indexed with tenant RLS isolation
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md,.json,.csv"
                onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
                className="hidden"
              />
            </label>
          </div>

          <div className="hf-field">
            <label>Or Paste Resume Text Directly</label>
            <textarea
              rows={5}
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Jane Doe — 6 years backend engineering experience with Python, FastAPI, PostgreSQL, Docker, and LangGraph..."
              className="hf-input min-h-[124px]"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line)] pt-4">
          <span className="text-xs text-[var(--muted)]">
            If no file or text is provided, HireFlow AI evaluates all matching candidates already in
            your tenant pool.
          </span>
          <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
            <Play className="h-3.5 w-3.5" />
            {running ? "Screening Resumes..." : "Run Resume Screening"}
          </button>
        </div>
      </form>

      {evaluations.length > 0 && (
        <div className="hf-card space-y-3">
          <h2 className="hf-h2 mb-0">Candidate Screening Scorecard ({evaluations.length})</h2>
          <div className="grid gap-3 md:grid-cols-2">
            {evaluations.map((ev, idx) => (
              <div key={idx} className="hf-claim supported">
                <div className="bar" />
                <div className="min-w-0 pr-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-[var(--ink)]">
                      {String(ev.candidate_name || `Candidate ${idx + 1}`)}
                    </span>
                    <span className="hf-chip hf-chip-pass font-mono">
                      Score: {String(ev.match_score ?? 0)}%
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-[var(--ink-2)]">
                    {String(ev.summary || "")}
                  </p>
                  {Array.isArray(ev.matched_skills) && ev.matched_skills.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {(ev.matched_skills as string[]).map((s) => (
                        <span key={s} className="hf-chip hf-chip-plain">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
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
