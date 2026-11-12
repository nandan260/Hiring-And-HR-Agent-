import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Bot, Menu, ShieldCheck, X } from "lucide-react";
import { useApp } from "../../context/AppContext";

export const PublicNavbar: React.FC = () => {
  const { session } = useApp();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const navItems = [
    { label: "Capabilities", to: "/#capabilities" },
    { label: "Architecture", to: "/#architecture" },
    { label: "Security & RBAC", to: "/#security" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8">
        <Link to="/" className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-blue-600 text-white shadow-sm shadow-indigo-500/30">
            <Bot className="h-5 w-5" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-display text-lg font-bold tracking-tight text-slate-900">
              HireFlow AI
            </span>
            <span className="hidden rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-700 sm:inline-block">
              Hiring &amp; HR AI Agent
            </span>
          </div>
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          {navItems.map((item) => (
            <a
              key={item.to}
              href={item.to}
              className="text-sm font-medium text-slate-600 transition hover:text-slate-900"
            >
              {item.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
            <ShieldCheck className="h-3.5 w-3.5" />
            PostgreSQL RLS Isolated
          </span>
          {session.isLiveAuthenticated ? (
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:from-indigo-500 hover:to-blue-500"
            >
              Open HR Workspace →
            </Link>
          ) : (
            <>
              <Link
                to="/signin"
                className={`rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                  location.pathname === "/signin"
                    ? "bg-slate-100 text-slate-900"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                Sign In
              </Link>
              <Link
                to="/signin"
                className="rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:from-indigo-500 hover:to-blue-500"
              >
                Launch HireFlow AI
              </Link>
            </>
          )}
        </div>

        <button
          onClick={() => setMobileOpen((o) => !o)}
          className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 md:hidden"
          aria-label="Toggle Menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="space-y-2 border-t border-slate-100 bg-white px-4 py-4 md:hidden">
          {navItems.map((item) => (
            <a
              key={item.to}
              href={item.to}
              onClick={() => setMobileOpen(false)}
              className="block rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              {item.label}
            </a>
          ))}
          <div className="pt-2">
            <Link
              to={session.isLiveAuthenticated ? "/dashboard" : "/signin"}
              onClick={() => setMobileOpen(false)}
              className="block rounded-xl bg-indigo-600 px-4 py-2.5 text-center text-sm font-semibold text-white"
            >
              {session.isLiveAuthenticated ? "Open HR Workspace" : "Sign In / Get Started"}
            </Link>
          </div>
        </div>
      )}
    </header>
  );
};
