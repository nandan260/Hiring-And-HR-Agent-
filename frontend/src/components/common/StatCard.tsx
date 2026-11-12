import React from "react";

interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
  icon: React.ReactNode;
  accent?: "indigo" | "blue" | "emerald" | "amber" | "purple";
}

const ACCENT_BG = {
  indigo: "bg-indigo-50 text-indigo-600",
  blue: "bg-blue-50 text-blue-600",
  emerald: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
  purple: "bg-purple-50 text-purple-600",
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subtext,
  icon,
  accent = "indigo",
}) => {
  return (
    <div className="rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs transition hover:border-indigo-200 hover:shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
          <p className="mt-2 font-display text-2xl font-bold tracking-tight text-slate-900">
            {value}
          </p>
          {subtext && <p className="mt-1 text-xs text-slate-500">{subtext}</p>}
        </div>
        <div className={`rounded-xl p-2.5 ${ACCENT_BG[accent]}`}>{icon}</div>
      </div>
    </div>
  );
};
