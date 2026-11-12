import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiClient, type BackendTokenResponse } from "../services/apiClient";
import type {
  AuditLogItem,
  CandidateRecord,
  ExecutionMonitorSnapshot,
  HitlApprovalRecord,
  InterviewRecordItem,
  McpServersPayload,
  OnboardingRecordItem,
  OrganizationMemberItem,
  RuntimesListPayload,
  StructuredHrToolSpec,
  TenantSession,
  UnifiedConversationSummary,
  UnifiedExecuteResponse,
  UnifiedExecutionRecord,
  UnifiedIntegrationItem,
  UnifiedKnowledgeDoc,
  UnifiedMessageTurnResult,
  UnifiedUsageBreakdown,
  UnifiedWorkspaceData,
  UserRole,
} from "../types/agent";

const STORAGE_KEY = "hireflow_hr_agent_auth_v1";

interface StoredAuth {
  authToken?: string;
  apiBaseUrl: string;
  session: TenantSession;
}

const DEFAULT_SESSION: TenantSession = {
  tenantId: "",
  tenantName: "Not signed in",
  tenantSlug: "unauthenticated",
  userEmail: "",
  userName: "Guest User",
  role: "business_employee",
  isSignedIn: false,
  isLiveAuthenticated: false,
};

function loadStoredAuth(): StoredAuth {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as StoredAuth;
      if (parsed.apiBaseUrl) {
        apiClient.setConfig({
          baseUrl: parsed.apiBaseUrl,
          authToken: parsed.authToken,
          liveModeEnabled: true,
        });
      }
      if (parsed.authToken && parsed.session?.isLiveAuthenticated) {
        return parsed;
      }
    }
  } catch {
    // ignore invalid localStorage data
  }
  return {
    authToken: undefined,
    apiBaseUrl: apiClient.getConfig().baseUrl,
    session: DEFAULT_SESSION,
  };
}

interface AppContextValue {
  session: TenantSession;
  authToken?: string;
  apiBaseUrl: string;
  backendStatus: { online: boolean; detail: string };
  loadingWorkspace: boolean;
  lastActionError: string | null;
  clearLastActionError: () => void;
  setLastActionError: (msg: string | null) => void;
  workspace: UnifiedWorkspaceData | null;
  candidates: CandidateRecord[];
  interviews: InterviewRecordItem[];
  onboardingWorkflows: OnboardingRecordItem[];
  approvals: HitlApprovalRecord[];
  knowledgeDocs: UnifiedKnowledgeDoc[];
  integrations: UnifiedIntegrationItem[];
  executions: UnifiedExecutionRecord[];
  usageStats: UnifiedUsageBreakdown | null;
  conversations: UnifiedConversationSummary[];
  organizationMembers: OrganizationMemberItem[];
  auditLogs: AuditLogItem[];
  monitorSnapshot: ExecutionMonitorSnapshot | null;
  runtimesInfo: RuntimesListPayload | null;
  structuredTools: StructuredHrToolSpec[];
  mcpData: McpServersPayload | null;
  refreshRuntimeData: () => Promise<void>;
  loginLive: (payload: {
    email: string;
    password: string;
    organizationSlug?: string;
  }) => Promise<{ ok: boolean; error?: string }>;
  registerBusinessLive: (payload: {
    fullName: string;
    email: string;
    password: string;
    organizationName: string;
    industry: string;
  }) => Promise<{ ok: boolean; error?: string }>;
  signOut: () => void;
  setApiBaseUrl: (baseUrl: string) => void;
  refreshWorkspaceData: () => Promise<void>;
  executeWorkflow: (payload: {
    prompt: string;
    workflow_hint?: string;
    structured_input?: Record<string, unknown>;
    attachments?: string[];
  }) => Promise<{ ok: boolean; data?: UnifiedExecuteResponse; error?: string }>;
  createConversation: (title: string) => Promise<UnifiedConversationSummary | null>;
  sendConversationTurn: (
    conversationId: string,
    payload: { content: string; workflow_hint?: string; attachments?: string[] }
  ) => Promise<{ ok: boolean; data?: UnifiedMessageTurnResult; error?: string }>;
  uploadKnowledgeDoc: (formData: FormData) => Promise<{ ok: boolean; doc?: UnifiedKnowledgeDoc; error?: string }>;
  deleteKnowledgeDoc: (docId: string) => Promise<boolean>;
  toggleIntegrationPermission: (permissionId: string, isAllowed: boolean) => Promise<boolean>;
  bindIntegrationCredential: (permissionId: string, secret: string) => Promise<boolean>;
  updateWorkspaceSettings: (payload: {
    blind_screening_mode?: boolean;
    strict_pii_masking?: boolean;
    require_hitl_approval?: boolean;
    model_routing_tier?: "tier_0_rule" | "tier_1_fast" | "tier_2_reasoning" | "auto_cascade";
    monthly_token_quota?: number;
    custom_persona_prompt?: string;
  }) => Promise<{ ok: boolean; error?: string }>;
  resolveHitlApproval: (
    approvalId: string,
    decision: "approved" | "rejected",
    resolutionNote?: string
  ) => Promise<boolean>;
  inviteMember: (payload: {
    fullName: string;
    email: string;
    password: string;
    role: "business_owner" | "business_admin" | "business_employee";
  }) => Promise<{ ok: boolean; error?: string }>;
  updateMemberRole: (
    memberId: string,
    role: "business_owner" | "business_admin" | "business_employee",
    isActive: boolean
  ) => Promise<boolean>;
}

const AppContext = createContext<AppContextValue | null>(null);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [initial] = useState<StoredAuth>(() => loadStoredAuth());
  const [authToken, setAuthToken] = useState<string | undefined>(initial.authToken);
  const [apiBaseUrl, setApiBaseUrlState] = useState<string>(initial.apiBaseUrl);
  const [session, setSession] = useState<TenantSession>(initial.session);
  const [backendStatus, setBackendStatus] = useState<{ online: boolean; detail: string }>({
    online: false,
    detail: "Checking FastAPI backend...",
  });
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [lastActionError, setLastActionError] = useState<string | null>(null);

  const [workspace, setWorkspace] = useState<UnifiedWorkspaceData | null>(null);
  const [candidates, setCandidates] = useState<CandidateRecord[]>([]);
  const [interviews, setInterviews] = useState<InterviewRecordItem[]>([]);
  const [onboardingWorkflows, setOnboardingWorkflows] = useState<OnboardingRecordItem[]>([]);
  const [approvals, setApprovals] = useState<HitlApprovalRecord[]>([]);
  const [knowledgeDocs, setKnowledgeDocs] = useState<UnifiedKnowledgeDoc[]>([]);
  const [integrations, setIntegrations] = useState<UnifiedIntegrationItem[]>([]);
  const [executions, setExecutions] = useState<UnifiedExecutionRecord[]>([]);
  const [usageStats, setUsageStats] = useState<UnifiedUsageBreakdown | null>(null);
  const [conversations, setConversations] = useState<UnifiedConversationSummary[]>([]);
  const [organizationMembers, setOrganizationMembers] = useState<OrganizationMemberItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [monitorSnapshot, setMonitorSnapshot] = useState<ExecutionMonitorSnapshot | null>(null);
  const [runtimesInfo, setRuntimesInfo] = useState<RuntimesListPayload | null>(null);
  const [structuredTools, setStructuredTools] = useState<StructuredHrToolSpec[]>([]);
  const [mcpData, setMcpData] = useState<McpServersPayload | null>(null);

  useEffect(() => {
    try {
      const payload: StoredAuth = { authToken, apiBaseUrl, session };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // ignore storage errors
    }
  }, [authToken, apiBaseUrl, session]);

  const clearDomainState = useCallback(() => {
    setWorkspace(null);
    setCandidates([]);
    setInterviews([]);
    setOnboardingWorkflows([]);
    setApprovals([]);
    setKnowledgeDocs([]);
    setIntegrations([]);
    setExecutions([]);
    setUsageStats(null);
    setConversations([]);
    setOrganizationMembers([]);
    setAuditLogs([]);
    setMonitorSnapshot(null);
    setRuntimesInfo(null);
    setStructuredTools([]);
    setMcpData(null);
  }, []);

  const refreshRuntimeData = useCallback(async () => {
    const cfg = apiClient.getConfig();
    if (!cfg.authToken) return;
    try {
      const [monData, rtData, toolData, mcpServersData] = await Promise.all([
        apiClient.getMonitorSnapshot(30),
        apiClient.listRuntimes(),
        apiClient.listStructuredTools(true),
        apiClient.listMcpServers(),
      ]);
      setMonitorSnapshot(monData);
      setRuntimesInfo(rtData);
      setStructuredTools(toolData);
      setMcpData(mcpServersData);
    } catch {
      // ignore if user role or network restricts telemetry
    }
  }, []);

  const refreshWorkspaceData = useCallback(async () => {
    const cfg = apiClient.getConfig();
    if (!cfg.authToken) return;
    setLoadingWorkspace(true);
    try {
      const [
        wsData,
        candData,
        ivData,
        onbData,
        hitlData,
        kbData,
        intData,
        execData,
        usageData,
        convData,
        memberData,
      ] = await Promise.all([
        apiClient.getHrWorkspace(),
        apiClient.listCandidates(),
        apiClient.listInterviews(),
        apiClient.listOnboarding(),
        apiClient.listHitlApprovals(),
        apiClient.listHrKnowledge(),
        apiClient.listHrIntegrations(),
        apiClient.listHrExecutions(),
        apiClient.getHrUsage(),
        apiClient.listHrConversations(),
        apiClient.listOrganizationMembers(),
      ]);

      setWorkspace(wsData);
      setCandidates(candData);
      setInterviews(ivData);
      setOnboardingWorkflows(onbData);
      setApprovals(hitlData);
      setKnowledgeDocs(kbData);
      setIntegrations(intData);
      setExecutions(execData);
      setUsageStats(usageData);
      setConversations(convData);
      setOrganizationMembers(
        memberData.map((m) => ({
          memberId: m.member_id,
          userId: m.user_id,
          email: m.email,
          fullName: m.full_name,
          role: m.role as UserRole,
          isActive: m.is_active,
          createdAt: m.created_at,
        }))
      );

      if (["business_owner", "business_admin", "platform_admin"].includes(wsData.role)) {
        try {
          const auditDto = await apiClient.listAuditLogs();
          setAuditLogs(
            auditDto.map((a) => ({
              id: a.id,
              tenantId: a.tenant_id,
              actorUserId: a.actor_user_id,
              rentalId: a.rental_id,
              action: a.action,
              resourceType: a.resource_type,
              resourceId: a.resource_id,
              status: a.status,
              ipAddress: a.ip_address,
              metadataJson: a.metadata_json,
              createdAt: a.created_at,
            }))
          );
        } catch {
          setAuditLogs([]);
        }
      } else {
        setAuditLogs([]);
      }
      await refreshRuntimeData();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load HR workspace";
      if (msg.includes("401")) {
        apiClient.setConfig({ authToken: undefined });
        setAuthToken(undefined);
        setSession(DEFAULT_SESSION);
        clearDomainState();
      } else {
        setLastActionError(msg);
      }
    } finally {
      setLoadingWorkspace(false);
    }
  }, [clearDomainState]);

  useEffect(() => {
    let cancelled = false;
    apiClient.checkBackendHealth().then(async (status) => {
      if (cancelled) return;
      setBackendStatus(status);
      if (status.online && apiClient.getConfig().authToken) {
        try {
          const me = await apiClient.getMe();
          if (cancelled) return;
          setSession({
            tenantId: me.tenant_id,
            tenantName: me.organization_name,
            tenantSlug: me.organization_slug,
            userEmail: me.email,
            userName: me.full_name,
            role: me.role,
            isSignedIn: true,
            isLiveAuthenticated: true,
          });
          await refreshWorkspaceData();
        } catch {
          if (cancelled) return;
          apiClient.setConfig({ authToken: undefined });
          setAuthToken(undefined);
          setSession(DEFAULT_SESSION);
          clearDomainState();
        }
      }
    });
    return () => {
      cancelled = true;
    };
  }, [clearDomainState, refreshWorkspaceData]);

  const applyAuthResponse = useCallback((tokenResp: BackendTokenResponse) => {
    apiClient.setConfig({ authToken: tokenResp.access_token });
    setAuthToken(tokenResp.access_token);
    setSession({
      tenantId: tokenResp.user.tenant_id,
      tenantName: tokenResp.user.organization_name,
      tenantSlug: tokenResp.user.organization_slug,
      userEmail: tokenResp.user.email,
      userName: tokenResp.user.full_name,
      role: tokenResp.user.role,
      isSignedIn: true,
      isLiveAuthenticated: true,
    });
  }, []);

  const loginLive: AppContextValue["loginLive"] = async (payload) => {
    setLastActionError(null);
    try {
      const resp = await apiClient.login({
        email: payload.email,
        password: payload.password,
        organization_slug: payload.organizationSlug,
      });
      applyAuthResponse(resp);
      await refreshWorkspaceData();
      return { ok: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      setLastActionError(msg);
      return { ok: false, error: msg };
    }
  };

  const registerBusinessLive: AppContextValue["registerBusinessLive"] = async (payload) => {
    setLastActionError(null);
    try {
      const resp = await apiClient.registerBusiness({
        full_name: payload.fullName,
        email: payload.email,
        password: payload.password,
        organization_name: payload.organizationName,
        industry: payload.industry,
      });
      applyAuthResponse(resp);
      await refreshWorkspaceData();
      return { ok: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      setLastActionError(msg);
      return { ok: false, error: msg };
    }
  };

  const signOut = () => {
    if (authToken) {
      apiClient.logout().catch(() => {});
    }
    apiClient.setConfig({ authToken: undefined });
    setAuthToken(undefined);
    setSession(DEFAULT_SESSION);
    clearDomainState();
  };

  const setApiBaseUrl = (baseUrl: string) => {
    setApiBaseUrlState(baseUrl);
    apiClient.setConfig({ baseUrl });
    apiClient.checkBackendHealth().then(setBackendStatus);
  };

  const executeWorkflow: AppContextValue["executeWorkflow"] = async (payload) => {
    setLastActionError(null);
    try {
      const res = await apiClient.executeHrAgent(payload);
      await refreshWorkspaceData();
      return { ok: true, data: res };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Workflow execution failed";
      setLastActionError(msg);
      await refreshWorkspaceData();
      return { ok: false, error: msg };
    }
  };

  const createConversation: AppContextValue["createConversation"] = async (title) => {
    setLastActionError(null);
    try {
      const conv = await apiClient.createHrConversation(title);
      setConversations((prev) => [conv, ...prev]);
      return conv;
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to create conversation");
      return null;
    }
  };

  const sendConversationTurn: AppContextValue["sendConversationTurn"] = async (
    conversationId,
    payload
  ) => {
    setLastActionError(null);
    try {
      const data = await apiClient.postHrConversationMessage(conversationId, payload);
      await refreshWorkspaceData();
      return { ok: true, data };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to send message";
      setLastActionError(msg);
      await refreshWorkspaceData();
      return { ok: false, error: msg };
    }
  };

  const uploadKnowledgeDoc: AppContextValue["uploadKnowledgeDoc"] = async (formData) => {
    setLastActionError(null);
    try {
      const doc = await apiClient.uploadHrKnowledge(formData);
      await refreshWorkspaceData();
      return { ok: true, doc };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setLastActionError(msg);
      return { ok: false, error: msg };
    }
  };

  const deleteKnowledgeDoc: AppContextValue["deleteKnowledgeDoc"] = async (docId) => {
    setLastActionError(null);
    try {
      await apiClient.deleteHrKnowledge(docId);
      await refreshWorkspaceData();
      return true;
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Delete failed");
      return false;
    }
  };

  const toggleIntegrationPermission: AppContextValue["toggleIntegrationPermission"] = async (
    permissionId,
    isAllowed
  ) => {
    setLastActionError(null);
    try {
      await apiClient.toggleHrIntegration(permissionId, isAllowed, true);
      await refreshWorkspaceData();
      return true;
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to update tool permission");
      return false;
    }
  };

  const bindIntegrationCredential: AppContextValue["bindIntegrationCredential"] = async (
    permissionId,
    secret
  ) => {
    setLastActionError(null);
    try {
      await apiClient.bindHrIntegrationCredential(permissionId, secret, true);
      await refreshWorkspaceData();
      return true;
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to bind secret");
      return false;
    }
  };

  const updateWorkspaceSettings: AppContextValue["updateWorkspaceSettings"] = async (payload) => {
    setLastActionError(null);
    try {
      await apiClient.updateHrSettings(payload);
      await refreshWorkspaceData();
      return { ok: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update settings";
      setLastActionError(msg);
      return { ok: false, error: msg };
    }
  };

  const resolveHitlApproval: AppContextValue["resolveHitlApproval"] = async (
    approvalId,
    decision,
    resolutionNote
  ) => {
    setLastActionError(null);
    try {
      await apiClient.resolveHitlApproval(approvalId, decision, resolutionNote);
      await refreshWorkspaceData();
      return true;
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to resolve approval");
      return false;
    }
  };

  const inviteMember: AppContextValue["inviteMember"] = async (payload) => {
    setLastActionError(null);
    try {
      await apiClient.inviteMember({
        full_name: payload.fullName,
        email: payload.email,
        password: payload.password,
        role: payload.role,
      });
      await refreshWorkspaceData();
      return { ok: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to invite member";
      setLastActionError(msg);
      return { ok: false, error: msg };
    }
  };

  const updateMemberRole: AppContextValue["updateMemberRole"] = async (memberId, role, isActive) => {
    setLastActionError(null);
    try {
      await apiClient.updateMemberRole(memberId, { role, is_active: isActive });
      await refreshWorkspaceData();
      return true;
    } catch (err) {
      setLastActionError(err instanceof Error ? err.message : "Failed to update member role");
      return false;
    }
  };

  return (
    <AppContext.Provider
      value={{
        session,
        authToken,
        apiBaseUrl,
        backendStatus,
        loadingWorkspace,
        lastActionError,
        clearLastActionError: () => setLastActionError(null),
        setLastActionError,
        workspace,
        candidates,
        interviews,
        onboardingWorkflows,
        approvals,
        knowledgeDocs,
        integrations,
        executions,
        usageStats,
        conversations,
        organizationMembers,
        auditLogs,
        monitorSnapshot,
        runtimesInfo,
        structuredTools,
        mcpData,
        refreshRuntimeData,
        loginLive,
        registerBusinessLive,
        signOut,
        setApiBaseUrl,
        refreshWorkspaceData,
        executeWorkflow,
        createConversation,
        sendConversationTurn,
        uploadKnowledgeDoc,
        deleteKnowledgeDoc,
        toggleIntegrationPermission,
        bindIntegrationCredential,
        updateWorkspaceSettings,
        resolveHitlApproval,
        inviteMember,
        updateMemberRole,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
