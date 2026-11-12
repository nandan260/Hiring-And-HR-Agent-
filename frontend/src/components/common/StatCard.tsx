import React from "react";

interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
  icon: React.ReactNode;
  accent?: "indigo" | "blue" | "emerald" | "amber" | "purple";
}

const ACCENT_STYLE = {
  indigo: "bg-[var(--field)] text-[var(--ink)] border-[var(--line)]",
  blue: "bg-[var(--field)] text-[var(--ink-2)] border-[var(--line)]",
  emerald: "bg-[var(--pass-soft)] text-[var(--pass)] border-transparent",
  amber: "bg-[var(--esc-soft)] text-[var(--esc)] border-transparent",
  purple: "bg-[var(--field)] text-[var(--ink-2)] border-[var(--line)]",
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subtext,
  icon,
  accent = "indigo",
}) => {
  return (
    <div className="hf-card transition-colors hover:border-[var(--muted)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[12.5px] font-medium text-[var(--muted)]">{label}</p>
          <p className="mt-1.5 text-[28px] font-bold leading-tight tracking-tight text-[var(--ink)] tabular-nums">
            {value}
          </p>
          {subtext && <p className="mt-1 text-xs text-[var(--muted)]">{subtext}</p>}
        </div>
        <div className={`shrink-0 rounded-xl border p-2.5 ${ACCENT_STYLE[accent]}`}>
          {icon}
        </div>
      </div>
    </div>
  );
};
