import type { HrWorkflowMeta } from "../types/agent";

export const HR_WORKFLOW_CATALOG: HrWorkflowMeta[] = [
  {
    slug: "recruitment-screening",
    name: "Recruitment & Resume Screening",
    shortLabel: "Screening",
    description:
      "Parse uploaded resumes, extract structured skills and experience, enforce optional blind PII screening, and score applicants against job rubrics.",
    routePath: "/dashboard/screening",
    requiresAdmin: true,
    samplePrompts: [
      "Screen backend candidates for Senior Backend Engineer requiring Python, FastAPI, PostgreSQL, and 4+ years experience.",
    ],
  },
  {
    slug: "jd-generator",
    name: "Job Description Generator",
    shortLabel: "JD Generator",
    description:
      "Draft structured, role-specific job descriptions grounded in internal leveling guides with automated inclusive-language linting.",
    routePath: "/dashboard/jd-generator",
    requiresAdmin: true,
    samplePrompts: [
      "Draft an inclusive Job Description for a Staff Platform Engineer requiring Kubernetes, Go, and distributed systems.",
    ],
  },
  {
    slug: "candidate-shortlisting",
    name: "Candidate Shortlisting",
    shortLabel: "Shortlisting",
    description:
      "Rank and compare talent pools on merit alone, highlight skill gaps transparently, block protected-attribute bias, and queue human sign-off.",
    routePath: "/dashboard/candidates",
    requiresAdmin: true,
    samplePrompts: [
      "Compare and shortlist the top 3 candidates for Senior Backend Engineer with Python, FastAPI, and PostgreSQL.",
    ],
  },
  {
    slug: "interview-scheduling",
    name: "Interview Scheduling",
    shortLabel: "Interviews",
    description:
      "Check interviewer availability, detect conflicts, propose structured interview slots, and draft calendar invites pending HITL approval.",
    routePath: "/dashboard/interviews",
    requiresAdmin: true,
    samplePrompts: [
      "Schedule a 45-minute technical interview round for Arnav Sharma with panel engineering-panel@acmecloud.io.",
    ],
  },
  {
    slug: "employee-onboarding",
    name: "Employee Onboarding",
    shortLabel: "Onboarding",
    description:
      "Track KYC verification progress, assign 30/60/90-day training plans, and submit IT provisioning & team allocation for human approval.",
    routePath: "/dashboard/onboarding",
    requiresAdmin: true,
    samplePrompts: [
      "Start employee onboarding for Priya Nair as Product Designer in Design with offer letter and Aadhaar verified.",
    ],
  },
  {
    slug: "hr-policy-support",
    name: "Employee Policy Support",
    shortLabel: "HR Policy RAG",
    description:
      "Answer employee handbook, PTO, parental leave, travel, and benefits questions with role-filtered pgvector citations.",
    routePath: "/dashboard/assistant",
    requiresAdmin: false,
    samplePrompts: [
      "How many days of PTO and paid parental leave do full-time employees receive?",
    ],
  },
  {
    slug: "hr-analytics",
    name: "HR Analytics",
    shortLabel: "HR Analytics",
    description:
      "Generate read-only, SQL-validated hiring funnel, time-to-hire, candidate match distribution, and workflow token reports.",
    routePath: "/dashboard/analytics",
    requiresAdmin: true,
    samplePrompts: [
      "Show the hiring pipeline funnel breakdown and active workflow token consumption report.",
    ],
  },
];
