import React, { useEffect } from "react";
import { X } from "lucide-react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  maxWidth?: string;
  children: React.ReactNode;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  maxWidth = "max-w-2xl",
  children,
}) => {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-xs">
      <div
        className={`w-full ${maxWidth} animate-fade-in overflow-hidden rounded-[20px] border border-[var(--line)] bg-[var(--panel)] text-[var(--ink)] shadow-2xl`}
      >
        <div className="flex items-start justify-between border-b border-[var(--line)] px-6 py-4">
          <div>
            <h3 className="text-lg font-bold tracking-tight text-[var(--ink)]">{title}</h3>
            {subtitle && <p className="mt-0.5 text-sm text-[var(--muted)]">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="hf-icon-btn h-8 w-8"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[82vh] overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
};
