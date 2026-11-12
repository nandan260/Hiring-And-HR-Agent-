import React, { useState } from "react";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const ResumeScreeningPage: React.FC = () => {
  const { executeWorkflow, uploadKnowledgeDoc, workspace } = useApp();
  const [jobTitle, setJobTitle] = useState("Senior Backend Engineer");
  const [requiredSkills, setRequiredSkills] = useState("Python, FastAPI, PostgreSQL, Docker");
  const [preferredSkills, setPreferredSkills] = useState("Kubernetes, Redis, LangGraph");
  const [minYears, setMinYears] = useState(4);
  const [blindMode, setBlindMode] = useState<boolean>(
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
    const attachments: string[] = [];

    if (resumeFile) {
      const fd = new FormData();
      fd.append("file", resumeFile);
      fd.append("category", "resume");
      fd.append("title", `Resume Upload - ${resumeFile.name}`);
      const up = await uploadKnowledgeDoc(fd);
      if (up.ok && up.doc) {
        attachments.push(up.doc.id);
      } else {
        setRunning(false);
        setErrorMsg(up.error || "Resume upload failed.");
        return;
      }
    }

    const reqSkills = requiredSkills.split(",").map((s) => s.trim()).filter(Boolean);
    const prefSkills = preferredSkills.split(",").map((s) => s.trim()).filter(Boolean);

    const res = await executeWorkflow({
      prompt: `Screen resumes for ${jobTitle} requiring ${reqSkills.join(", ")}${blindMode ? " using blind screening" : ""}`,
      workflow_hint: "recruitment-screening",
      structured_input: {
        job_title: jobTitle,
        required_skills: reqSkills,
        preferred_skills: prefSkills,
        min_years_experience: Number(minYears) || 0,
        blind_screening: blindMode,
        resume_texts: resumeText.trim() ? [resumeText.trim()] : [],
        search_candidate_pool: true,
      },
      attachments,
    });

    setRunning(false);
    if (res.ok && res.data) {
      setResult(res.data);
    } else {
      setErrorMsg(res.error || "Resume screening failed.");
    }
  };

  const evaluations =
    (result?.structured_output?.candidate_evaluations as Array<{
      candidate_name?: string;
      match_score?: number;
      recommendation?: string;
      matched_skills?: string[];
      missing_skills?: string[];
    }>) || [];

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">Resume Screening</h1>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
        <form
          onSubmit={handleScreen}
          className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 overflow-y-auto lg:col-span-5"
        >
          <div className="grid grid-cols-3 gap-2">
            <div className="hf-field col-span-2">
              <label>Job Title</label>
              <input
                type="text"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
                required
                className="hf-input"
              />
            </div>
            <div className="hf-field">
              <label>Min Years</label>
              <input
                type="number"
                min={0}
                max={30}
                value={minYears}
                onChange={(e) => setMinYears(Number(e.target.value))}
                className="hf-input"
              />
            </div>
          </div>

          <div className="hf-field">
            <label>Required Skills</label>
            <input
              type="text"
              value={requiredSkills}
              onChange={(e) => setRequiredSkills(e.target.value)}
              required
              className="hf-input"
            />
          </div>

          <div className="hf-field">
            <label>Preferred Skills</label>
            <input
              type="text"
              value={preferredSkills}
              onChange={(e) => setPreferredSkills(e.target.value)}
              className="hf-input"
            />
          </div>

          <div className="hf-field flex min-h-0 flex-1 flex-col">
            <label>Resume Text</label>
            <textarea
              rows={4}
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Paste resume text (e.g., Jane Doe, 6 years Python, FastAPI, PostgreSQL...)"
              className="hf-input min-h-[88px] flex-1 resize-none"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
              className="max-w-[210px] text-xs text-[var(--muted)] file:mr-2 file:rounded-[var(--r-field)] file:border file:border-[var(--border)] file:bg-[var(--surface)] file:px-2 file:py-1 file:text-xs file:font-medium file:text-[var(--fg)]"
            />
            <label className="flex items-center gap-1.5 text-xs text-[var(--fg)]">
              <input
                type="checkbox"
                checked={blindMode}
                onChange={(e) => setBlindMode(e.target.checked)}
                className="h-3.5 w-3.5 accent-[var(--fg)]"
              />
              Blind Mode
            </label>
          </div>

          <button type="submit" disabled={running} className="hf-btn hf-btn-primary w-full">
            {running ? "Screening Resumes..." : "Run Resume Screening"}
          </button>
        </form>

        <div className="hf-card col-span-12 flex min-h-0 flex-col gap-3 overflow-y-auto lg:col-span-7">
          {evaluations.length > 0 && (
            <div className="space-y-2">
              {evaluations.map((ev, idx) => (
                <div key={idx} className="hf-subcard flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-[var(--fg)]">
                      {ev.candidate_name || "Candidate"}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1 text-[11px] font-mono text-[var(--muted)]">
                      {ev.matched_skills?.map((s) => (
                        <span key={s} className="hf-chip hf-chip-pass">
                          +{s}
                        </span>
                      ))}
                      {ev.missing_skills?.map((s) => (
                        <span key={s} className="hf-chip hf-chip-block">
                          -{s}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-lg font-bold text-[var(--fg)]">
                      {ev.match_score ?? 0}%
                    </div>
                    <div className="text-[11px] text-[var(--muted)]">{ev.recommendation || "—"}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {result || errorMsg ? (
            <ExecutionResultPanel result={result} errorMsg={errorMsg} title="Screening" />
          ) : (
            <div className="hf-empty my-auto">Run screening to view candidate match scores.</div>
          )}
        </div>
      </div>
    </div>
  );
};
