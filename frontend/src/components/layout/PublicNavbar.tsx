import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, Moon, ShieldCheck, Sun, X } from "lucide-react";
import { useApp } from "../../context/AppContext";
import { useTheme } from "../../utils/theme";

const BrandLogo: React.FC = () => (
  <svg
    width="22"
    height="22"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" />
    <path d="M8.5 12l2.5 2.5 4.5-5" />
  </svg>
);

export const PublicNavbar: React.FC = () => {
  const { session } = useApp();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();

  const navItems = [
    { label: "Capabilities", to: "/#capabilities" },
    { label: "Architecture", to: "/#architecture" },
    { label: "Security & RBAC", to: "/#security" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--line)] bg-[var(--panel)]/95 backdrop-blur-md text-[var(--ink)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-2.5 text-[var(--ink)] no-underline">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--line)] bg-[var(--field)] text-[var(--ink)]">
            <BrandLogo />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[17px] font-bold tracking-tight text-[var(--ink)]">
              HireFlow AI
            </span>
            <span className="hf-chip hf-chip-plain hidden sm:inline-flex">
              Hiring &amp; HR AI Agent
            </span>
          </div>
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          {navItems.map((item) => (
            <a
              key={item.to}
              href={item.to}
              className="text-sm font-medium text-[var(--ink-2)] no-underline transition hover:text-[var(--ink)]"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2.5 md:flex">
          <span className="hf-chip hf-chip-pass">
            <ShieldCheck className="h-3.5 w-3.5" />
            PostgreSQL RLS
          </span>
          <button
            type="button"
            onClick={toggleTheme}
            className="hf-icon-btn"
            aria-label="Toggle theme"
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          {session.isLiveAuthenticated ? (
            <Link to="/dashboard" className="hf-btn hf-btn-primary">
              Open HR Workspace &rarr;
            </Link>
          ) : (
            <>
              <Link
                to="/signin"
                className={`hf-btn ${location.pathname === "/signin" ? "bg-[var(--field-hover)]" : ""}`}
              >
                Sign In
              </Link>
              <Link to="/signin?tab=register" className="hf-btn hf-btn-primary">
                Get Started
              </Link>
            </>
          )}
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <button
            type="button"
            onClick={toggleTheme}
            className="hf-icon-btn"
            aria-label="Toggle theme"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setMobileOpen((o) => !o)}
            className="hf-icon-btn"
            aria-label="Toggle Menu"
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="space-y-2 border-t border-[var(--line)] bg-[var(--panel)] px-4 pb-4 pt-3 md:hidden">
          {navItems.map((item) => (
            <a
              key={item.to}
              href={item.to}
              onClick={() => setMobileOpen(false)}
              className="block rounded-xl px-3 py-2 text-sm font-medium text-[var(--ink-2)] no-underline hover:bg-[var(--field)] hover:text-[var(--ink)]"
            >
              {item.label}
            </a>
          ))}
          <div className="pt-2">
            <Link
              to={session.isLiveAuthenticated ? "/dashboard" : "/signin"}
              onClick={() => setMobileOpen(false)}
              className="hf-btn hf-btn-primary w-full"
            >
              {session.isLiveAuthenticated ? "Open HR Workspace" : "Sign In / Get Started"}
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};
