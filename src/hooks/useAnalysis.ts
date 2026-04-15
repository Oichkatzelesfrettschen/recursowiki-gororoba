'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AnalysisMetrics,
  AnalysisStatus,
  Finding,
  FindingExplanation,
  SarifLog,
  Severity,
  TopologyGraph,
} from '@/types/analysis';

const POLL_INTERVAL_MS = 2000;

interface FindingsFilter {
  severity?: string;
  tool?: string;
  file?: string;
  limit?: number;
  offset?: number;
}

interface UseAnalysisReturn {
  runId: string | null;
  status: AnalysisStatus | null;
  findings: Finding[];
  totalFindings: number;
  metrics: AnalysisMetrics | null;
  topology: TopologyGraph | null;
  sarif: SarifLog | null;
  explanation: FindingExplanation | null;
  isLoading: boolean;
  isPolling: boolean;
  error: string | null;
  startAnalysis: (path: string, tools?: string[], languages?: string[]) => Promise<void>;
  loadRun: (runId: string) => void;
  fetchFindings: (filters?: FindingsFilter) => Promise<void>;
  explainFinding: (index: number) => Promise<void>;
}

export function useAnalysis(): UseAnalysisReturn {
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [totalFindings, setTotalFindings] = useState(0);
  const [metrics, setMetrics] = useState<AnalysisMetrics | null>(null);
  const [topology, setTopology] = useState<TopologyGraph | null>(null);
  const [sarif, setSarif] = useState<SarifLog | null>(null);
  const [explanation, setExplanation] = useState<FindingExplanation | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // -- helpers to bridge the backend response shape to the frontend types ----

  /** Map a single raw finding object from the API into the frontend Finding type. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function mapFinding(raw: any, idx: number): Finding {
    return {
      index: idx,
      tool: raw.tool ?? '',
      ruleId: raw.rule_id ?? raw.ruleId ?? '',
      message: raw.message ?? '',
      severity: (raw.level ?? raw.severity ?? 'warning') as Severity,
      file: raw.file ?? '',
      startLine: raw.line ?? raw.startLine ?? 0,
      endLine: raw.endLine ?? raw.line ?? 0,
      snippet: raw.snippet,
      cweIds: raw.cweIds,
      fingerprint: raw.fingerprint,
    };
  }

  /** Build AnalysisMetrics from the raw backend response + mapped findings. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function mapMetrics(raw: any, mappedFindings: Finding[]): AnalysisMetrics {
    // Compute by_severity from findings
    const bySeverity: Record<Severity, number> = { error: 0, warning: 0, note: 0 };
    const byTool: Record<string, number> = {};
    const filesSet = new Set<string>();

    for (const f of mappedFindings) {
      bySeverity[f.severity] = (bySeverity[f.severity] ?? 0) + 1;
      byTool[f.tool] = (byTool[f.tool] ?? 0) + 1;
      if (f.file) filesSet.add(f.file);
    }

    // tools_run comes as either a string[] or a number from the backend
    const toolsRunCount = Array.isArray(raw.tools_run)
      ? raw.tools_run.length
      : (raw.tools_run ?? raw.tool_count ?? 0);

    return {
      run_id: raw.run_id ?? '',
      total_findings: raw.total_findings ?? mappedFindings.length,
      by_severity: bySeverity,
      by_tool: byTool,
      files_affected: filesSet.size,
      tools_run: toolsRunCount,
      tools_succeeded: raw.tools_succeeded ?? toolsRunCount,
      tools_failed: raw.tools_failed ?? 0,
      duration_seconds: raw.duration_seconds ?? 0,
    };
  }

  // Fetch all results once analysis is complete
  const fetchResults = useCallback(async (id: string) => {
    try {
      const [findingsRes, metricsRes, topoRes, sarifRes] = await Promise.all([
        fetch(`/api/analyze/${id}/findings?limit=500`),
        fetch(`/api/analyze/${id}/metrics`),
        fetch(`/api/analyze/${id}/topology`),
        fetch(`/api/analyze/${id}/sarif`),
      ]);

      let mappedFindings: Finding[] = [];
      if (findingsRes.ok) {
        const data = await findingsRes.json();
        mappedFindings = (data.findings ?? []).map(mapFinding);
        setFindings(mappedFindings);
        setTotalFindings(data.total ?? data.count ?? mappedFindings.length);
      }
      if (metricsRes.ok) {
        const rawMetrics = await metricsRes.json();
        setMetrics(mapMetrics(rawMetrics, mappedFindings));
      }
      if (topoRes.ok) {
        setTopology(await topoRes.json());
      }
      if (sarifRes.ok) {
        setSarif(await sarifRes.json());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch results');
    }
  }, []);

  // Poll for status
  const startPolling = useCallback(
    (id: string) => {
      setIsPolling(true);
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`/api/analyze/${id}`);
          if (!res.ok) return;
          const data: AnalysisStatus = await res.json();
          setStatus(data);

          if (data.status === 'complete') {
            stopPolling();
            await fetchResults(id);
            setIsLoading(false);
          } else if (data.status === 'failed') {
            stopPolling();
            setError(data.error || 'Analysis failed');
            setIsLoading(false);
          }
        } catch {
          // Keep polling on transient network errors
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling, fetchResults],
  );

  const startAnalysis = useCallback(
    async (path: string, tools?: string[], languages?: string[]) => {
      setIsLoading(true);
      setError(null);
      setFindings([]);
      setMetrics(null);
      setTopology(null);
      setSarif(null);
      setExplanation(null);

      try {
        const body: Record<string, unknown> = { path };
        if (tools) body.tools = tools;
        if (languages) body.languages = languages;

        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          const msg = await res.text();
          throw new Error(msg || `HTTP ${res.status}`);
        }

        const data = await res.json();
        const id = data.run_id as string;
        setRunId(id);
        setStatus({ run_id: id, status: 'queued', progress: 0 });
        startPolling(id);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to start analysis');
        setIsLoading(false);
      }
    },
    [startPolling],
  );

  const loadRun = useCallback(
    (id: string) => {
      setRunId(id);
      setIsLoading(true);
      setError(null);

      // Check current status first, then either poll or fetch results
      fetch(`/api/analyze/${id}`)
        .then(async (res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data: AnalysisStatus = await res.json();
          setStatus(data);

          if (data.status === 'complete') {
            await fetchResults(id);
            setIsLoading(false);
          } else if (data.status === 'failed') {
            setError(data.error || 'Analysis failed');
            setIsLoading(false);
          } else {
            startPolling(id);
          }
        })
        .catch((e) => {
          setError(e instanceof Error ? e.message : 'Failed to load run');
          setIsLoading(false);
        });
    },
    [startPolling, fetchResults],
  );

  const fetchFindings = useCallback(
    async (filters?: FindingsFilter) => {
      if (!runId) return;
      const params = new URLSearchParams();
      if (filters?.severity) params.set('severity', filters.severity);
      if (filters?.tool) params.set('tool', filters.tool);
      if (filters?.file) params.set('file', filters.file);
      if (filters?.limit) params.set('limit', String(filters.limit));
      if (filters?.offset) params.set('offset', String(filters.offset));

      try {
        const res = await fetch(`/api/analyze/${runId}/findings?${params}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const mapped = (data.findings ?? []).map(mapFinding);
        setFindings(mapped);
        setTotalFindings(data.total ?? data.count ?? mapped.length);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to fetch findings');
      }
    },
    [runId],
  );

  const explainFinding = useCallback(
    async (index: number) => {
      if (!runId) return;
      setExplanation(null);
      try {
        const res = await fetch(`/api/analyze/${runId}/explain`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ finding_index: index }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setExplanation(await res.json());
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to explain finding');
      }
    },
    [runId],
  );

  // Cleanup polling on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    runId,
    status,
    findings,
    totalFindings,
    metrics,
    topology,
    sarif,
    explanation,
    isLoading,
    isPolling,
    error,
    startAnalysis,
    loadRun,
    fetchFindings,
    explainFinding,
  };
}
