import { z } from "zod";
import { jsonValueSchema, type JsonValue } from "./json";

/**
 * Zod mirrors of `vulnclaw/web/schemas.py`. Every backend response is decoded
 * through these schemas at the I/O boundary, so the rest of the UI works with
 * domain values rather than unparsed payloads. Backend `Optional[...]` fields
 * serialise as `null` when unset, so they are decoded with `.nullish()`.
 */

const optionalString = z.string().nullish();
const optionalNumber = z.number().nullish();

export const taskCommandSchema = z.enum(["run", "recon", "scan", "exploit", "persistent"]);
export type TaskCommand = z.infer<typeof taskCommandSchema>;

export const taskStatusSchema = z.enum([
  "pending",
  "restoring",
  "running",
  "completed",
  "failed",
  "stopped",
]);
export type TaskStatus = z.infer<typeof taskStatusSchema>;

export const reportLanguageSchema = z.enum(["auto", "zh", "en"]);
export type ReportLanguage = z.infer<typeof reportLanguageSchema>;

export const reportFormatSchema = z.enum(["markdown", "html"]);
export type ReportFormat = z.infer<typeof reportFormatSchema>;

/**
 * Mirrors `vulnclaw.config.domain_models.TaskConstraints`. The `only_*` /
 * `*_actions` aliases are the flat scope keys written by older target-state
 * files, which the UI still falls back to when the structured keys are absent.
 */
export const taskConstraintsSchema = z.object({
  allowed_ports: z.array(z.number()).optional(),
  blocked_ports: z.array(z.number()).optional(),
  allowed_hosts: z.array(z.string()).optional(),
  blocked_hosts: z.array(z.string()).optional(),
  allowed_paths: z.array(z.string()).optional(),
  blocked_paths: z.array(z.string()).optional(),
  allowed_actions: z.array(z.string()).optional(),
  blocked_actions: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
  strict_mode: z.boolean().optional(),
  only_host: optionalString,
  only_path: optionalString,
  only_port: z.union([z.string(), z.number()]).nullish(),
  blocked_host: optionalString,
  blocked_path: optionalString,
  allow_actions: z.array(z.string()).optional(),
  block_actions: z.array(z.string()).optional(),
});
export type TaskConstraints = z.infer<typeof taskConstraintsSchema>;

/** Mirrors `vulnclaw.config.domain_models.ConstraintViolationEvent`. */
export const constraintViolationEventSchema = z.object({
  timestamp: z.string().default(""),
  kind: z.string().default("constraint_violation"),
  code: z.string().default(""),
  severity: z.string().default(""),
  source: z.string().default(""),
  action: z.string().default(""),
  tool_name: z.string().default(""),
  phase: z.string().default(""),
  summary: z.string().default(""),
  detail: z.string().default(""),
});
export type ConstraintViolationEvent = z.infer<typeof constraintViolationEventSchema>;

export const configViewSchema = z.object({
  provider: z.string(),
  model: z.string(),
  base_url: z.string(),
  api_key_configured: z.boolean(),
  language: reportLanguageSchema,
  output_dir: z.string(),
  max_rounds: z.number(),
  max_context_tokens: z.number(),
  context_auto_compact: z.boolean(),
  context_compact_trigger_ratio: z.number(),
  context_compact_target_ratio: z.number(),
  context_recent_message_groups: z.number(),
  context_summary_max_tokens: z.number(),
  context_output_reserve_tokens: z.number(),
  context_compaction_mode: z.literal("structured"),
  context_compaction_audit_enabled: z.boolean(),
  persistent_rounds_per_cycle: z.number(),
  persistent_max_cycles: z.number(),
  show_thinking: z.boolean(),
  python_execute_enabled: z.boolean(),
  python_execute_mode: z.string(),
  python_execute_max_lines: z.number(),
  python_execute_audit_enabled: z.boolean(),
});
export type ConfigView = z.infer<typeof configViewSchema>;

export interface ConfigUpdateRequest {
  provider?: string;
  model?: string;
  base_url?: string;
  language?: ReportLanguage;
  output_dir?: string;
  max_rounds?: number;
  max_context_tokens?: number;
  context_auto_compact?: boolean;
  context_compact_trigger_ratio?: number;
  context_compact_target_ratio?: number;
  context_recent_message_groups?: number;
  context_summary_max_tokens?: number;
  context_output_reserve_tokens?: number;
  context_compaction_mode?: "structured";
  context_compaction_audit_enabled?: boolean;
  persistent_rounds_per_cycle?: number;
  persistent_max_cycles?: number;
  show_thinking?: boolean;
  python_execute_enabled?: boolean;
  python_execute_mode?: string;
  python_execute_max_lines?: number;
  python_execute_audit_enabled?: boolean;
}

export const providerPresetViewSchema = z.object({
  id: z.string(),
  label: z.string(),
  base_url: z.string(),
  default_model: z.string(),
});
export type ProviderPresetView = z.infer<typeof providerPresetViewSchema>;

export const providersViewSchema = z.object({
  providers: z.array(providerPresetViewSchema).default([]),
});
export type ProvidersView = z.infer<typeof providersViewSchema>;

export interface ProviderModelsRequest {
  provider?: string;
  base_url?: string;
}

export const providerModelsResponseSchema = z.object({
  base_url: z.string(),
  models: z.array(z.string()).default([]),
  has_api_key: z.boolean().default(false),
  detail: z.string().default(""),
});
export type ProviderModelsResponse = z.infer<typeof providerModelsResponseSchema>;

/**
 * `TargetView.raw` is the persisted target-state document. Only `findings` is
 * read structurally by the UI; the remainder is rendered as formatted JSON.
 */
export const findingRecordSchema = z
  .object({
    id: optionalString,
    title: optionalString,
    name: optionalString,
    summary: optionalString,
    description: optionalString,
    detail: optionalString,
    severity: optionalString,
    risk: optionalString,
    status: optionalString,
    lifecycle_status: optionalString,
    target: optionalString,
    url: optionalString,
    vuln_type: optionalString,
    category: optionalString,
    evidence_level: optionalString,
    verification_note: optionalString,
  })
  .catchall(jsonValueSchema);
export type FindingRecord = z.infer<typeof findingRecordSchema>;

export const targetRawStateSchema = z
  .object({
    findings: z.array(findingRecordSchema).optional(),
  })
  .catchall(jsonValueSchema);
export type TargetRawState = z.infer<typeof targetRawStateSchema>;

export const targetViewSchema = z.object({
  target: z.string(),
  schema_version: z.number().default(1),
  phase: optionalString,
  findings_count: z.number().default(0),
  verified_count: z.number().default(0),
  pending_count: z.number().default(0),
  candidate_count: z.number().default(0),
  pending_verification_count: z.number().default(0),
  manual_review_count: z.number().default(0),
  resume_strategy: z.string().default(""),
  resume_reason: z.string().default(""),
  constraints: taskConstraintsSchema.default({}),
  constraint_violations: z.array(z.string()).default([]),
  constraint_violation_events: z.array(constraintViolationEventSchema).default([]),
  raw: targetRawStateSchema.default({}),
});
export type TargetView = z.infer<typeof targetViewSchema>;

export const targetSnapshotViewSchema = z.object({
  snapshot_id: z.string(),
  schema_version: z.number().default(1),
  last_saved_at: z.string().default(""),
  last_command: z.string().default(""),
  verified_findings: z.number().default(0),
  pending_findings: z.number().default(0),
  executed_steps: z.number().default(0),
  resume_strategy: z.string().default(""),
});
export type TargetSnapshotView = z.infer<typeof targetSnapshotViewSchema>;

export const targetPreviewViewSchema = z.object({
  target: z.string(),
  schema_version: z.number().default(1),
  phase: optionalString,
  snapshot_id: z.string().default(""),
  last_command: z.string().default(""),
  resume_strategy: z.string().default(""),
  resume_reason: z.string().default(""),
  findings_count: z.number().default(0),
  verified_count: z.number().default(0),
  pending_count: z.number().default(0),
  candidate_count: z.number().default(0),
  pending_verification_count: z.number().default(0),
  manual_review_count: z.number().default(0),
  priority_targets: z.array(z.string()).default([]),
  priority_recon_assets: z.array(z.string()).default([]),
  blocked_targets: z.array(z.string()).default([]),
  failed_targets: z.array(z.string()).default([]),
  recent_failed_steps: z.array(z.string()).default([]),
  next_actions: z.array(z.string()).default([]),
  low_value_rounds: z.number().default(0),
  constraints: taskConstraintsSchema.default({}),
  constraint_violations: z.array(z.string()).default([]),
  constraint_violation_events: z.array(constraintViolationEventSchema).default([]),
});
export type TargetPreviewView = z.infer<typeof targetPreviewViewSchema>;

export const targetStateDiffViewSchema = z.object({
  target: z.string(),
  schema_version_from: z.number().default(1),
  schema_version_to: z.number().default(1),
  from_snapshot_id: z.string(),
  to_snapshot_id: z.string(),
  resume_strategy_from: z.string().default(""),
  resume_strategy_to: z.string().default(""),
  added_findings: z.array(z.string()).default([]),
  removed_findings: z.array(z.string()).default([]),
  updated_findings: z.array(z.string()).default([]),
  added_steps: z.array(z.string()).default([]),
  removed_steps: z.array(z.string()).default([]),
  added_notes: z.array(z.string()).default([]),
  removed_notes: z.array(z.string()).default([]),
  added_recon_assets: z.array(z.string()).default([]),
  removed_recon_assets: z.array(z.string()).default([]),
});
export type TargetStateDiffView = z.infer<typeof targetStateDiffViewSchema>;

export const reportListItemSchema = z.object({
  name: z.string(),
  path: z.string(),
  kind: z.string(),
  modified_at: optionalString,
  size_bytes: optionalNumber,
});
export type ReportListItem = z.infer<typeof reportListItemSchema>;

export const reportContentViewSchema = z.object({
  path: z.string(),
  kind: z.string(),
  content: z.string(),
});
export type ReportContentView = z.infer<typeof reportContentViewSchema>;

export const taskOptionsSchema = z.object({
  max_rounds: optionalNumber,
  rounds_per_cycle: optionalNumber,
  max_cycles: optionalNumber,
  cve: optionalString,
  cmd: optionalString,
  only_port: optionalNumber,
  only_host: optionalString,
  only_path: optionalString,
  blocked_host: optionalString,
  blocked_path: optionalString,
  allow_actions: z.array(z.string()).nullish(),
  block_actions: z.array(z.string()).nullish(),
});
export type TaskOptions = z.infer<typeof taskOptionsSchema>;

export const taskSummarySchema = z.object({
  target: z.string(),
  command: taskCommandSchema,
  restored: z.boolean().default(false),
  snapshot_id: z.string().default(""),
  schema_version: z.number().default(1),
  status: z.string().default("completed"),
  exit_code: z.number().default(0),
  exit_meaning: z.string().default("completed"),
  run_name: z.string().default(""),
  run_dir: z.string().default(""),
  resume_command: z.string().default(""),
  artifact_locations: z.record(z.string(), z.string()).default({}),
  phase: optionalString,
  findings_count: z.number().default(0),
  verified_count: z.number().default(0),
  pending_count: z.number().default(0),
  candidate_count: z.number().default(0),
  quarantined_count: z.number().default(0),
  executed_steps: z.number().default(0),
  resume_strategy: z.string().default(""),
  resume_reason: z.string().default(""),
  constraints: taskConstraintsSchema.default({}),
  constraint_violations: z.array(z.string()).default([]),
  constraint_violation_events: z.array(constraintViolationEventSchema).default([]),
});
export type TaskSummary = z.infer<typeof taskSummarySchema>;

export const taskRecordSchema = z.object({
  task_id: z.string(),
  command: taskCommandSchema,
  target: z.string(),
  status: taskStatusSchema,
  created_at: z.string(),
  started_at: optionalString,
  completed_at: optionalString,
  error: optionalString,
  resume: z.boolean().default(true),
  snapshot_id: optionalString,
  options: taskOptionsSchema.default({}),
  latest_phase: optionalString,
  latest_message: optionalString,
  summary: taskSummarySchema.nullish(),
});
export type TaskRecord = z.infer<typeof taskRecordSchema>;

/**
 * Task stream payloads are open on the backend (`dict[str, Any]`); the keys
 * declared here are the ones the UI reads, and the rest stay decodable JSON.
 */
export const taskEventPayloadSchema = z
  .object({
    text: optionalString,
    message: optionalString,
    error: optionalString,
    phase: optionalString,
    cycle: optionalNumber,
    round: optionalNumber,
    summary: taskSummarySchema.nullish(),
    constraint_violations: z.array(z.string()).optional(),
    constraint_violation_events: z.array(constraintViolationEventSchema).optional(),
  })
  .catchall(jsonValueSchema);
export type TaskEventPayload = z.infer<typeof taskEventPayloadSchema>;

export const taskEventSchema = z.object({
  event: z.string(),
  task_id: z.string(),
  timestamp: z.string().default(""),
  payload: taskEventPayloadSchema.default({}),
});
export type TaskEvent = z.infer<typeof taskEventSchema>;

export const mcpServiceViewSchema = z.object({
  name: z.string(),
  enabled: z.boolean().default(false),
  priority: z.number().default(0),
  transport_type: z.string().default(""),
  execution_mode: z.string().default(""),
  health_status: z.string().default(""),
  attach_attempted: z.boolean().default(false),
  attach_succeeded: z.boolean().default(false),
  running: z.boolean().default(false),
  can_execute: z.boolean().default(false),
  tool_count: z.number().default(0),
  tools: z.array(z.string()).default([]),
  error: optionalString,
  last_error_type: optionalString,
  started_at: optionalString,
  description: z.string().default(""),
  call_count: z.number().default(0),
  success_count: z.number().default(0),
  failure_count: z.number().default(0),
});
export type MCPServiceView = z.infer<typeof mcpServiceViewSchema>;

export const mcpDiagnosticsViewSchema = z.object({
  total_services: z.number().default(0),
  running_services: z.number().default(0),
  local_services: z.number().default(0),
  placeholder_services: z.number().default(0),
  tool_count: z.number().default(0),
  services: z.array(mcpServiceViewSchema).default([]),
});
export type MCPDiagnosticsView = z.infer<typeof mcpDiagnosticsViewSchema>;

export const constraintAuditEventViewSchema = z.object({
  target: z.string(),
  timestamp: z.string().default(""),
  code: z.string().default(""),
  severity: z.string().default(""),
  source: z.string().default(""),
  action: z.string().default(""),
  tool_name: z.string().default(""),
  phase: z.string().default(""),
  summary: z.string().default(""),
  detail: z.string().default(""),
});
export type ConstraintAuditEventView = z.infer<typeof constraintAuditEventViewSchema>;

export const constraintAuditViewSchema = z.object({
  total_events: z.number().default(0),
  high_severity_events: z.number().default(0),
  by_source: z.record(z.string(), z.number()).default({}),
  by_code: z.record(z.string(), z.number()).default({}),
  recent_events: z.array(constraintAuditEventViewSchema).default([]),
});
export type ConstraintAuditView = z.infer<typeof constraintAuditViewSchema>;

/** Plain acknowledgement envelopes returned by mutation routes. */
export const rollbackAckSchema = z.object({
  status: z.string(),
  target: z.string(),
  snapshot_id: z.string(),
});
export type RollbackAck = z.infer<typeof rollbackAckSchema>;

export const targetClearedAckSchema = z.object({
  status: z.string(),
  target: z.string(),
});
export type TargetClearedAck = z.infer<typeof targetClearedAckSchema>;

export const reportGeneratedAckSchema = z.object({
  status: z.string(),
  path: z.string(),
});
export type ReportGeneratedAck = z.infer<typeof reportGeneratedAckSchema>;

export const taskStoppedAckSchema = z.object({
  status: z.string(),
  task_id: z.string(),
});
export type TaskStoppedAck = z.infer<typeof taskStoppedAckSchema>;

export type { JsonValue };
