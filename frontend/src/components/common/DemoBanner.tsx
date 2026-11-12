import React from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../../context/AppContext";

export const DemoBanner: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const { backendStatus, session } = useApp();

  if (backendStatus.online && session.isLiveAuthenticated) {
    return (
      <div
        className={`flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200 bg-emerald-50/80 px-4 ${
          compact ? "py-2" : "py-2.5"
        } text-xs text-emerald-900`}
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>
            <strong>HireFlow AI Connected (PostgreSQL RLS + JWT):</strong> Active organization{" "}
            <code className="rounded bg-emerald-100 px-1.5 py-0.5 font-mono font-semibold">
              {session.tenantName}
            </code>{" "}
            • Role <code className="font-mono font-semibold">{session.role}</code> • Calendar &amp;
            provisioning connectors use human-approved HITL drafts.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50/90 px-4 ${
        compact ? "py-2" : "py-2.5"
      } text-xs text-amber-950`}
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
        <span>
          {backendStatus.online
            ? "Sign in with a business account to load live PostgreSQL HR workflows, candidates, knowledge documents, and execution traces."
            : backendStatus.detail}
        </span>
      </div>
      <Link
        to="/signin"
        className="rounded-lg bg-amber-900 px-3 py-1 font-semibold text-white transition hover:bg-amber-800"
      >
        Sign In / Demo Accounts →
      </Link>
    </div>
  );
};
