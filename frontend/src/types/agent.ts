export type UserRole =
  | "platform_admin"
  | "business_owner"
  | "business_admin"
  | "business_employee";

export type HrWorkflowSlug =
  | "recruitment-screening"
  | "jd-generator"
  | "candidate-shortlisting"
  | "interview-scheduling"
  | "employee-onboarding"
  | "hr-policy-support"
  | "hr-analytics";

export interface HrWorkflowMeta {
  slug: HrWorkflowSlug;
  name: string;
  shortLabel: string;
  description: string;
  routePath: string;
  requiresAdmin: boolean;
  samplePrompts: string[];
}

export interface TenantSession {
  tenantId: string;
  tenantName: string;
  tenantSlug: string;
  userEmail: string;
  userName: string;
  role: UserRole;
  isSignedIn: boolean;
  isLiveAuthenticated: boolean;
}

export interface WorkspaceWorkflowStatus {
  slug: string;
  name: string;
  description: string;
  rental_id: string | null;
  status: string;
  allowed_for_current_role: boolean;
  blind_screening_mode: boolean;
  strict_pii_masking: boolean;
  require_hitl_approval: boolean;
  model_routing_tier: string;
  monthly_token_quota: number;
}

export interface WorkspaceQuota {
  monthly_token_limit: number;
  tokens_used_this_month: number;
  remaining_tokens: number;
  usage_percent: number;
}

export interface WorkspaceMetrics {
  total_executions: number;
  completed_executions: number;
  failed_executions: number;
  rejected_executions: number;
  blocked_executions: number;
  pending_hitl_count: number;
  total_jobs_count: number;
  candidate_count: number;
  resumes_analyzed_count: number;
  interview_count: number;
  scheduled_interviews_count: number;
  onboarding_count: number;
  pending_onboarding_count: number;
  kb_document_count: number;
  estimated_ai_cost_usd: number;
}

export interface WorkspaceSettings {
  blind_screening_mode: boolean;
  strict_pii_masking: boolean;
  require_hitl_approval: boolean;
  model_routing_tier: "tier_0_rule" | "tier_1_fast" | "tier_2_reasoning" | "auto_cascade";
  monthly_token_quota: number;
  custom_persona_prompt: string;
}

export interface UnifiedWorkspaceData {
  product_name: string;
  tenant_id: string;
  organization_name: string;
  organization_slug: string;
  role: UserRole;
  workflows: WorkspaceWorkflowStatus[];
  metrics: WorkspaceMetrics;
  quota: WorkspaceQuota;
  settings: WorkspaceSettings;
}

export interface TraceStep {
  step: string;
  status: string;
  duration_ms: number;
  detail: string;
}

export interface AnalyticsChartSpec {
  chart_id?: string;
  title: string;
  chart_type?: string;
  x_label?: string;
  y_label?: string;
  data: { label: string; value: number }[];
}

export interface HitlRequestItem {
  approval_id?: string;
  action_type: string;
  title: string;
  summary?: string;
  status?: string;
  payload?: Record<string, unknown>;
}

export interface UnifiedExecuteResponse {
  execution_status: string;
  classifier_result: string;
  routed_workflow: string;
  routed_workflow_name: string;
  requested_workflow: string;
  agent_version: string;
  execution_log_id: string | null;
  final_response_text: string;
  structured_output: Record<string, unknown>;
  citations: string[];
  charts: AnalyticsChartSpec[];
  hitl_requests: HitlRequestItem[];
  trace_steps: TraceStep[];
  llm_provider_used: string;
  model_used: string;
  baseline_input_tokens?: number;
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  tokens_saved?: number;
  reduction_percent?: number;
  optimization_enabled?: boolean;
  optimization_methods_used?: string[];
  guardrail_flags?: string[];
  intent_analysis?: {
    intent_label?: string;
    user_intent?: string;
    requested_task?: string;
    hr_workflow?: string;
    required_tools?: string[];
    risk_level?: string;
    required_permissions?: string[];
    needs_clarification?: boolean;
    clarification_questions?: string[];
    classifier_method?: string;
  };
  clarification_questions?: string[];
  latency_ms: number;
  rejection_reason: string | null;
}

export interface CandidateRecord {
  id: string;
  full_name: string;
  target_role: string;
  years_experience: number;
  skills: string[];
  match_score: number | null;
  status: string;
}

export interface InterviewRecordItem {
  id: string;
  candidate_name: string;
  role_title: string;
  interview_stage: string;
  interviewer_emails: string[];
  scheduled_start: string;
  duration_minutes: number;
  status: string;
  meeting_link: string;
}

export interface OnboardingRecordItem {
  id: string;
  employee_name: string;
  role_title: string;
  department: string;
  current_stage: string;
  progress_percent: number;
  documents_status: Record<string, string>;
  checklist: { stage: string; label?: string; title?: string; completed?: boolean; status?: string }[];
  it_provisioning: Record<string, unknown>;
  team_allocation: Record<string, unknown>;
  training_plan: { title?: string; module?: string; week?: string; owner?: string; completed?: boolean }[];
}

export interface HitlApprovalRecord {
  id: string;
  rental_id: string;
  conversation_id: string | null;
  agent_slug: string;
  action_type: string;
  title: string;
  summary: string;
  payload_json: Record<string, unknown>;
  status: "pending" | "approved" | "rejected";
  resolution_note: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface UnifiedKnowledgeDoc {
  id: string;
  rental_id: string;
  workflow_slug: string;
  workflow_name: string;
  title: string;
  original_filename: string;
  source_type: string;
  mime_type: string;
  file_size_bytes: number;
  sha256_checksum: string;
  chunk_count: number;
  min_role_access: UserRole;
  status: string;
  created_at: string;
}

export interface UnifiedIntegrationItem {
  id: string;
  rental_id: string;
  workflow_slug: string;
  workflow_name: string;
  tool_id: string;
  tool_slug: string;
  tool_name: string;
  category: string;
  mcp_server_slug: string | null;
  execution_mode: string;
  requires_hitl: boolean;
  auth_scheme: string;
  description: string;
  is_allowed: boolean;
  credential_status: string;
  masked_secret_ref: string;
}

export interface ExecutionToolCallTelemetry {
  tool: string;
  status: string;
  duration_ms: number;
  risk_level?: string;
  error?: string | null;
}

export interface ExecutionBrowserActivity {
  status: "not_used" | "completed" | "blocked" | "error" | string;
  agent_slug?: string;
  tools?: string[];
  visited_urls?: string[];
  blocked_requests?: Array<{ url: string; reason: string }>;
  screenshots?: string[];
}

export interface ExecutionSandboxStatus {
  status: string;
  runtime_id?: string;
  agent_runtime_id?: string;
  backend_mode: "docker" | "development_fallback" | "none" | string;
  is_container_isolated: boolean;
  last_task?: string;
  duration_ms?: number;
}

export interface ExecutionTokenUsage {
  input_tokens: number;
  cached_tokens?: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface UnifiedExecutionRecord {
  id: string;
  rental_id: string;
  workflow_slug: string;
  workflow_name: string;
  prompt_preview: string;
  classifier_result: string;
  status: string;
  latency_ms: number;
  model_tier_used: string;
  steps_json: TraceStep[];
  citations_json: string[];
  tools: string[];
  tool_calls?: ExecutionToolCallTelemetry[];
  browser_activity?: ExecutionBrowserActivity;
  sandbox_status?: ExecutionSandboxStatus;
  token_usage?: ExecutionTokenUsage;
  created_at: string;
}

export interface SandboxRuntimeItem {
  id: string;
  tenant_id: string;
  agent_runtime_id: string;
  rental_id: string | null;
  backend_mode: "docker" | "development_fallback" | string;
  is_container_isolated: boolean;
  status: "created" | "running" | "stopped" | "destroyed" | "error" | string;
  container_id: string | null;
  image_name: string;
  cpu_limit: number;
  memory_limit_mb: number;
  timeout_seconds: number;
  network_mode: string;
  last_health: Record<string, unknown>;
  execution_logs: Array<{
    timestamp: string;
    event: string;
    status: string;
    duration_ms: number;
    detail: string;
  }>;
  last_started_at: string | null;
  last_stopped_at: string | null;
  destroyed_at: string | null;
  created_at: string | null;
}

export interface RuntimesListPayload {
  docker_available: boolean;
  isolation_notice: string;
  runtimes: SandboxRuntimeItem[];
}

export interface StructuredHrToolSpec {
  tool_id: string;
  name: string;
  description: string;
  category: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  required_roles: string[];
  requires_hitl: boolean;
  risk_level: "low" | "medium" | "high" | string;
  timeout_seconds: number;
}

export interface McpToolPermissionConfig {
  allowed: boolean;
  requires_hitl: boolean;
  allowed_roles: string[];
  timeout_seconds: number;
}

export interface McpServerItem {
  id: string;
  tenant_id: string;
  slug: string;
  name: string;
  description: string;
  transport: "stdio" | "sse" | string;
  command_or_url: string;
  args: string[];
  env_keys: string[];
  is_approved: boolean;
  approval_status: "pending_approval" | "approved" | "blocked" | string;
  approved_at: string | null;
  connection_status: "not_checked" | "connected" | "unreachable" | "pending_approval" | "blocked" | string;
  last_error: string | null;
  discovered_tools: Array<{
    name: string;
    description: string;
    inputSchema: Record<string, unknown>;
  }>;
  tool_permissions: Record<string, McpToolPermissionConfig>;
  last_checked_at: string | null;
  created_at: string | null;
}

export interface McpExecutionLogItem {
  id: string;
  server_id: string;
  tool_name: string;
  status: string;
  duration_ms: number;
  error_message: string | null;
  request_summary: Record<string, unknown>;
  response_summary: Record<string, unknown>;
  created_at: string | null;
}

export interface McpServersPayload {
  servers: McpServerItem[];
  execution_logs: McpExecutionLogItem[];
}

export interface ExecutionMonitorSnapshot {
  active_runs: Array<{
    run_id: string;
    current_task: string;
    current_workflow: string;
    status: string;
    started_at: string;
    tool_calls: ExecutionToolCallTelemetry[];
    browser_activity: ExecutionBrowserActivity;
    sandbox_status: Record<string, unknown>;
  }>;
  current_task: string | null;
  current_workflow: string | null;
  executions: Array<{
    id: string;
    current_task: string;
    current_workflow: string;
    status: string;
    execution_duration_ms: number;
    model_tier_used: string;
    tool_calls: ExecutionToolCallTelemetry[];
    browser_activity: ExecutionBrowserActivity;
    sandbox_status: ExecutionSandboxStatus;
    token_usage: ExecutionTokenUsage;
    steps: TraceStep[];
    created_at: string | null;
  }>;
  sandbox_runtimes: Array<{
    id: string;
    agent_runtime_id: string;
    status: string;
    backend_mode: string;
    is_container_isolated: boolean;
    network_mode: string;
    cpu_limit: number;
    memory_limit_mb: number;
    timeout_seconds: number;
    last_health: Record<string, unknown>;
    recent_logs: Array<Record<string, unknown>>;
  }>;
  token_summary: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
  };
  mcp_summary: {
    total_servers: number;
    connected_approved_servers: number;
    recent_calls: Array<{
      id: string;
      server_id: string;
      tool_name: string;
      status: string;
      duration_ms: number;
      error_message: string | null;
      created_at: string | null;
    }>;
  };
}

export interface UnifiedUsageBreakdown {
  monthly_token_limit: number;
  tokens_used_this_month: number;
  remaining_tokens: number;
  optimization_summary?: {
    total_runs_measured: number;
    optimized_runs: number;
    unoptimized_runs: number;
    total_baseline_input_tokens: number;
    total_actual_input_tokens: number;
    total_cached_tokens: number;
    total_output_tokens: number;
    total_measured_tokens_saved: number;
    measured_reduction_percent: number;
    total_estimated_cost_usd: number;
    avg_optimized_input_tokens: number | null;
    avg_unoptimized_input_tokens: number | null;
    methods_frequency: Record<string, number>;
  };
  by_workflow: {
    workflow_slug: string;
    workflow_name: string;
    baseline_input_tokens?: number;
    input_tokens: number;
    cached_tokens: number;
    output_tokens: number;
    total_tokens: number;
    tokens_saved?: number;
    tool_calls_count?: number;
    avg_duration_ms?: number;
    estimated_cost_usd: number;
    runs: number;
  }[];
  recent_entries: {
    id: string;
    workflow_slug: string;
    workflow_name: string;
    model_id: string;
    baseline_input_tokens?: number;
    input_tokens: number;
    cached_tokens: number;
    output_tokens: number;
    duration_ms?: number;
    tool_calls_count?: number;
    optimization_enabled?: boolean;
    optimization_methods?: string[];
    estimated_cost_usd: string;
    created_at: string;
  }[];
}

export interface OptimizationComparisonResult {
  workflow_slug: string;
  workflow_name: string;
  unoptimized: {
    execution_status: string;
    model_used: string;
    input_tokens: number;
    cached_tokens: number;
    output_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
    latency_ms: number;
  };
  optimized: {
    execution_status: string;
    model_used: string;
    baseline_input_tokens: number;
    input_tokens: number;
    cached_tokens: number;
    output_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
    latency_ms: number;
    methods_used: string[];
  };
  measured_diff: {
    input_tokens_saved: number;
    total_tokens_saved: number;
    input_reduction_percent: number;
    cost_saved_usd: number;
    latency_diff_ms: number;
  };
}

export interface KnowledgeGraphPayload {
  tenant_id: string;
  pii_included: boolean;
  summary: {
    total_nodes: number;
    total_edges: number;
    documents: number;
    candidates: number;
    interviews: number;
  };
  nodes: Array<{ id: string; type: string; label: string; [key: string]: unknown }>;
  edges: Array<{ source: string; target: string; relation: string }>;
}

export interface ObsidianMarkdownExport {
  document_id: string;
  title: string;
  filename: string;
  markdown: string;
  tags: string[];
  wikilinks: string[];
}

export interface OrganizationMemberItem {
  memberId: string;
  userId: string;
  email: string;
  fullName: string;
  role: UserRole;
  isActive: boolean;
  createdAt: string;
}

export interface AuditLogItem {
  id: number;
  tenantId: string;
  actorUserId: string | null;
  rentalId: string | null;
  action: string;
  resourceType: string;
  resourceId: string;
  status: string;
  ipAddress: string | null;
  metadataJson: Record<string, unknown>;
  createdAt: string;
}

export interface UnifiedConversationSummary {
  id: string;
  tenant_id: string;
  rental_id: string;
  user_id: string | null;
  title: string;
  status: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface UnifiedConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system_guardrail";
  content: string;
  classifier_result: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface UnifiedMessageTurnResult {
  conversation_id: string;
  user_message: UnifiedConversationMessage;
  assistant_message: UnifiedConversationMessage;
  workflow_slug: string;
  workflow_name: string;
  execution_status: string;
  classifier_result: string;
  citations: string[];
  charts: AnalyticsChartSpec[];
  hitl_requests: HitlRequestItem[];
  trace_steps: TraceStep[];
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  latency_ms: number;
}
