import React from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../../context/AppContext";

export const DemoBanner: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { backendStatus, session } = useApp();

  if (backendStatus.online && session.isLiveAuthenticated) {
    return (
      <div
        className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--line)] bg-[var(--field)] px-4 ${
          compact ? "py-2" : "py-2.5"
        } text-xs text-[var(--ink-2)]`}
      >
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-2 w-2 shrink-0 rounded-full bg-[var(--pass)]" />
          <ShieldCheck className="h-4 w-4 shrink-0 text-[var(--pass)]" />
          <span>
            <strong className="font-semibold text-[var(--ink)]">
              HireFlow AI Connected (PostgreSQL RLS + JWT):
            </strong>{" "}
            Organization{" "}
            <code className="rounded bg-[var(--panel)] px-1.5 py-0.5 font-mono font-medium text-[var(--ink)]">
              {session.tenantName}
            </code>{" "}
            &bull; Role{" "}
            <code className="font-mono font-medium text-[var(--ink)]">{session.role}</code> &bull;
            Calendar &amp; provisioning connectors use human-approved HITL drafts.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[color:var(--esc-soft)] bg-[var(--esc-soft)] px-4 ${
        compact ? "py-2" : "py-2.5"
      } text-xs text-[var(--ink)]`}
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--esc)]" />
        <span>
          {backendStatus.online
            ? "Sign in with a business account to load live PostgreSQL HR workflows, candidates, knowledge documents, and execution traces."
            : backendStatus.detail}
        </span>
      </div>
      <Link to="/signin" className="hf-btn hf-btn-primary hf-btn-sm">
        Sign In / Demo Accounts &rarr;
      </Link>
    </div>
  );
};
