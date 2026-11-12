import React from "react";

type BadgeVariant = "indigo" | "blue" | "emerald" | "amber" | "rose" | "slate" | "purple";

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  indigo: "bg-indigo-50 text-indigo-700 border-indigo-200/80",
  purple: "bg-purple-50 text-purple-700 border-purple-200/80",
  blue: "bg-blue-50 text-blue-700 border-blue-200/80",
  emerald: "bg-emerald-50 text-emerald-700 border-emerald-200/80",
  amber: "bg-amber-50 text-amber-800 border-amber-200/80",
  rose: "bg-rose-50 text-rose-700 border-rose-200/80",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "slate",
  className = "",
}) => {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium tracking-tight ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
