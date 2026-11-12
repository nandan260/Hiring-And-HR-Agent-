import React, { useState } from "react";
import { Check, Copy, FileText, Sparkles } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { ExecutionResultPanel } from "../../components/common/ExecutionResultPanel";
import type { UnifiedExecuteResponse } from "../../types/agent";

export const JdGeneratorPage: React.FC = () => {
  const { executeWorkflow } = useApp();

  const [jobTitle, setJobTitle] = useState("Senior Backend Engineer");
  const [department, setDepartment] = useState("Platform Engineering");
  const [requiredSkills, setRequiredSkills] = useState("Python, FastAPI, PostgreSQL, LangGraph");
  const [preferredSkills, setPreferredSkills] = useState("Docker, Redis, Kubernetes");
  const [extraContext, setExtraContext] = useState(
    "Include inclusive language check, clear leveling expectations, and hybrid flexibility."
  );
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<UnifiedExecuteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setErrorMsg(null);
    setResult(null);

    const reqList = requiredSkills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const prefList = preferredSkills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    const res = await executeWorkflow({
      prompt: `Draft a structured job description for ${jobTitle} in ${department} requiring ${reqList.join(", ")}. ${extraContext}`,
      workflow_hint: "jd-generator",
      structured_input: {
        job_title: jobTitle,
        department,
        required_skills: reqList,
        preferred_skills: prefList,
      },
    });
    setRunning(false);
    if (!res.ok) {
      setErrorMsg(res.error || "Job description generation failed");
    } else if (res.data) {
      setResult(res.data);
    }
  };

  const out = result?.structured_output || {};
  const markdownDoc =
    typeof out.formatted_job_description_markdown === "string"
      ? out.formatted_job_description_markdown
      : "";
  const inclusiveScore = out.inclusive_language_score;
  const findings = (out.inclusive_language_findings as Record<string, string>[]) || [];

  const copyMarkdown = () => {
    if (!markdownDoc) return;
    navigator.clipboard?.writeText(markdownDoc);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="hf-h1">Job Description Generator</h1>
        <p className="hf-lede">
          Generate structured, role-specific job descriptions grounded in your tenant leveling
          rubric with automated inclusive language linting.
        </p>
      </div>

      <form onSubmit={handleGenerate} className="hf-card space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
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
              className="hf-input"
            />
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
            <label>Preferred Skills</label>
            <input
              type="text"
              value={preferredSkills}
              onChange={(e) => setPreferredSkills(e.target.value)}
              className="hf-input"
            />
          </div>
        </div>

        <div className="hf-field">
          <label>Additional Context &amp; Notes</label>
          <textarea
            rows={2}
            value={extraContext}
            onChange={(e) => setExtraContext(e.target.value)}
            className="hf-input"
          />
        </div>

        <div className="pt-1">
          <button type="submit" disabled={running} className="hf-btn hf-btn-primary">
            <Sparkles className="h-4 w-4" />
            {running ? "Generating Job Description..." : "Generate Job Description"}
          </button>
        </div>
      </form>

      {markdownDoc && (
        <div className="hf-card">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--line)] pb-3">
            <div className="flex items-center gap-2.5">
              <FileText className="h-4 w-4 text-[var(--ink)]" />
              <h2 className="hf-h2 mb-0">Formatted Job Description</h2>
              {inclusiveScore !== undefined && (
                <span className="hf-chip hf-chip-pass font-mono">
                  Inclusive Score: {String(inclusiveScore)}/100
                </span>
              )}
            </div>
            <button type="button" onClick={copyMarkdown} className="hf-btn hf-btn-sm">
              {copied ? (
                <Check className="h-3.5 w-3.5 text-[var(--pass)]" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              {copied ? "Copied" : "Copy Markdown"}
            </button>
          </div>

          {findings.length > 0 && (
            <div className="mt-3 rounded-xl border border-[color:var(--esc-soft)] bg-[var(--esc-soft)] p-3 text-xs text-[var(--ink)]">
              <strong className="text-[var(--esc)]">Inclusive Linter Notes:</strong>{" "}
              {findings
                .map((f) => `"${f.flagged_phrase}" -> "${f.suggested_replacement}"`)
                .join(" | ")}
            </div>
          )}

          <pre className="mt-4 whitespace-pre-wrap rounded-xl border border-[var(--line)] bg-[var(--field)] p-4 font-sans text-sm leading-relaxed text-[var(--ink)]">
            {markdownDoc}
          </pre>
        </div>
      )}

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
