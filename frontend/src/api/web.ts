import { z } from "zod";
import { jsonValueSchema, type JsonValue } from "../types/json";
import {
  configViewSchema,
  constraintAuditViewSchema,
  mcpDiagnosticsViewSchema,
  providerModelsResponseSchema,
  providersViewSchema,
  reportContentViewSchema,
  reportGeneratedAckSchema,
  reportListItemSchema,
  rollbackAckSchema,
  targetClearedAckSchema,
  targetPreviewViewSchema,
  targetSnapshotViewSchema,
  targetStateDiffViewSchema,
  targetViewSchema,
  taskEventSchema,
  taskRecordSchema,
  taskStoppedAckSchema,
  type ConfigUpdateRequest,
  type ConfigView,
  type ConstraintAuditView,
  type MCPDiagnosticsView,
  type ProviderModelsRequest,
  type ProviderModelsResponse,
  type ProvidersView,
  type ReportContentView,
  type ReportGeneratedAck,
  type ReportListItem,
  type RollbackAck,
  type TargetClearedAck,
  type TargetPreviewView,
  type TargetSnapshotView,
  type TargetStateDiffView,
  type TargetView,
  type TaskCommand,
  type TaskEvent,
  type TaskOptions,
  type TaskRecord,
  type TaskStoppedAck,
} from "../types/api";

/**
 * Fetch JSON and decode it through `schema` at the network boundary, so callers
 * receive a validated domain value instead of an unparsed response body.
 */
async function requestJson<Output>(
  input: string,
  schema: z.ZodType<Output>,
  init?: RequestInit,
): Promise<Output> {
  let response: Response;
  try {
    response = await fetch(input, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...init?.headers,
      },
      ...init,
    });
  } catch {
    throw new Error("Unable to reach the VulnClaw backend API. Start `vulnclaw web` and reconnect.");
  }

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(
      detail
        ? `Request failed (${response.status}): ${detail}`
        : `Request failed (${response.status}). Try again or open advanced diagnostics.`,
    );
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("The backend API returned non-JSON content. Confirm the backend was started with `vulnclaw web`.");
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new Error(`The backend API returned an unexpected shape for ${input}.`);
  }
  return parsed.data;
}

const errorDetailSchema = z.object({
  detail: jsonValueSchema.optional(),
  message: jsonValueSchema.optional(),
  error: jsonValueSchema.optional(),
  code: jsonValueSchema.optional(),
});

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const parsed = errorDetailSchema.safeParse(await response.json());
      if (!parsed.success) {
        return `Request failed with status ${response.status}`;
      }
      const payload = parsed.data;
      const rawDetail = payload.detail ?? payload.message ?? payload.error;
      const detailStr = stringifyErrorValue(rawDetail);
      if (payload.code !== undefined && payload.code !== null && payload.code !== "") {
        return `[${stringifyErrorValue(payload.code)}] ${detailStr}`;
      }
      return summarizeErrorDetail(detailStr);
    }
    const text = await response.text();
    if (text) {
      return summarizeErrorDetail(text);
    }
    return `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

function summarizeErrorDetail(value: string): string {
  const normalized = value
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) return "";
  if (normalized.length <= 240) return normalized;
  return `${normalized.slice(0, 240)}...`;
}

const errorStringSchema = z.string();

function stringifyErrorValue(value: JsonValue | undefined): string {
  const asString = errorStringSchema.safeParse(value);
  if (asString.success) return asString.data;
  if (value === null || value === undefined) return "";
  return JSON.stringify(value);
}

export function getConfig(): Promise<ConfigView> {
  return requestJson("/api/config", configViewSchema);
}

export function getMcpDiagnostics(): Promise<MCPDiagnosticsView> {
  return requestJson("/api/mcp", mcpDiagnosticsViewSchema);
}

export function getConstraintAudit(): Promise<ConstraintAuditView> {
  return requestJson("/api/constraint-audit", constraintAuditViewSchema);
}

export function updateConfig(payload: ConfigUpdateRequest): Promise<ConfigView> {
  return requestJson("/api/config", configViewSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProviders(): Promise<ProvidersView> {
  return requestJson("/api/providers", providersViewSchema);
}

export function fetchProviderModels(payload: ProviderModelsRequest): Promise<ProviderModelsResponse> {
  return requestJson("/api/provider-models", providerModelsResponseSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTasks(): Promise<TaskRecord[]> {
  return requestJson("/api/tasks", z.array(taskRecordSchema));
}

export function getTargets(): Promise<TargetView[]> {
  return requestJson("/api/targets", z.array(targetViewSchema));
}

export function getTarget(target: string): Promise<TargetView> {
  return requestJson(`/api/targets/${encodeURIComponent(target)}`, targetViewSchema);
}

export function getTargetSnapshots(target: string): Promise<TargetSnapshotView[]> {
  return requestJson(
    `/api/targets/${encodeURIComponent(target)}/snapshots`,
    z.array(targetSnapshotViewSchema),
  );
}

export function getTargetPreview(target: string): Promise<TargetPreviewView> {
  return requestJson(`/api/target-preview/${encodeURIComponent(target)}`, targetPreviewViewSchema);
}

export function getTargetDiff(target: string, fromSnapshotId: string, toSnapshotId?: string): Promise<TargetStateDiffView> {
  const params = new URLSearchParams({ from_snapshot_id: fromSnapshotId });
  if (toSnapshotId) {
    params.set("to_snapshot_id", toSnapshotId);
  }
  return requestJson(
    `/api/target-diff/${encodeURIComponent(target)}?${params.toString()}`,
    targetStateDiffViewSchema,
  );
}

export function getReports(): Promise<ReportListItem[]> {
  return requestJson("/api/reports", z.array(reportListItemSchema));
}

export function getReportContent(path: string): Promise<ReportContentView> {
  return requestJson(`/api/reports/content?path=${encodeURIComponent(path)}`, reportContentViewSchema);
}

export function getReportDownloadUrl(path: string): string {
  return `/api/reports/download?path=${encodeURIComponent(path)}`;
}

export function rollbackTarget(target: string, snapshotId: string): Promise<RollbackAck> {
  return requestJson(`/api/targets/${encodeURIComponent(target)}/rollback`, rollbackAckSchema, {
    method: "POST",
    body: JSON.stringify({ snapshot_id: snapshotId }),
  });
}

export function clearTargetState(target: string): Promise<TargetClearedAck> {
  return requestJson(`/api/targets/${encodeURIComponent(target)}`, targetClearedAckSchema, {
    method: "DELETE",
  });
}

export function generateTargetReport(
  target: string,
  reportFormat: "markdown" | "html" = "markdown",
): Promise<ReportGeneratedAck> {
  return requestJson("/api/reports/target", reportGeneratedAckSchema, {
    method: "POST",
    body: JSON.stringify({ target, report_format: reportFormat }),
  });
}

export function createTask(command: TaskCommand, target: string, resume: boolean, options: TaskOptions = {}): Promise<TaskRecord> {
  return requestJson("/api/tasks/run", taskRecordSchema, {
    method: "POST",
    body: JSON.stringify({
      command,
      target,
      resume,
      options,
    }),
  });
}

export function stopTask(taskId: string): Promise<TaskStoppedAck> {
  return requestJson(`/api/tasks/${taskId}/stop`, taskStoppedAckSchema, {
    method: "POST",
  });
}

const messageDataSchema = z.string();

export function openTaskStream(taskId: string, onEvent: (event: TaskEvent) => void): EventSource {
  const source = new EventSource(`/api/tasks/${taskId}/stream`);
  const handler = (event: Event) => {
    if (!(event instanceof MessageEvent)) return;
    const data = messageDataSchema.safeParse(event.data);
    if (!data.success) return;
    let body: unknown;
    try {
      body = JSON.parse(data.data);
    } catch {
      // Ignore malformed events.
      return;
    }
    const parsed = taskEventSchema.safeParse(body);
    if (parsed.success) {
      onEvent(parsed.data);
    }
  };

  const eventNames = [
    "task_created",
    "task_started",
    "task_state_changed",
    "round_output",
    "cycle_completed",
    "task_completed",
    "task_failed",
    "task_stopped",
  ];
  for (const name of eventNames) {
    source.addEventListener(name, handler);
  }
  source.onmessage = handler;
  return source;
}
