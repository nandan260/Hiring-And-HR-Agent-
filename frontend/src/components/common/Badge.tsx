import React from "react";

type BadgeVariant = "indigo" | "blue" | "emerald" | "amber" | "rose" | "slate" | "purple";

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  indigo: "bg-[var(--field)] text-[var(--ink)] border-[var(--line)]",
  purple: "bg-[var(--field)] text-[var(--ink)] border-[var(--line)]",
  blue: "bg-[var(--field)] text-[var(--ink-2)] border-[var(--line)]",
  emerald: "bg-[var(--pass-soft)] text-[var(--pass)] border-[color:var(--pass-soft)]",
  amber: "bg-[var(--esc-soft)] text-[var(--esc)] border-[color:var(--esc-soft)]",
  rose: "bg-[var(--block-soft)] text-[var(--block)] border-[color:var(--block-soft)]",
  slate: "bg-[var(--field)] text-[var(--ink-2)] border-[var(--line)]",
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
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-tight ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
};
