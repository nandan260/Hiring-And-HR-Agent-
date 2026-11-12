import React from "react";

export const PublicFooter: React.FC = () => {
  return (
    <footer className="flex flex-none items-center justify-between border-t border-[var(--border)] bg-[var(--bg)] px-6 py-2.5 text-xs text-[var(--muted)]">
      <span>HireFlow AI</span>
      <span>PostgreSQL RLS &bull; RBAC &bull; HITL</span>
    </footer>
  );
};
