import React from "react";
import { Link } from "react-router-dom";
import { DemoBanner } from "../../components/common/DemoBanner";
import { PublicFooter } from "../../components/layout/PublicFooter";
import { PublicNavbar } from "../../components/layout/PublicNavbar";
import { useApp } from "../../context/AppContext";

const WORKFLOW_LINKS = [
  { title: "Resume Screening", route: "/dashboard/screening" },
  { title: "JD Generator", route: "/dashboard/jd-generator" },
  { title: "Candidates", route: "/dashboard/candidates" },
  { title: "Interviews", route: "/dashboard/interviews" },
  { title: "Onboarding", route: "/dashboard/onboarding" },
  { title: "HR Assistant", route: "/dashboard/assistant" },
  { title: "HR Analytics", route: "/dashboard/analytics" },
];

export const LandingPage: React.FC = () => {
  const { session } = useApp();

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--bg)] text-[var(--fg)]">
      <PublicNavbar />

      <main className="mx-auto flex min-h-0 w-full max-w-5xl flex-1 flex-col justify-center gap-6 px-6">
        <DemoBanner />

        <div className="flex flex-col gap-4 border border-[var(--border)] rounded-[var(--r-panel)] p-8">
          <h1 className="text-4xl font-bold tracking-tight text-[var(--fg)] sm:text-5xl">
            Hiring &amp; HR AI Agent
          </h1>
          <div className="flex flex-wrap gap-3">
            <Link
              to={session.isLiveAuthenticated ? "/dashboard" : "/signin"}
              className="hf-btn hf-btn-primary"
            >
              {session.isLiveAuthenticated ? "Open Workspace" : "Sign In"}
            </Link>
            <Link to="/signin?tab=register" className="hf-btn">
              Register Workspace
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
          {WORKFLOW_LINKS.map((wf) => (
            <Link
              key={wf.route}
              to={session.isLiveAuthenticated ? wf.route : "/signin"}
              className="hf-subcard text-center text-xs font-semibold text-[var(--fg)] no-underline hover:bg-[var(--surface-hover)]"
            >
              {wf.title}
            </Link>
          ))}
        </div>
      </main>

      <PublicFooter />
    </div>
  );
};
