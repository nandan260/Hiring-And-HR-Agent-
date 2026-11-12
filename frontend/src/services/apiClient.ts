import type {
  AnalyticsChartSpec,
  CandidateRecord,
  ExecutionMonitorSnapshot,
  HitlApprovalRecord,
  InterviewRecordItem,
  KnowledgeGraphPayload,
  McpServerItem,
  McpServersPayload,
  ObsidianMarkdownExport,
  OnboardingRecordItem,
  OptimizationComparisonResult,
  RuntimesListPayload,
  SandboxRuntimeItem,
  StructuredHrToolSpec,
  TraceStep,
  UnifiedConversationMessage,
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

export interface ApiClientConfig {
  baseUrl: string;
  liveModeEnabled: boolean;
  authToken?: string;
}

export interface BackendAuthenticatedUser {
  user_id: string;
  email: string;
  full_name: string;
  tenant_id: string;
  organization_name: string;
  organization_slug: string;
  role: UserRole;
  is_platform_admin: boolean;
}

export interface BackendTokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: BackendAuthenticatedUser;
}

export interface BackendOrgMemberDto {
  member_id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface BackendAuditLogDto {
  id: number;
  tenant_id: string;
  actor_user_id: string | null;
  rental_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  status: string;
  ip_address: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export type {
  AnalyticsChartSpec,
  CandidateRecord,
  HitlApprovalRecord,
  InterviewRecordItem,
  OnboardingRecordItem,
  TraceStep,
  UnifiedConversationMessage,
  UnifiedConversationSummary,
  UnifiedExecuteResponse,
  UnifiedExecutionRecord,
  UnifiedIntegrationItem,
  UnifiedKnowledgeDoc,
  UnifiedMessageTurnResult,
  UnifiedUsageBreakdown,
  UnifiedWorkspaceData,
};

const DEFAULT_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.toString() || "http://localhost:8000/api/v1";

export class HireFlowApiClient {
  private config: ApiClientConfig;

  constructor(config?: Partial<ApiClientConfig>) {
    this.config = {
      baseUrl: config?.baseUrl || DEFAULT_BASE_URL,
      liveModeEnabled:
        config?.liveModeEnabled ?? import.meta.env.VITE_ENABLE_LIVE_API !== "false",
      authToken: config?.authToken,
    };
  }

  public setConfig(next: Partial<ApiClientConfig>) {
    this.config = { ...this.config, ...next };
  }

  public getConfig(): ApiClientConfig {
    return this.config;
  }

  private async request<T>(path: string, init?: RequestInit & { isMultipart?: boolean }): Promise<T> {
    const headers: Record<string, string> = {
      ...(init?.isMultipart ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers as Record<string, string> | undefined),
    };
    if (this.config.authToken) {
      headers.Authorization = `Bearer ${this.config.authToken}`;
    }

    const res = await fetch(`${this.config.baseUrl}${path}`, {
      ...init,
      headers,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body?.detail ? String(body.detail) : JSON.stringify(body);
      } catch {
        detail = (await res.text()) || res.statusText;
      }
      throw new Error(`API ${res.status}: ${detail}`);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  }

  public async checkBackendHealth(): Promise<{ online: boolean; detail: string }> {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3000);
      const res = await fetch(`${this.config.baseUrl.replace(/\/api\/v1$/, "")}/health`, {
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (res.ok) {
        const payload = await res.json().catch(() => ({}));
        const pg = payload?.postgres_version ? ` (${payload.postgres_version})` : "";
        return { online: true, detail: `Connected to HireFlow AI FastAPI Backend${pg}` };
      }
      return { online: false, detail: `HTTP ${res.status}` };
    } catch {
      return {
        online: false,
        detail: "FastAPI backend unreachable at " + this.config.baseUrl,
      };
    }
  }

  // Auth
  public registerBusiness(payload: {
    full_name: string;
    email: string;
    password: string;
    organization_name: string;
    industry: string;
  }): Promise<BackendTokenResponse> {
    return this.request<BackendTokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public login(payload: {
    email: string;
    password: string;
    organization_slug?: string;
  }): Promise<BackendTokenResponse> {
    return this.request<BackendTokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public logout(): Promise<{ status: string; revoked_jti: string }> {
    return this.request<{ status: string; revoked_jti: string }>("/auth/logout", {
      method: "POST",
    });
  }

  public getMe(): Promise<BackendAuthenticatedUser> {
    return this.request<BackendAuthenticatedUser>("/auth/me");
  }

  // Unified HireFlow AI Hiring & HR Agent API
  public getHrWorkspace(): Promise<UnifiedWorkspaceData> {
    return this.request<UnifiedWorkspaceData>("/hr-agent/workspace");
  }

  public executeHrAgent(payload: {
    prompt: string;
    workflow_hint?: string;
    conversation_id?: string;
    structured_input?: Record<string, unknown>;
    attachments?: string[];
    model_provider_override?: string;
    enable_optimization?: boolean;
  }): Promise<UnifiedExecuteResponse> {
    return this.request<UnifiedExecuteResponse>("/hr-agent/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public compareOptimization(payload: {
    prompt: string;
    workflow_hint?: string;
    structured_input?: Record<string, unknown>;
    record_telemetry?: boolean;
  }): Promise<OptimizationComparisonResult> {
    return this.request<OptimizationComparisonResult>("/hr-agent/optimization/compare", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public getKnowledgeMarkdown(docId: string): Promise<ObsidianMarkdownExport> {
    return this.request<ObsidianMarkdownExport>(`/hr-agent/knowledge/${docId}/markdown`);
  }

  public getKnowledgeGraph(): Promise<KnowledgeGraphPayload> {
    return this.request<KnowledgeGraphPayload>("/hr-agent/knowledge-graph");
  }

  public listHrConversations(): Promise<UnifiedConversationSummary[]> {
    return this.request<UnifiedConversationSummary[]>("/hr-agent/conversations");
  }

  public createHrConversation(title: string): Promise<UnifiedConversationSummary> {
    return this.request<UnifiedConversationSummary>("/hr-agent/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  public listHrConversationMessages(conversationId: string): Promise<UnifiedConversationMessage[]> {
    return this.request<UnifiedConversationMessage[]>(
      `/hr-agent/conversations/${conversationId}/messages`
    );
  }

  public postHrConversationMessage(
    conversationId: string,
    payload: {
      content: string;
      workflow_hint?: string;
      structured_input?: Record<string, unknown>;
      attachments?: string[];
    }
  ): Promise<UnifiedMessageTurnResult> {
    return this.request<UnifiedMessageTurnResult>(
      `/hr-agent/conversations/${conversationId}/messages`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  }

  public listHrKnowledge(): Promise<UnifiedKnowledgeDoc[]> {
    return this.request<UnifiedKnowledgeDoc[]>("/hr-agent/knowledge");
  }

  public uploadHrKnowledge(formData: FormData): Promise<UnifiedKnowledgeDoc> {
    return this.request<UnifiedKnowledgeDoc>("/hr-agent/knowledge", {
      method: "POST",
      body: formData,
      isMultipart: true,
    });
  }

  public async downloadHrKnowledge(docId: string, fallbackFilename: string): Promise<void> {
    const headers: Record<string, string> = {};
    if (this.config.authToken) {
      headers.Authorization = `Bearer ${this.config.authToken}`;
    }
    const res = await fetch(`${this.config.baseUrl}/hr-agent/knowledge/${docId}/download`, {
      headers,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body?.detail ? String(body.detail) : detail;
      } catch {
        // ignore
      }
      throw new Error(`API ${res.status}: ${detail}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fallbackFilename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  public deleteHrKnowledge(docId: string): Promise<void> {
    return this.request<void>(`/hr-agent/knowledge/${docId}`, { method: "DELETE" });
  }

  public listHrIntegrations(): Promise<UnifiedIntegrationItem[]> {
    return this.request<UnifiedIntegrationItem[]>("/hr-agent/integrations");
  }

  public toggleHrIntegration(
    permissionId: string,
    isAllowed: boolean,
    applyToAllWorkflows = true
  ): Promise<{ id: string; tool_slug: string; is_allowed: boolean }> {
    return this.request(`/hr-agent/integrations/${permissionId}`, {
      method: "PATCH",
      body: JSON.stringify({
        is_allowed: isAllowed,
        apply_to_all_workflows: applyToAllWorkflows,
      }),
    });
  }

  public bindHrIntegrationCredential(
    permissionId: string,
    apiKeyOrToken: string,
    applyToAllWorkflows = true
  ): Promise<{
    id: string;
    tool_slug: string;
    is_allowed: boolean;
    credential_status: string;
    masked_secret_ref: string;
  }> {
    return this.request(`/hr-agent/integrations/${permissionId}/credentials`, {
      method: "POST",
      body: JSON.stringify({
        api_key_or_token: apiKeyOrToken,
        apply_to_all_workflows: applyToAllWorkflows,
      }),
    });
  }

  public updateHrSettings(payload: {
    blind_screening_mode?: boolean;
    strict_pii_masking?: boolean;
    require_hitl_approval?: boolean;
    model_routing_tier?: "tier_0_rule" | "tier_1_fast" | "tier_2_reasoning" | "auto_cascade";
    monthly_token_quota?: number;
    custom_persona_prompt?: string;
  }): Promise<Record<string, unknown>> {
    return this.request("/hr-agent/settings", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  public listHrExecutions(workflowSlug?: string, statusFilter?: string): Promise<UnifiedExecutionRecord[]> {
    const params = new URLSearchParams();
    if (workflowSlug) params.set("workflow_slug", workflowSlug);
    if (statusFilter) params.set("status", statusFilter);
    const qs = params.toString();
    return this.request<UnifiedExecutionRecord[]>(`/hr-agent/executions${qs ? `?${qs}` : ""}`);
  }

  public getHrUsage(): Promise<UnifiedUsageBreakdown> {
    return this.request<UnifiedUsageBreakdown>("/hr-agent/usage");
  }

  // Runtime Infrastructure, Tool Registry, Browser & MCP Client Manager
  public getMonitorSnapshot(limit = 25): Promise<ExecutionMonitorSnapshot> {
    return this.request<ExecutionMonitorSnapshot>(`/hr-agent/monitor?limit=${limit}`);
  }

  public listRuntimes(): Promise<RuntimesListPayload> {
    return this.request<RuntimesListPayload>("/hr-agent/runtimes");
  }

  public createRuntime(payload?: {
    cpu_limit?: number;
    memory_limit_mb?: number;
    timeout_seconds?: number;
    auto_start?: boolean;
  }): Promise<SandboxRuntimeItem> {
    return this.request<SandboxRuntimeItem>("/hr-agent/runtimes", {
      method: "POST",
      body: JSON.stringify(payload || { auto_start: true }),
    });
  }

  public performRuntimeAction(
    runtimeId: string,
    action: "start" | "stop" | "restart"
  ): Promise<SandboxRuntimeItem> {
    return this.request<SandboxRuntimeItem>(`/hr-agent/runtimes/${runtimeId}/${action}`, {
      method: "POST",
    });
  }

  public destroyRuntime(runtimeId: string): Promise<SandboxRuntimeItem> {
    return this.request<SandboxRuntimeItem>(`/hr-agent/runtimes/${runtimeId}`, {
      method: "DELETE",
    });
  }

  public listStructuredTools(coreOnly = false): Promise<StructuredHrToolSpec[]> {
    return this.request<StructuredHrToolSpec[]>(`/hr-agent/tools?core_only=${coreOnly}`);
  }

  public executeRegisteredTool(toolId: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/hr-agent/tools/${encodeURIComponent(toolId)}/execute`, {
      method: "POST",
      body: JSON.stringify(args),
    });
  }

  public listMcpServers(): Promise<McpServersPayload> {
    return this.request<McpServersPayload>("/hr-agent/mcp/servers");
  }

  public registerMcpServer(payload: {
    slug: string;
    name: string;
    transport: "stdio" | "sse";
    command_or_url: string;
    args?: string[];
    env_keys?: string[];
    description?: string;
  }): Promise<McpServerItem> {
    return this.request<McpServerItem>("/hr-agent/mcp/servers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public setMcpApproval(serverId: string, approved: boolean): Promise<McpServerItem> {
    return this.request<McpServerItem>(`/hr-agent/mcp/servers/${serverId}/approval`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    });
  }

  public discoverMcpTools(serverId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/hr-agent/mcp/servers/${serverId}/discover`, {
      method: "POST",
    });
  }

  public updateMcpToolPermission(
    serverId: string,
    payload: { tool_name: string; allowed: boolean; requires_hitl?: boolean }
  ): Promise<McpServerItem> {
    return this.request<McpServerItem>(`/hr-agent/mcp/servers/${serverId}/permissions`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  // Domain Records & Governance
  public listCandidates(): Promise<CandidateRecord[]> {
    return this.request<CandidateRecord[]>("/candidates");
  }

  public listInterviews(): Promise<InterviewRecordItem[]> {
    return this.request<InterviewRecordItem[]>("/interviews");
  }

  public listOnboarding(): Promise<OnboardingRecordItem[]> {
    return this.request<OnboardingRecordItem[]>("/onboarding");
  }

  public listHitlApprovals(statusFilter?: string): Promise<HitlApprovalRecord[]> {
    const q = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
    return this.request<HitlApprovalRecord[]>(`/hitl/approvals${q}`);
  }

  public resolveHitlApproval(
    approvalId: string,
    decision: "approved" | "rejected",
    resolutionNote?: string
  ): Promise<HitlApprovalRecord> {
    return this.request<HitlApprovalRecord>(`/hitl/approvals/${approvalId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ decision, resolution_note: resolutionNote || null }),
    });
  }

  public listOrganizationMembers(): Promise<BackendOrgMemberDto[]> {
    return this.request<BackendOrgMemberDto[]>("/organizations/members");
  }

  public inviteMember(payload: {
    full_name: string;
    email: string;
    password: string;
    role: "business_owner" | "business_admin" | "business_employee";
  }): Promise<BackendOrgMemberDto> {
    return this.request<BackendOrgMemberDto>("/organizations/members", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public updateMemberRole(
    memberId: string,
    payload: { role: "business_owner" | "business_admin" | "business_employee"; is_active: boolean }
  ): Promise<BackendOrgMemberDto> {
    return this.request<BackendOrgMemberDto>(`/organizations/members/${memberId}/role`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  public listAuditLogs(): Promise<BackendAuditLogDto[]> {
    return this.request<BackendAuditLogDto[]>("/audit-logs");
  }
}

export const apiClient = new HireFlowApiClient();
