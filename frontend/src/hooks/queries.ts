import { useQuery } from "@tanstack/react-query";
import { getConfig, getConstraintAudit, getMcpDiagnostics, getProviders, getReportContent, getReports, getTarget, getTargetDiff, getTargetPreview, getTargetSnapshots, getTargets, getTasks } from "../api/web";

export function useConfigQuery() {
  return useQuery({
    queryKey: ["config"],
    queryFn: getConfig,
    staleTime: 30_000,
  });
}

export function useProvidersQuery() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: getProviders,
    staleTime: 300_000,
  });
}

export function useMcpDiagnosticsQuery() {
  return useQuery({
    queryKey: ["mcp-diagnostics"],
    queryFn: getMcpDiagnostics,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

export function useConstraintAuditQuery() {
  return useQuery({
    queryKey: ["constraint-audit"],
    queryFn: getConstraintAudit,
    staleTime: 15_000,
    refetchInterval: 15_000,
  });
}

export function useTargetsQuery() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: getTargets,
    staleTime: 15_000,
  });
}

export function useTasksQuery() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: getTasks,
    staleTime: 5_000,
    refetchInterval: 5_000,
  });
}

export function useTargetQuery(target: string | null) {
  return useQuery({
    queryKey: ["target", target],
    queryFn: () => getTarget(requireValue(target)),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useTargetSnapshotsQuery(target: string | null) {
  return useQuery({
    queryKey: ["target-snapshots", target],
    queryFn: () => getTargetSnapshots(requireValue(target)),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useTargetPreviewQuery(target: string | null) {
  return useQuery({
    queryKey: ["target-preview", target],
    queryFn: () => getTargetPreview(requireValue(target)),
    enabled: Boolean(target),
    staleTime: 10_000,
  });
}

export function useTargetDiffQuery(target: string | null, fromSnapshotId: string | null, toSnapshotId?: string | null) {
  return useQuery({
    queryKey: ["target-diff", target, fromSnapshotId, toSnapshotId ?? null],
    queryFn: () => getTargetDiff(requireValue(target), requireValue(fromSnapshotId), toSnapshotId ?? undefined),
    enabled: Boolean(target && fromSnapshotId),
    staleTime: 10_000,
  });
}

export function useReportsQuery() {
  return useQuery({
    queryKey: ["reports"],
    queryFn: getReports,
    staleTime: 30_000,
  });
}

export function useReportContentQuery(path: string | null) {
  return useQuery({
    queryKey: ["report-content", path],
    queryFn: () => getReportContent(requireValue(path)),
    enabled: Boolean(path),
    staleTime: 30_000,
  });
}

/**
 * Unwrap a query key value that is guaranteed present by the query's `enabled`
 * guard. React Query never runs `queryFn` while the value is null, so reaching
 * here with null is a programming error rather than a runtime input.
 */
function requireValue(value: string | null): string {
  if (value === null) {
    throw new Error("Query ran without its required key; check the enabled guard.");
  }
  return value;
}
