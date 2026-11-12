import React from "react";

type BadgeVariant = "indigo" | "blue" | "emerald" | "amber" | "rose" | "slate" | "purple";

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
  const variantClass =
    variant === "emerald"
      ? "hf-chip-pass"
      : variant === "amber"
        ? "hf-chip-escalate"
        : variant === "rose"
          ? "hf-chip-block"
          : "hf-chip-plain";

  return <span className={`hf-chip ${variantClass} ${className}`}>{children}</span>;
};
