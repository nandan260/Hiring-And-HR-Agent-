import React from "react";
import { Link } from "react-router-dom";
import { useApp } from "../../context/AppContext";

export const DemoBanner: React.FC<{ compact?: boolean }> = () => {
  const { backendStatus } = useApp();

  if (backendStatus.online) {
    return null;
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs text-[var(--fg)]">
      <span>{backendStatus.detail}</span>
      <Link to="/signin" className="hf-btn hf-btn-primary hf-btn-sm">
        Sign In
      </Link>
    </div>
  );
};
