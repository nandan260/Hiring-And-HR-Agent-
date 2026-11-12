import React, { useState } from "react";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import { useApp } from "../../context/AppContext";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const JdGeneratorPage: React.FC = () => {
  const { executeWorkflow } = useApp();
  const [jobTitle, setJobTitle] = useState("Senior Backend Engineer");
  const [department, setDepartment] = useState("Platform Engineering");
  const [requiredSkills, setRequiredSkills] = useState(
    "Python, FastAPI, PostgreSQL, Docker, REST APIs"
  );
  const [preferredSkills, setPreferredSkills] = useState("LangGraph, Redis, Kubernetes");
  const [extraContext, setExtraContext] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    const reqList = requiredSkills.split(",").map((s) => s.trim()).filter(Boolean);
    const prefList = preferredSkills.split(",").map((s) => s.trim()).filter(Boolean);

    const res = await executeWorkflow({
      prompt: `Generate an inclusive job description for ${jobTitle} in ${department} requiring ${reqList.join(", ")}. ${extraContext}`.trim(),
      workflow_hint: "jd-generator",
      structured_input: {
        job_title: jobTitle,
        department,
        required_skills: reqList,
        preferred_skills: prefList,
      },
    });
    setRunning(false);
    if (res.ok && res.data) {
      setResult(res.data);
    } else {
      setErrorMsg(res.error || "JD generation failed.");
    }
  };

  const jdMarkdown =
    (result?.structured_output?.formatted_job_description_markdown as string) || "";
  const inclusiveScore = result?.structured_output?.inclusive_language_score as number | undefined;
  const findings =
    (result?.structured_output?.inclusive_language_findings as Array<{
      flagged_term: string;
      suggestion: string;
    }>) || [];

  const copyJd = () => {
    if (!jdMarkdown) return;
    navigator.clipboard?.writeText(jdMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="hf-page-head">
        <h1 className="hf-h1">JD Generator</h1>
        {jdMarkdown && (
          <button type="button" onClick={copyJd} className="hf-btn hf-btn-sm">
            {copied ? "Copied" : "Copy Markdown"}
          </button>
        )}
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-12 gap-3">
        <form
          onSubmit={handleGenerate}
          className="hf-card col-span-12 flex min-h-0 flex-col gap-2.5 overflow-y-auto lg:col-span-5"
        >
          <div className="hf-field">
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
            <label>Notes</label>
            <textarea
              rows={3}
              value={extraContext}
              onChange={(e) => setExtraContext(e.target.value)}
              placeholder="Location, team context, expectations..."
              className="hf-input min-h-[72px] flex-1 resize-none"
            />
          </div>

          <button type="submit" disabled={running} className="hf-btn hf-btn-primary w-full">
            {running ? "Generating Job Description..." : "Generate Job Description"}
          </button>
        </form>

        <div className="hf-card col-span-12 flex min-h-0 flex-col gap-3 overflow-y-auto lg:col-span-7">
          {jdMarkdown ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="hf-h2">Draft</h2>
                {typeof inclusiveScore === "number" && (
                  <span className="hf-chip hf-chip-pass font-mono">
                    Bias Score {inclusiveScore}/100
                  </span>
                )}
              </div>

              {findings.length > 0 && (
                <div className="hf-subcard space-y-1 text-xs">
                  {findings.map((f, i) => (
                    <div key={i}>
                      <span className="font-mono text-[var(--fg)]">{f.flagged_term}</span> &rarr;{" "}
                      <span className="text-[var(--muted)]">{f.suggestion}</span>
                    </div>
                  ))}
                </div>
              )}

              <pre className="whitespace-pre-wrap rounded-[var(--r-field)] border border-[var(--border)] bg-[var(--surface)] p-3 font-sans text-xs leading-relaxed text-[var(--fg)]">
                {jdMarkdown}
              </pre>
            </>
          ) : null}

          {result || errorMsg ? (
            <ExecutionResultPanel result={result} errorMsg={errorMsg} title="JD Generation" />
          ) : (
            <div className="hf-empty my-auto">Generate a job description to review draft output.</div>
          )}
        </div>
      </div>
    </div>
  );
};
