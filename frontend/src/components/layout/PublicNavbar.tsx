import React from "react";
import { Link } from "react-router-dom";
import { useApp } from "../../context/AppContext";
import { useTheme } from "../../utils/theme";

export const PublicNavbar: React.FC = () => {
  const { session } = useApp();
  const [theme, toggleTheme] = useTheme();

  return (
    <header className="flex flex-none items-center justify-between border-b border-[var(--border)] bg-[var(--bg)] px-6 py-3 text-[var(--fg)]">
      <Link to="/" className="text-base font-bold tracking-tight text-[var(--fg)] no-underline">
        HireFlow AI
      </Link>

      <div className="flex items-center gap-2">
        <button type="button" onClick={toggleTheme} className="hf-btn hf-btn-sm">
          {theme === "dark" ? "Light" : "Dark"}
        </button>
        {session.isLiveAuthenticated ? (
          <Link to="/dashboard" className="hf-btn hf-btn-primary hf-btn-sm">
            Workspace
          </Link>
        ) : (
          <Link to="/signin" className="hf-btn hf-btn-primary hf-btn-sm">
            Sign In
          </Link>
        )}
      </div>
    </header>
  );
};
