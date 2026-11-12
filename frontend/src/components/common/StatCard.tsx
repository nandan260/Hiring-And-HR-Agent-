import React from "react";

interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
  icon?: React.ReactNode;
  accent?: "indigo" | "blue" | "emerald" | "amber" | "purple";
}

export const StatCard: React.FC<StatCardProps> = ({ label, value, subtext }) => {
  return (
    <div className="hf-card">
      <p className="text-[11.5px] font-medium text-[var(--muted)]">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight text-[var(--fg)] tabular-nums">
        {value}
      </p>
      {subtext && <p className="mt-1 text-[11px] text-[var(--muted)]">{subtext}</p>}
    </div>
  );
};
