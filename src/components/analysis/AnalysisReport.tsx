'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { Severity } from '@/types/analysis';
import { useAnalysis } from '@/hooks/useAnalysis';
import AnalysisProgress from './AnalysisProgress';
import SeverityOverview from './SeverityOverview';
import MetricsPanel from './MetricsPanel';
import ToolBreakdown from './ToolBreakdown';
import FilterBar from './FilterBar';
import FindingsTable from './FindingsTable';
import DependencyGraph from './DependencyGraph';

interface AnalysisReportProps {
  /** Existing run to load -- omit to start fresh. */
  runId?: string;
  /** Target path when starting a new analysis. */
  targetPath?: string;
}

export default function AnalysisReport({ runId: initialRunId, targetPath }: AnalysisReportProps) {
  const {
    runId,
    status,
    findings,
    metrics,
    topology,
    explanation,
    isLoading,
    isPolling,
    error,
    startAnalysis,
    loadRun,
    fetchFindings,
    explainFinding,
  } = useAnalysis();

  // Filters
  const [selectedSeverity, setSelectedSeverity] = useState<Severity | ''>('');
  const [selectedTool, setSelectedTool] = useState('');
  const [fileFilter, setFileFilter] = useState('');

  // Load existing run or start new analysis
  useEffect(() => {
    if (initialRunId) {
      loadRun(initialRunId);
    }
    // startAnalysis is triggered by user action, not on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRunId]);

  // Re-fetch findings when filters change
  useEffect(() => {
    if (!runId || isPolling) return;
    fetchFindings({
      severity: selectedSeverity || undefined,
      tool: selectedTool || undefined,
      file: fileFilter || undefined,
    });
  }, [runId, selectedSeverity, selectedTool, fileFilter, isPolling, fetchFindings]);

  // Derive list of tools from metrics
  const toolNames = useMemo(
    () => (metrics ? Object.keys(metrics.by_tool) : []),
    [metrics],
  );

  // Filtered findings (client-side, since server may not support all filters)
  const filteredFindings = useMemo(() => {
    let result = findings;
    if (selectedSeverity) {
      result = result.filter((f) => f.severity === selectedSeverity);
    }
    if (selectedTool) {
      result = result.filter((f) => f.tool === selectedTool);
    }
    if (fileFilter) {
      const lower = fileFilter.toLowerCase();
      result = result.filter((f) => f.file.toLowerCase().includes(lower));
    }
    return result;
  }, [findings, selectedSeverity, selectedTool, fileFilter]);

  const handleStart = useCallback(() => {
    if (targetPath) {
      startAnalysis(targetPath);
    }
  }, [targetPath, startAnalysis]);

  const isComplete = status?.status === 'complete';
  const isFailed = status?.status === 'failed';
  const inProgress = status && !isComplete && !isFailed;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 card-japanese p-6 rounded-lg">
        <div>
          <h2 className="text-lg font-serif font-bold text-[var(--foreground)]">
            Analysis Report
          </h2>
          {runId && (
            <p className="text-xs text-[var(--muted)] font-mono mt-1">{runId}</p>
          )}
          {targetPath && (
            <p className="text-xs text-[var(--muted)] mt-1">Target: {targetPath}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isComplete && (
            <span className="severity-badge severity-badge-note">Complete</span>
          )}
          {isFailed && (
            <span className="severity-badge severity-badge-error">Failed</span>
          )}
          {inProgress && (
            <span className="severity-badge severity-badge-warning">In Progress</span>
          )}
          {!runId && targetPath && (
            <button type="button" onClick={handleStart} className="btn-japanese text-sm">
              Start Analysis
            </button>
          )}
          {isComplete && targetPath && (
            <button
              type="button"
              onClick={handleStart}
              className="btn-japanese text-sm"
            >
              Re-run
            </button>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-[var(--highlight)]/5 border border-[var(--highlight)]/30 rounded-lg p-4">
          <p className="text-sm text-[var(--highlight)]">{error}</p>
        </div>
      )}

      {/* Progress */}
      {inProgress && status && (
        <AnalysisProgress
          phase={status.status}
          progress={status.progress}
          message={status.message}
        />
      )}

      {/* Results (only shown when complete) */}
      {isComplete && metrics && (
        <>
          {/* Overview row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SeverityOverview bySeverity={metrics.by_severity} total={metrics.total_findings} />
            <MetricsPanel metrics={metrics} />
          </div>

          {/* Tool breakdown */}
          <ToolBreakdown byTool={metrics.by_tool} />

          {/* Findings table with filters */}
          <FilterBar
            tools={toolNames}
            selectedSeverity={selectedSeverity}
            selectedTool={selectedTool}
            fileFilter={fileFilter}
            onSeverityChange={setSelectedSeverity}
            onToolChange={setSelectedTool}
            onFileChange={setFileFilter}
          />
          <FindingsTable
            findings={filteredFindings}
            explanation={explanation}
            onExplain={explainFinding}
          />

          {/* Dependency graph */}
          {topology && <DependencyGraph topology={topology} />}
        </>
      )}

      {/* Empty state */}
      {!runId && !isLoading && !error && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-16 h-16 rounded-full bg-[var(--accent-primary)]/10 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-[var(--accent-primary)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h3 className="text-lg font-serif text-[var(--foreground)] mb-2">
            No analysis loaded
          </h3>
          <p className="text-sm text-[var(--muted)]">
            Start an analysis or navigate to an existing run to view results.
          </p>
        </div>
      )}
    </div>
  );
}
