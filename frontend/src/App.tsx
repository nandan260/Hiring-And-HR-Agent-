import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppProvider } from "./context/AppContext";
import { LandingPage } from "./pages/public/LandingPage";
import { SignInPage } from "./pages/public/SignInPage";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { OverviewPage } from "./pages/dashboard/OverviewPage";
import { RecruitmentPage } from "./pages/dashboard/RecruitmentPage";
import { ResumeScreeningPage } from "./pages/dashboard/ResumeScreeningPage";
import { CandidatesPage } from "./pages/dashboard/CandidatesPage";
import { JdGeneratorPage } from "./pages/dashboard/JdGeneratorPage";
import { InterviewsPage } from "./pages/dashboard/InterviewsPage";
import { OnboardingPage } from "./pages/dashboard/OnboardingPage";
import { HrAssistantPage } from "./pages/dashboard/HrAssistantPage";
import { HrAnalyticsPage } from "./pages/dashboard/HrAnalyticsPage";
import { ExecutionHistoryPage } from "./pages/dashboard/ExecutionHistoryPage";
import { KnowledgeBasePage } from "./pages/dashboard/KnowledgeBasePage";
import { ToolsIntegrationsPage } from "./pages/dashboard/ToolsIntegrationsPage";
import { SettingsPage } from "./pages/dashboard/SettingsPage";

export const App: React.FC = () => {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          {/* Public HireFlow AI Routes */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/signin" element={<SignInPage />} />

          {/* Authenticated Hiring & HR Workspace (13 Navigation Views) */}
          <Route path="/dashboard" element={<DashboardLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="recruitment" element={<RecruitmentPage />} />
            <Route path="screening" element={<ResumeScreeningPage />} />
            <Route path="candidates" element={<CandidatesPage />} />
            <Route path="jd-generator" element={<JdGeneratorPage />} />
            <Route path="interviews" element={<InterviewsPage />} />
            <Route path="onboarding" element={<OnboardingPage />} />
            <Route path="assistant" element={<HrAssistantPage />} />
            <Route path="analytics" element={<HrAnalyticsPage />} />
            <Route path="monitor" element={<ExecutionHistoryPage />} />
            <Route path="knowledge-base" element={<KnowledgeBasePage />} />
            <Route path="integrations" element={<ToolsIntegrationsPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>

          {/* Fallback removes any legacy marketplace paths */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
};

export default App;
