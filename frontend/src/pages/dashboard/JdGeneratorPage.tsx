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
    "Focus on multi-tenant APIs, deterministic guardrails, and technical mentorship."
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
  const markdownDoc = typeof out.formatted_job_description_markdown === "string"
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
        <h1 className="font-display text-2xl font-bold text-slate-900">
          Job Description Generator
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Generate structured, role-specific job descriptions grounded in your tenant leveling
          documents with automated inclusive-language linting.
        </p>
      </div>

      <form
        onSubmit={handleGenerate}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs"
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-xs font-semibold text-slate-700">Job Title</label>
            <input
              type="text"
              required
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">Department</label>
            <input
              type="text"
              required
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-slate-700">
              Required Skills (comma-separated)
            </label>
            <input
              type="text"
              required
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

        <div>
          <label className="text-xs font-semibold text-slate-700">Role Context &amp; Priorities</label>
          <textarea
            rows={3}
            value={extraContext}
            onChange={(e) => setExtraContext(e.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-200 px-3.5 py-2 text-sm outline-none focus:border-indigo-400"
          />
        </div>

        <button
          type="submit"
          disabled={running}
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-60"
        >
          <Sparkles className="h-4 w-4" />
          {running ? "Generating Job Description..." : "Generate Job Description"}
        </button>
      </form>

      {markdownDoc && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-indigo-600" />
              <h2 className="font-display text-base font-bold text-slate-900">
                Formatted Job Description
              </h2>
              {inclusiveScore !== undefined && (
                <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 font-mono text-xs font-semibold text-emerald-700">
                  Inclusive Score: {String(inclusiveScore)}/100
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={copyMarkdown}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? "Copied" : "Copy Markdown"}
            </button>
          </div>

          {findings.length > 0 && (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <strong>Inclusive Linter Notes:</strong>{" "}
              {findings
                .map((f) => `"${f.flagged_phrase}" -> "${f.suggested_replacement}"`)
                .join(" | ")}
            </div>
          )}

          <pre className="mt-4 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 font-sans text-sm leading-relaxed text-slate-800">
            {markdownDoc}
          </pre>
        </div>
      )}

      <ExecutionResultPanel result={result} errorMsg={errorMsg} />
    </div>
  );
};
